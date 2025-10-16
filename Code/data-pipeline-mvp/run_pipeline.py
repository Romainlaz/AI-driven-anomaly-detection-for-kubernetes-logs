from Pipeline.anomaly_detector import AnomalyDetector
from Pipeline.normalizer import Normalizer

detector = AnomalyDetector()
normalizer = Normalizer()

# Exemple de log
logs = [
    {"timestamp": "2025-10-09T12:00:00Z", "service": "auth", "message": "User login success"},
    {"timestamp": "2025-10-09T12:01:00Z", "service": "auth", "message": "User login failed"},
    {"timestamp": "2025-10-09T12:02:00Z", "service": "db", "message": "Connection timeout"},
]

for log in logs:
    log["_message_safe"] = normalizer.normalize(log["message"])
    log["is_anomaly"] = detector.predict(log["_message_safe"])
    print(log)
