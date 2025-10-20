from Pipeline.anomaly_detector import AnomalyDetector
from Pipeline.normalizer import Normalizer

normalizer = Normalizer()
detector = AnomalyDetector()

logs = [
    {"timestamp": "2025-10-09T12:00:00Z", "service": "auth", "message": "User login success"},
    {"timestamp": "2025-10-09T12:01:00Z", "service": "auth", "message": "User login failed"},
    {"timestamp": "2025-10-09T12:02:00Z", "service": "db", "message": "Connection timeout"},
]

# Normalisation
messages = [normalizer.normalize(log["message"]) for log in logs]

# Entraînement
detector.fit(messages)

# Prédiction
results = detector.predict(messages)

# Lier résultats aux logs et afficher
for log, r in zip(logs, results):
    log.update(r)
    print(log)
