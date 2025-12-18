"""
Modèle Hybride de Détection d'Anomalies
========================================

Ce fichier contient la configuration complète du modèle hybride.
Pour l'utiliser, exécutez : python hybrid_model.py
"""

from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder
from sklearn.feature_extraction.text import CountVectorizer
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
import pickle

# Configuration du modèle Isolation Forest
ISOLATION_FOREST_CONFIG = {
    'n_estimators': 300,
    'contamination': 0.05,
    'max_samples': 0.8,
    'bootstrap': True,
    'random_state': 42
}

# Seuil de détection optimisé
THRESHOLD_PERCENTILE = 90  # Percentile pour seuil restrictif
THRESHOLD_VALUE = None  # Calculé lors de l'entraînement

# Liste des mots-clés critiques
CRITICAL_KEYWORDS = [
    'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
    'timeout', 'refused', 'denied', 'crash', 'killed',
    'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
    'outofmemory', 'segmentation fault', 'panic', 'cannot',
    'unable', 'broken', 'corrupt', 'invalid'
]

# Configuration Drain pour extraction de templates
DRAIN_CONFIG = {
    'depth': 4,
    'sim_th': 0.4,
    'max_children': 100,
    'max_clusters': 0
}

# Configuration du vectorizer de templates
VECTORIZER_CONFIG = {
    'max_features': 300,
    'token_pattern': r'\S+'
}

# Features temporelles
TEMPORAL_FEATURES = [
    'rate_5min',    # Taux d'erreurs sur 5 minutes
    'rate_5min',   # Taux d'erreurs sur 5 minutes
    'rate_h',      # Taux d'erreurs sur  heure
    'std_5min',     # Écart-type sur 5 minutes
    'std_5min',    # Écart-type sur 5 minutes
    'acceleration', # Différence rate_5min - rate_5min
    'burst_ratio'   # Ratio rate_5min / rate_h (détection de pics)
]

# Features numériques de base
NUMERIC_FEATURES = [
    'length',       # Longueur du message
    'num_tokens',   # Nombre de tokens
    'digit_ratio',  # Ratio de chiffres
    'upper_ratio',  # Ratio de majuscules
    'hour',         # Heure du timestamp
    'minute',       # Minute du timestamp
    'weekday',      # Jour de la semaine
    'is_weekend',   # Weekend ou non
    'latency_ms'    # Latence extraite (si présente)
]


def create_model():
    """
    Crée un nouveau modèle Isolation Forest avec la configuration optimale.
    
    Returns:
        dict: Dictionnaire contenant tous les composants du modèle
    """
    # Isolation Forest
    iso_forest = IsolationForest(**ISOLATION_FOREST_CONFIG)
    
    # Drain Template Miner
    config = TemplateMinerConfig()
    config.load(DRAIN_CONFIG)
    miner = TemplateMiner(config=config)
    
    # Vectorizer pour templates
    vectorizer = CountVectorizer(**VECTORIZER_CONFIG)
    
    # Encoder pour contexte Kubernetes
    encoder = OneHotEncoder(sparse_output=True, handle_unknown="ignore")
    
    return {
        'iso_forest': iso_forest,
        'miner': miner,
        'vectorizer': vectorizer,
        'encoder': encoder,
        'threshold': THRESHOLD_VALUE,
        'threshold_percentile': THRESHOLD_PERCENTILE,
        'critical_keywords': CRITICAL_KEYWORDS,
        'detection_method': 'hybrid',
        'version': '.0.0',
        'features': {
            'temporal': TEMPORAL_FEATURES,
            'numeric': NUMERIC_FEATURES
        }
    }


def has_critical_keyword(message):
    """
    Vérifie si un message contient un mot-clé critique.
    
    Args:
        message (str): Message de log à analyser
        
    Returns:
        bool: True si un mot-clé critique est détecté
    """
    msg_lower = message.lower()
    return any(keyword in msg_lower for keyword in CRITICAL_KEYWORDS)


def predict(model_data, log_entry):
    """
    Prédiction hybride sur un log.
    
    Args:
        model_data (dict): Modèle chargé
        log_entry (dict): Log avec 'message', 'namespace', 'pod'
        
    Returns:
        dict: Résultat avec is_anomaly, method, confidence
    """
    message = log_entry.get('message', '')
    
    # Détection par keywords (prioritaire)
    if has_critical_keyword(message):
        return {
            'is_anomaly': True,
            'method': 'keyword_detection',
            'confidence': 0.90,
            'message': message
        }
    
    # Détection par Isolation Forest
    # Note: Nécessite le preprocessing complet (voir src/model.py)
    return {
        'is_anomaly': False,
        'method': 'none',
        'confidence': 0.0,
        'message': message
    }


def save_model(model_data, filepath='hybrid_model.pkl'):
    """
    Sauvegarde le modèle au format pickle.
    
    Args:
        model_data (dict): Modèle à sauvegarder
        filepath (str): Chemin de destination
    """
    with open(filepath, 'wb') as f:
        pickle.dump(model_data, f)
    print(f"Modèle sauvegardé : {filepath}")


def load_model(filepath='hybrid_model.pkl'):
    """
    Charge un modèle depuis un fichier pickle.
    
    Args:
        filepath (str): Chemin du fichier
        
    Returns:
        dict: Modèle chargé
    """
    with open(filepath, 'rb') as f:
        model_data = pickle.load(f)
    print(f"Modèle chargé : {filepath}")
    return model_data


if __name__ == '__main__':
    print("=" * 70)
    print("Configuration du Modèle Hybride")
    print("=" * 70)
    print(f"\nIsolation Forest:")
    print(f"[INFO]  - Estimateurs : {ISOLATION_FOREST_CONFIG['n_estimators']}")
    print(f"[INFO]  - Contamination : {ISOLATION_FOREST_CONFIG['contamination']}")
    print(f"[INFO]  - Max samples : {ISOLATION_FOREST_CONFIG['max_samples']}")
    
    print(f"\nKeywords critiques : {len(CRITICAL_KEYWORDS)}")
    print(f"[INFO]  {', '.join(CRITICAL_KEYWORDS[:0])}...")
    
    print(f"\nFeatures temporelles : {len(TEMPORAL_FEATURES)}")
    print(f"[INFO]  {', '.join(TEMPORAL_FEATURES)}")
    
    print(f"\nFeatures numériques : {len(NUMERIC_FEATURES)}")
    print(f"[INFO]  {', '.join(NUMERIC_FEATURES)}")
    
    print(f"\nSeuil de détection : Percentile {THRESHOLD_PERCENTILE}%")
    
    print("\n" + "=" * 70)
    print("Pour créer un nouveau modèle :")
    print("[INFO]  model_data = create_model()")
    print("[INFO]  save_model(model_data, 'hybrid_model.pkl')")
    print("\nPour charger un modèle existant :")
    print("[INFO]  model_data = load_model('hybrid_model.pkl')")
    print("=" * 70)
