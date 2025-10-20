from fastapi import FastAPI
from pydantic import BaseModel
from Pipeline.normalizer import Normalizer
from Pipeline.anomaly_detector import AnomalyDetector
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="Log Anomaly Detector")

normalizer = Normalizer()
detector = AnomalyDetector()

# Entraînement initial
seed_logs = [
    "User login success",
    "User login failed",
    "Connection timeout",
]
detector.fit([normalizer.normalize(msg) for msg in seed_logs])

# Prometheus metric
ANOMALY_COUNTER = Counter("anomaly_count_total", "Total anomalies detected")

class LogEntry(BaseModel):
    message: str

@app.post("/score")
def score_log(entry: LogEntry):
    msg_norm = normalizer.normalize(entry.message)
    result = detector.predict([msg_norm])[0]
    if result["is_anomaly"]:
        ANOMALY_COUNTER.inc()
    return result

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
