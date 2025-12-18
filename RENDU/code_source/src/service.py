"""
Anomaly Detection Service - FastAPI
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import time
from typing import Dict
from .model import AnomalyDetector

# Prometheus metrics
anomaly_counter = Counter('anomalies_detected_total', 'Total anomalies detected')
prediction_counter = Counter('predictions_total', 'Total predictions')
prediction_latency = Histogram('prediction_latency_seconds', 'Prediction latency')

# FastAPI app
app = FastAPI(title="Anomaly Detection Service", version="2.0.0")

# Global model instance
model: AnomalyDetector = None


class LogEntry(BaseModel):
    """Log entry schema"""
    message: str
    namespace: str
    pod: str
    timestamp: str = None


class PredictionResponse(BaseModel):
    """Prediction response schema"""
    is_anomaly: bool
    score: float
    threshold: float
    template: str
    confidence: float
    detection_method: str


@app.on_event("startup")
async def load_model():
    """Load model on startup"""
    global model
    try:
        import pickle
        import numpy as np
        from scipy.sparse import hstack
        import os
        
        # Load hybrid model - try multiple locations
        model_file = os.getenv("MODEL_FILE", "model.pkl")
        if not os.path.exists(model_file):
            model_file = "hybrid_model.pkl"
        
        with open(model_file, "rb") as f:
            model_data = pickle.load(f)
        
        print(f"[OK] Loaded hybrid model from {model_file}")
        print(f"[INFO]   - Isolation Forest: {model_data['iso_forest'].n_estimators} trees")
        print(f"[INFO]   - Total features: {model_data['iso_forest'].n_features_in_}")
        print(f"[INFO]   - Vectorizer vocabulary: {len(model_data['vectorizer'].vocabulary_)} terms")
        
        # Create hybrid predictor wrapper (ISO Forest + Keywords)
        class HybridPredictor:
            # Critical keywords that always indicate anomalies
            CRITICAL_KEYWORDS = [
                'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
                'timeout', 'refused', 'denied', 'crash', 'killed',
                'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
                'outofmemory', 'segmentation fault', 'panic', 'cannot',
                'unable', 'broken', 'corrupt', 'invalid'
            ]
            
            def __init__(self, data):
                self.iso_forest = data['iso_forest']
                self.miner = data['miner']
                self.vectorizer = data['vectorizer']
                self.encoder = data['encoder']
                self.threshold = data['threshold']
                
                # Temporal aggregator for stateful features
                from collections import defaultdict, deque
                from datetime import datetime
                self.windows = defaultdict(lambda: {
                    '5min': deque(maxlen=5),    # 5 minutes
                    '15min': deque(maxlen=15),  # 15 minutes
                    '1h': deque(maxlen=60)      # 1 hour
                })
                self.last_update = defaultdict(lambda: datetime.now())
                
            def _has_critical_keyword(self, message):
                """Check if message contains critical keywords"""
                msg_lower = message.lower()
                return any(keyword in msg_lower for keyword in self.CRITICAL_KEYWORDS)
            
            def _update_temporal_features(self, pod_key, has_error):
                """Update temporal aggregation windows for a pod"""
                from datetime import datetime
                now = datetime.now()
                last = self.last_update[pod_key]
                
                # Check if we need to flush to a new minute bucket
                if (now - last).total_seconds() >= 60:
                    # Add error count for this minute to windows
                    self.windows[pod_key]['5min'].append(0)
                    self.windows[pod_key]['15min'].append(0)
                    self.windows[pod_key]['1h'].append(0)
                    self.last_update[pod_key] = now
                
                # Increment current minute count if error
                if has_error and len(self.windows[pod_key]['5min']) > 0:
                    self.windows[pod_key]['5min'][-1] += 1
                    self.windows[pod_key]['15min'][-1] += 1
                    self.windows[pod_key]['1h'][-1] += 1
            
            def _get_temporal_features(self, pod_key):
                """Get aggregated temporal features for a pod"""
                windows = self.windows[pod_key]
                
                # Calculate rates (errors per minute)
                rate_5min = sum(windows['5min']) / max(len(windows['5min']), 1)
                rate_15min = sum(windows['15min']) / max(len(windows['15min']), 1)
                rate_1h = sum(windows['1h']) / max(len(windows['1h']), 1)
                
                # Calculate standard deviations
                std_5min = np.std(windows['5min']) if len(windows['5min']) > 1 else 0
                std_15min = np.std(windows['15min']) if len(windows['15min']) > 1 else 0
                
                # Calculate acceleration and burst ratio
                acceleration = rate_5min - rate_15min
                burst_ratio = rate_5min / (rate_1h + 1e-6)
                
                return [rate_5min, rate_15min, rate_1h, std_5min, std_15min, acceleration, burst_ratio]
                
            def predict(self, log_entry):
                import re
                from sklearn.feature_extraction.text import CountVectorizer
                import pandas as pd
                from datetime import datetime
                
                # Redact PII and normalize
                msg = log_entry['message']
                msg = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "<EMAIL>", msg)
                msg = re.sub(r'\b\d{,}(?:\.\d{,}){}\b', "<IP>", msg)
                msg = re.sub(r'\b\d+\b', "<NUM>", msg)
                msg = re.sub(r'/[A-Za-z0-9_\-\.]+', "<PATH>", msg)
                msg = msg.lower()
                
                # Template with Drain if available
                if self.miner is not None:
                    result = self.miner.match(msg)
                    template = result.get_template() if result else msg
                else:
                    # Fallback: simple normalization
                    template = re.sub(r'<num>+', '<num>', msg)
                    template = re.sub(r'<path>+', '<path>', template)
                    template = re.sub(r'\s+', ' ', template).strip()
                
                # Vectorize template
                X_template = self.vectorizer.transform([template])
                
                # Encode context (namespace AND pod required)
                # Use DataFrame to match the feature names from training
                import pandas as pd
                context_df = pd.DataFrame({
                    'kubernetes.namespace_name': [log_entry['namespace']],
                    'kubernetes.pod_name': [log_entry['pod']]
                })
                X_context = self.encoder.transform(context_df)
                
                # Basic numeric features (10 features to match training)
                msg = log_entry['message']
                tokens = msg.split()
                length = len(msg)
                num_tokens = len(tokens)
                digit_ratio = sum(c.isdigit() for c in msg) / (length + 1e-5)
                upper_ratio = sum(c.isupper() for c in msg) / (length + 1e-5)
                special_ratio = sum(not c.isalnum() and not c.isspace() for c in msg) / (length + 1e-5)
                avg_token_length = sum(len(t) for t in tokens) / (num_tokens + 1e-5)
                has_error_kw = float(self._has_critical_keyword(msg))
                is_error_level = 1.0 if any(lvl in msg.upper() for lvl in ['ERROR', 'FATAL', 'CRITICAL']) else 0.0
                is_warn_level = 1.0 if 'WARN' in msg.upper() else 0.0
                has_traceback = 1.0 if 'traceback' in msg.lower() or 'exception' in msg.lower() else 0.0
                
                # Check error keyword for temporal update
                has_error = int(self._has_critical_keyword(msg))
                
                # Update temporal aggregation windows
                pod_key = f"{log_entry['namespace']}:{log_entry['pod']}"
                self._update_temporal_features(pod_key, has_error)
                
                # Get temporal aggregated features (7)
                temporal_agg = self._get_temporal_features(pod_key)
                
                # Combine all features: templates + context + numeric(10) + temporal_agg(7) = 17 total numeric
                # Total features: 300 (tfidf) + context + 17 numeric
                X = hstack([X_template, X_context, 
                           np.array([[length, num_tokens, digit_ratio, upper_ratio,
                                      special_ratio, avg_token_length, has_error_kw, is_error_level, is_warn_level, has_traceback,
                                      *temporal_agg]])])
                
                # HYBRID DETECTION: Keywords OR ISO Forest
                
                # Level 1: Check critical keywords (high confidence)
                has_keyword = self._has_critical_keyword(log_entry['message'])
                
                # Level 2: ISO Forest prediction (convention sklearn native)
                # score < threshold → Anomalie
                # score >= threshold → Normal
                score = self.iso_forest.decision_function(X)[0]  # PAS d'inversion
                iso_anomaly = score < self.threshold  # Score BAS = anomalie
                
                # Combine: Anomaly if EITHER method detects it
                is_anomaly = has_keyword or iso_anomaly
                
                # Determine detection method and confidence
                if has_keyword and iso_anomaly:
                    method = "hybrid_both"
                    confidence = 0.95
                elif has_keyword:
                    method = "keyword_detection"
                    confidence = 0.90
                elif iso_anomaly:
                    method = "isolation_forest"
                    # Confidence basée sur combien le score est en-dessous du threshold
                    confidence = min(0.9, float(abs(self.threshold - score) / 0.1))
                else:
                    method = "none"
                    confidence = 0.0
                
                return {
                    'is_anomaly': bool(is_anomaly),
                    'score': float(score),
                    'threshold': float(self.threshold),
                    'template': template,
                    'confidence': float(confidence),
                    'detection_method': method
                }
        
        model = HybridPredictor(model_data)
        print("[INFO] Model loaded successfully")
    except Exception as e:
        print(f"[INFO]  Failed to load model: {e}")
        import traceback
        traceback.print_exc()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": model is not None
    }


@app.get("/ready")
async def readiness():
    """Readiness probe"""
    if model is None:
        raise HTTPException(status_code=50, detail="Model not loaded")
    return {"status": "ready"}


@app.post("/predict", response_model=PredictionResponse)
async def predict(log_entry: LogEntry):
    """
    Predict if log entry is anomalous
    
    Example:
    ```
    curl -X POST http://localhost:8080/predict \\
      -H "Content-Type: application/json" \\
      -d '{
        "message": "Error: connection refused",
        "namespace": "default",
        "pod": "api-server-xyz"
      }'
    ```
    """
    if model is None:
        raise HTTPException(status_code=50, detail="Model not loaded")
    
    start_time = time.time()
    
    try:
        # Predict
        result = model.predict(log_entry.dict())
        
        # Update metrics
        prediction_counter.inc()
        if result['is_anomaly']:
            anomaly_counter.inc()
        
        latency = time.time() - start_time
        prediction_latency.observe(latency)
        
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": "Anomaly Detection",
        "version": "2.0.0",
        "endpoints": {
            "POST /predict": "Predict anomaly",
            "GET /health": "Health check",
            "GET /ready": "Readiness probe",
            "GET /metrics": "Prometheus metrics"
        }
    }
