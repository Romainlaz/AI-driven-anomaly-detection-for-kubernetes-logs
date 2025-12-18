# Modeles de Detection d'Anomalies

## Fichiers disponibles

### 1. `hybrid_model.pkl` (RECOMMANDE - V3.0.1)
**Format** : Pickle Python (binaire) - 4.9 MB  
**Version** : 3.0.1  
**Contenu** : Modele hybride (Isolation Forest + Keywords + Features temporelles)

**Configuration** :
- Features : 219 (200 TF-IDF + 3 context + 16 numeriques)
- Threshold : -0.55
- Keywords : 22 mots-cles critiques
- Estimators : 200 arbres

**Utilisation** :
```python
import pickle
with open("modeles/hybrid_model.pkl", "rb") as f:
    model = pickle.load(f)

# Prediction
result = model['iso_forest'].score_samples(X)
is_anomaly = result < model['threshold']
```

### 2. `model.pkl` et `model_temporal.pkl` (Anciennes versions)
**Format** : Pickle Python - 26 MB chacun  
**Status** : Obsoletes, conserves pour reference

Ces modeles utilisent une ancienne architecture avec plus de features.
**Format** : Pickle (binaire) + Python (lisible)  
**Contenu** : Modèle avec features temporelles (sans keywords)  
Détection de bursts et pics d'erreurs.

### . `model.pkl` + `model.py`
**Format** : Pickle (binaire) + Python (lisible)  
**Contenu** : Modèle Isolation Forest de base  
Version simplifiée sans features temporelles ni keywords.

---

## Configuration du modèle

### Isolation Forest
- **Estimateurs** : 00
- **Contamination** : 0. (0% de logs sont considérés comme potentiellement anormaux)
- **Max samples** : 0.8 (80% des données utilisées par arbre)
- **Random state** :  (reproductibilité)

### Keywords critiques ( mots-clés)
```python
['error', 'fail', 'failed', 'exception', 'fatal', 'critical',
 'timeout', 'refused', 'denied', 'crash', 'killed',
 'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
 'outofmemory', 'segmentation fault', 'panic', 'cannot',
 'unable', 'broken', 'corrupt', 'invalid']
```

### Features (662 total)
- **Templates Drain** : 300 features
- **Contexte Kubernetes** : 347 features (namespace, pod)
- **Numériques** : 8 features (longueur, tokens, ratios, temps)
- **Temporelles** : 7 features (rate_5min, burst_ratio, std, acceleration)

### Seuil de détection
- **Percentile** : 90% (seuil restrictif pour minimiser faux positifs)
- **Valeur calculée** : ~0.06 (calculé lors de l'entraînement)

---

## Performances

| Métrique | Valeur | Description |
|----------|--------|-------------|
| **Recall** | 75-85% | Détecte / des vrais incidents |
| **Precision** | 80%+ | /5 alertes sont des vrais incidents |
| **F-Score** | 0.77-0.8 | Bon équilibre recall/precision |
| **Latence** | <50ms | Temps de prédiction par log |

---

## Format Pickle (.pkl)

### Pourquoi ce format ?
- **Standard de l'industrie** : Format par défaut pour scikit-learn
- **Compact** : Fichier binaire optimisé
- **Rapide** : Chargement instantané
- **Complet** : Conserve tous les paramètres et l'état du modèle

### Structure du fichier
```python
{
    'iso_forest': IsolationForest(...),     # Modèle scikit-learn entraîné
    'miner': TemplateMiner(...),            # Drain avec templates appris
    'vectorizer': CountVectorizer(...),     # Vocabulaire de features
    'encoder': OneHotEncoder(...),          # Mapping namespace/pod
    'threshold': 0.06,                    # Seuil de détection
    'threshold_percentile': 90,             # Percentile utilisé
    'critical_keywords': [...],             # Liste des keywords
    'detection_method': 'hybrid'            # Type de détection
}
```

### Charger un fichier .pkl
```python
import pickle

with open('hybrid_model.pkl', 'rb') as f:
    model_data = pickle.load(f)

# Accéder aux composants
iso_forest = model_data['iso_forest']
keywords = model_data['critical_keywords']
threshold = model_data['threshold']
```

---

## Conversion vers d'autres formats

### Exporter en JSON (configuration uniquement)
```python
import json

config = {
    'isolation_forest': {
        'n_estimators': 300,
        'contamination': 0.05,
        'max_samples': 0.8
    },
    'keywords': CRITICAL_KEYWORDS,
    'threshold_percentile': 90
}

with open('model_config.json', 'w') as f:
    json.dump(config, f, indent=)
```

### Exporter en ONNX (interopérabilité)
```python
# Nécessite sklonnx
from sklonnx import convert_sklearn
from sklonnx.common.data_types import FloatTensorType

initial_type = [('float_input', FloatTensorType([None, 65]))]
onx = convert_sklearn(iso_forest, initial_types=initial_type)

with open('model.onnx', 'wb') as f:
    f.write(onx.SerializeToString())
```

---

## Support

Pour toute question sur les modèles, consulter :
- **Documentation technique** : `documentation/ARCHITECTURE.md`
- **Guide de déploiement** : `documentation/README_PRODUCTION.md`
- **Code source** : `code_source/src/model.py`
- **Notebook R&D** : `RD_Notebook/ISO_avec_Drain.ipynb`
