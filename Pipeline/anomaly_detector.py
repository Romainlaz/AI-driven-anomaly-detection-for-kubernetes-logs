from drain3 import TemplateMiner
from sklearn.ensemble import IsolationForest
import pandas as pd

class AnomalyDetector:
    """Isolation Forest + template mining baseline"""

    def __init__(self):
        self.tm = TemplateMiner()
        self.model = None

    def fit(self, messages):
        template_ids = []
        for msg in messages:
            self.tm.add_log_message(msg)
            template_ids.append(self.tm.match_template(msg).id)
        df = pd.DataFrame({"template_id": template_ids})
        self.model = IsolationForest(contamination=0.2, random_state=42)
        self.model.fit(df)

    def predict(self, messages):
        template_ids = [self.tm.match_template(msg).id for msg in messages]
        df = pd.DataFrame({"template_id": template_ids})
        scores = self.model.decision_function(df)
        preds = self.model.predict(df)  # -1 = anomaly, 1 = normal
        return [{"score": s, "is_anomaly": 1 if p == -1 else 0} for s, p in zip(scores, preds)]
