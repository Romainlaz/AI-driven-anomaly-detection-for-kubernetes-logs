import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import OneHotEncoder
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from scipy.sparse import hstack
import re

# === CONFIG ===
TFIDF_MAX_FEATURES = 300
CRITICAL_KEYWORDS = [
    'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
    'timeout', 'refused', 'denied', 'crash', 'killed',
    'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
    'outofmemory', 'segmentation fault', 'panic', 'cannot',
    'unable', 'broken', 'corrupt', 'invalid'
]

# === DATA ===
# Remplace par ton vrai CSV !
CSV_PATH = "/Users/pierresimian-salvay/Desktop/Wiremind_logs (1).csv"
df = pd.read_csv(CSV_PATH)

# === PREPROCESSING ===
def redact_pii(msg):
    msg = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '<EMAIL>', str(msg))
    msg = re.sub(r'\b\d{,}(?:\.\d{,}){}\b', '<IP>', msg)
    msg = re.sub(r'\b\d+\b', '<NUM>', msg)
    msg = re.sub(r'/[A-Za-z0-9_\-\.]+', '<PATH>', msg)
    return msg.lower()
df['clean_message'] = df['wiremind.message'].apply(redact_pii)

# === TEMPLATE MINING ===
config = TemplateMinerConfig()
miner = TemplateMiner(config=config)
templates = []
for msg in df['clean_message']:
    result = miner.add_log_message(msg)
    templates.append(result["template_mined"])
df['template'] = templates

# === TF-IDF ===
vectorizer = CountVectorizer(max_features=TFIDF_MAX_FEATURES)
X_templates = vectorizer.fit_transform(df['template'])

# === CONTEXT ENCODING ===
encoder = OneHotEncoder(sparse_output=True, handle_unknown="ignore")
X_context = encoder.fit_transform(df[['kubernetes.namespace_name', 'kubernetes.pod_name']])

# === NUMERIC FEATURES (17) ===
def extract_features(row):
    msg = str(row['wiremind.message'])
    tokens = msg.split()
    return pd.Series({
        'length': len(msg),
        'num_tokens': len(tokens),
        'digit_ratio': sum(c.isdigit() for c in msg) / (len(msg) + 1e-5),
        'upper_ratio': sum(c.isupper() for c in msg) / (len(msg) + 1e-5),
        'special_ratio': sum(not c.isalnum() and not c.isspace() for c in msg) / (len(msg) + 1e-5),
        'avg_token_length': sum(len(t) for t in tokens) / (len(tokens) + 1e-5),
        'has_error_kw': float(any(kw in msg.lower() for kw in CRITICAL_KEYWORDS)),
        'is_error_level': 1.0 if any(lvl in msg.upper() for lvl in ['ERROR', 'FATAL', 'CRITICAL']) else 0.0,
        'is_warn_level': 1.0 if 'WARN' in msg.upper() else 0.0,
        'has_traceback': 1.0 if 'traceback' in msg.lower() or 'exception' in msg.lower() else 0.0,
        'rate_5min': 0.0,
        'rate_15min': 0.0,
        'rate_1h': 0.0,
        'std_5min': 0.0,
        'std_15min': 0.0,
        'acceleration': 0.0,
        'burst_ratio': 0.0
    })
features_df = df.apply(extract_features, axis=1)

X_numeric = features_df.values

# === COMBINE ===
X = hstack([X_templates, X_context, X_numeric])

# === TRAIN ISOLATION FOREST ===
iso_forest = IsolationForest(
    n_estimators=300,
    contamination=0.05,
    max_samples=0.8,
    bootstrap=True,
    random_state=42
)
iso_forest.fit(X)

# === THRESHOLD ===
scores = iso_forest.score_samples(X)
threshold = np.percentile(scores, 90)

# === SAVE ===
model_data = {
    'iso_forest': iso_forest,
    'miner': miner,
    'vectorizer': vectorizer,
    'encoder': encoder,
    'threshold': threshold,
    'threshold_percentile': 90,
    'critical_keywords': CRITICAL_KEYWORDS,
    'detection_method': 'hybrid'
}
with open('hybrid_model.pkl', 'wb') as f:
    pickle.dump(model_data, f)
print("[OK] Modèle sauvegardé sous hybrid_model.pkl")
