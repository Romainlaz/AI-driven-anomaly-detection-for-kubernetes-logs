# Pipeline/anomaly_detector.py
class AnomalyDetector:
    """Simple baseline anomaly detector (placeholder for MVP)."""

    def __init__(self):
        pass

    def predict(self, message: str) -> int:
        """
        Predict anomaly: 0 = normal, 1 = anomaly.
        For now, flag messages containing 'error' or 'failed'.
        """
        if any(word in message.lower() for word in ["error", "fail", "timeout", "exception"]):
            return 1
        return 0
