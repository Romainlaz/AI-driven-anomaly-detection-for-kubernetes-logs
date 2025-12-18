"""
Anomaly Detection Model - Isolation Forest with Drain3
"""
import numpy as np
import pandas as pd
import pickle
import re
from typing import Dict, List, Tuple
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import OneHotEncoder
from scipy.sparse import hstack
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig


class AnomalyDetector:
    """Isolation Forest anomaly detector with Drain template extraction"""
    
    def __init__(self, threshold_percentile: int = 90):
        self.threshold_percentile = threshold_percentile
        self.iso_forest = None
        self.miner = None
        self.vectorizer = None
        self.encoder = None
        self.threshold = None
        
    def _redact_pii(self, message: str) -> str:
        """Remove PII from log messages"""
        message = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "<EMAIL>", str(message))
        message = re.sub(r'\b\d{,}(?:\.\d{,}){}\b', "<IP>", message)
        message = re.sub(r'\b\d+\b', "<NUM>", message)
        message = re.sub(r'/[A-Za-z0-9_\-\.]+', "<PATH>", message)
        return message.lower()
    
    def _extract_features(self, message: str) -> Dict:
        """Extract basic features from log message"""
        return {
            'length': len(message),
            'num_tokens': len(message.split()),
            'num_digits': sum(c.isdigit() for c in message),
            'num_upper': sum(c.isupper() for c in message),
            'digit_ratio': sum(c.isdigit() for c in message) / (len(message) + 1e-5),
            'upper_ratio': sum(c.isupper() for c in message) / (len(message) + 1e-5),
        }
    
    def train(self, logs_df: pd.DataFrame):
        """Train the anomaly detector"""
        print("Training Isolation Forest model...")
        
        # Redact PII
        logs_df['clean_message'] = logs_df['message'].apply(self._redact_pii)
        
        # Extract templates with Drain
        config = TemplateMinerConfig()
        self.miner = TemplateMiner(config=config)
        templates = []
        for msg in logs_df['clean_message']:
            result = self.miner.add_log_message(msg)
            templates.append(result["template_mined"])
        logs_df['template'] = templates
        
        # Vectorize templates
        self.vectorizer = CountVectorizer(max_features=300)
        X_templates = self.vectorizer.fit_transform(logs_df['template'])
        
        # Encode context (namespace + pod)
        self.encoder = OneHotEncoder(sparse_output=True, handle_unknown="ignore")
        X_context = self.encoder.fit_transform(logs_df[['namespace', 'pod']])
        
        # Extract basic features
        features = logs_df['message'].apply(self._extract_features)
        features_df = pd.DataFrame(features.tolist())
        
        # Combine all features
        X = hstack([X_templates, X_context, features_df.values])
        
        # Train Isolation Forest on normal logs only
        self.iso_forest = IsolationForest(
            n_estimators=300,
            contamination=0.05,
            max_samples=0.8,
            bootstrap=True,
            random_state=42
        )
        self.iso_forest.fit(X)
        
        # Compute optimal threshold
        scores = -self.iso_forest.decision_function(X)
        self.threshold = np.percentile(scores, self.threshold_percentile)
        
        print(f"[INFO] Model trained. Threshold (p{self.threshold_percentile}): {self.threshold:.2f}")
        return self
    
    def predict(self, log_entry: Dict) -> Dict:
        """
        Predict if a single log entry is anomalous
        
        Args:
            log_entry: Dict with keys 'message', 'namespace', 'pod'
            
        Returns:
            Dict with 'is_anomaly', 'score', 'template'
        """
        # Redact and extract template
        clean_msg = self._redact_pii(log_entry['message'])
        result = self.miner.add_log_message(clean_msg)
        template = result["template_mined"]
        
        # Vectorize
        X_template = self.vectorizer.transform([template])
        X_context = self.encoder.transform([[log_entry['namespace'], log_entry['pod']]])
        
        # Extract features
        features = self._extract_features(log_entry['message'])
        X_features = np.array(list(features.values())).reshape(1, -1)
        
        # Combine
        X = hstack([X_template, X_context, X_features])
        
        # Score
        score = -self.iso_forest.decision_function(X)[0]
        is_anomaly = score >= self.threshold
        
        return {
            'is_anomaly': bool(is_anomaly),
            'score': float(score),
            'threshold': float(self.threshold),
            'template': template,
            'confidence': float((score - self.threshold) / self.threshold) if is_anomaly else 0.0
        }
    
    def save(self, filepath: str):
        """Save model to disk"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'iso_forest': self.iso_forest,
                'miner': self.miner,
                'vectorizer': self.vectorizer,
                'encoder': self.encoder,
                'threshold': self.threshold,
                'threshold_percentile': self.threshold_percentile
            }, f)
        print(f"[INFO] Model saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str):
        """Load model from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        detector = cls(threshold_percentile=data['threshold_percentile'])
        detector.iso_forest = data['iso_forest']
        detector.miner = data['miner']
        detector.vectorizer = data['vectorizer']
        detector.encoder = data['encoder']
        detector.threshold = data['threshold']
        
        print(f"[INFO] Model loaded from {filepath}")
        return detector
