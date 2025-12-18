"""
Modèle avec Features Temporelles
==================================

Ce fichier contient la configuration du modèle avec features temporelles.
Variante sans keywords critiques (détection purement statistique).
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
THRESHOLD_PERCENTILE = 90
THRESHOLD_VALUE = None  # Calculé lors de l'entraînement

# Configuration Drain
DRAIN_CONFIG = {
    'depth': 4,
    'sim_th': 0.4,
    'max_children': 100,
    'max_clusters': 0
}

# Configuration du vectorizer
VECTORIZER_CONFIG = {
    'max_features': 300,
    'token_pattern': r'\S+'
}

# Features temporelles (détection de bursts et pics d'erreurs)
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
    Crée un nouveau modèle avec features temporelles.
    
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
        'detection_method': 'temporal',
        'version': '.0.0',
        'features': {
            'temporal': TEMPORAL_FEATURES,
            'numeric': NUMERIC_FEATURES
        }
    }


def save_model(model_data, filepath='model_temporal.pkl'):
    """
    Sauvegarde le modèle au format pickle.
    
    Args:
        model_data (dict): Modèle à sauvegarder
        filepath (str): Chemin de destination
    """
    with open(filepath, 'wb') as f:
        pickle.dump(model_data, f)
    print(f"Modèle sauvegardé : {filepath}")


def load_model(filepath='model_temporal.pkl'):
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
    print("Configuration du Modèle avec Features Temporelles")
    print("=" * 70)
    print(f"\nIsolation Forest:")
    print(f"[INFO]  - Estimateurs : {ISOLATION_FOREST_CONFIG['n_estimators']}")
    print(f"[INFO]  - Contamination : {ISOLATION_FOREST_CONFIG['contamination']}")
    print(f"[INFO]  - Max samples : {ISOLATION_FOREST_CONFIG['max_samples']}")
    
    print(f"\nFeatures temporelles : {len(TEMPORAL_FEATURES)}")
    print(f"[INFO]  {', '.join(TEMPORAL_FEATURES)}")
    
    print(f"\nFeatures numériques : {len(NUMERIC_FEATURES)}")
    print(f"[INFO]  {', '.join(NUMERIC_FEATURES)}")
    
    print(f"\nSeuil de détection : Percentile {THRESHOLD_PERCENTILE}%")
    
    print(f"\nTotal features : 300 templates + 347 context + {len(NUMERIC_FEATURES)} numeric + {len(TEMPORAL_FEATURES)} temporal = 665")
    
    print("\n" + "=" * 70)
    print("Différence avec hybrid_model.py:")
    print("[INFO]  - PAS de keywords critiques (détection purement statistique)")
    print("[INFO]  - Focus sur les patterns temporels (bursts, pics)")
    print("=" * 70)
