# Architecture Technique - Détection d'Anomalies Logs Kubernetes

## Vue d'ensemble

Ce document détaille l'architecture technique du système de détection d'anomalies développé pour Wiremind.

---

## Architecture Globale

```

                     Logs Kubernetes (source)                     

                         
                         

                    API FastAPI (port 8080)                       
                
   Preprocessing Feature Eng.     Detection             
    + Redaction     (65 feat.)      Hybride              
                

                         
                         

                    Métriques Prometheus                          
  anomaly_detector_predictions_total                              
  anomaly_detector_anomalies_detected_total                       
  anomaly_detector_prediction_duration_seconds                    

                         
                         

                    Dashboards Grafana                            
  - Détections temps réel                                         
  - Performance du modèle                                         
  - Santé du système                                              

```

---

## Pipeline de Détection

### . Preprocessing (Entrée  Nettoyage)

```python
Input: {
    "message": "ERROR: Connection to db-.prod.wiremind.io:5 failed",
    "namespace": "production",
    "pod": "api-backend-"
}

# Étapes:
. Redaction PII:
   - Emails  <EMAIL>
   - IPs  <IP>
   - Chemins  <PATH>
   - Nombres  <NUM>

Output: "error: connection to <PATH>:<NUM> failed"
```

**Code**:
```python
def redact(message):
    message = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', 
                     "<EMAIL>", str(message))
    message = re.sub(r'\b\d{,}(?:\.\d{,}){}\b', "<IP>", message)
    message = re.sub(r'\b\d+\b', "<NUM>", message)
    message = re.sub(r'/[A-Za-z0-9_\-\.]+', "<PATH>", message)
    return message.lower()
```

---

### . Template Extraction (Drain)

```
Input: "error: connection to <PATH>:<NUM> failed"

Drain  Template: "error: connection to <*> failed"

# Drain crée un arbre de parsing qui regroupe
# les logs similaires en templates
```

**Configuration Drain**:
```python
config = TemplateMinerConfig()
miner = TemplateMiner(config=config)

# Paramètres par défaut:
# - max_depth = 
# - similarity_threshold = 0.
# - max_children = 00
```

---

### 2. Feature Engineering (664 features)

#### 2.1 Templates (300 features)
```python
# CountVectorizer sur les templates Drain
vect_templates = CountVectorizer(max_features=300)
X_templates = vect_templates.fit_transform(templates)

# Exemple:
# Template: "error: connection to <*> failed"
#  Vector: [0, 0, 1, 0, ..., 0]  (300 dimensions)
```

#### 2.2 Contexte Kubernetes (347 features)
```python
# OneHotEncoder sur namespace + pod
encoder = OneHotEncoder(sparse_output=True, handle_unknown="ignore")
X_context = encoder.fit_transform(df[['kubernetes.namespace_name', 'kubernetes.pod_name']])

# Exemple:
# namespace=production, pod=api-xyz
#  Vector: [0, 1, 0, ..., 1, 0]  (347 dimensions)
```

#### 2.3 Features numériques (10 features)
```python
features = [
    length,           # Longueur du message
    num_tokens,       # Nombre de tokens
    digit_ratio,      # Ratio chiffres
    upper_ratio,      # Ratio majuscules
    special_ratio,    # Ratio caractères spéciaux
    avg_token_length, # Longueur moyenne des tokens
    has_error_kw,     # Présence de mot-clé d'erreur (0/1)
    is_error_level,   # Niveau ERROR/FATAL/CRITICAL (0/1)
    is_warn_level,    # Niveau WARN (0/1)
    has_traceback     # Présence de traceback/exception (0/1)
]
```

#### 2.4 Features temporelles (7 features)
```python
temporal_features = [
    rate_5min,        # Taux erreurs 5 dernières minutes
    rate_15min,       # Taux erreurs 15 dernières minutes
    rate_1h,          # Taux erreurs dernière heure
    std_5min,         # Écart-type 5 min
    std_15min,        # Écart-type 15 min
    acceleration,     # rate_5min - rate_15min
    burst_ratio       # rate_5min / (rate_1h + epsilon)
]
```

**Calcul des features temporelles**:
```python
# Agrégation par pod + fenêtre temporelle glissante
from collections import deque

windows = {
    '5min': deque(maxlen=5),
    '15min': deque(maxlen=15),
    '1h': deque(maxlen=60)
}

# Calcul des taux et écarts-types
rate_5min = sum(windows['5min']) / max(len(windows['5min']), 1)
std_5min = np.std(windows['5min']) if len(windows['5min']) > 1 else 0
```

#### 2.5 Assemblage final
```python
from scipy.sparse import hstack

X = hstack([
    X_templates,      # 300 features
    X_context,        # 347 features
    X_numeric,        # 10 features
    X_temporal        # 7 features
])
# Total: 300 + 347 + 10 + 7 = 664 features
```

---

### 3. Détection Hybride

#### 3.1 Isolation Forest (Détection statistique)

```python
iso = IsolationForest(
    n_estimators=300,      # Nombre d'arbres
    contamination=0.05,    # % anomalies attendu
    max_samples=0.8,       # Échantillonnage
    bootstrap=True,
    random_state=42
)

# Entraînement sur logs NORMAUX uniquement
iso.fit(X_train_normal)

# Prédiction (score d'anomalie)
scores = -iso.decision_function(X_test)

# Seuil optimisé (percentile 90%)
threshold = np.percentile(scores, 90)
y_pred_iso = (scores >= threshold).astype(int)
```

**Fonctionnement Isolation Forest**:
1. Créer 300 arbres aléatoires
2. Pour chaque log, calculer la profondeur moyenne dans les arbres
3. Anomalie = log isolé rapidement (faible profondeur)

#### . Keywords critiques (Règles)

```python
CRITICAL_KEYWORDS = [
    'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
    'timeout', 'refused', 'denied', 'crash', 'killed',
    'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
    'outofmemory', 'segmentation fault', 'panic', 'cannot',
    'unable', 'broken', 'corrupt', 'invalid'
]

def has_critical_keyword(message):
    msg_lower = message.lower()
    return any(keyword in msg_lower for keyword in CRITICAL_KEYWORDS)

y_pred_kw = messages.apply(has_critical_keyword).astype(int)
```

#### . Détection hybride (OR logic)

```python
# Anomalie si ISO Forest OU Keyword détecté
y_pred_hybrid = (y_pred_iso | y_pred_kw).astype(int)

# Confiance:
# - Keyword: confiance = 0.90 (erreur évidente)
# - ISO seul: confiance = score / threshold
```

---

## Modèle Exporté

**Note** : Les configurations complètes sont disponibles en Python lisible :
- `modeles/hybrid_model.py` - Modèle hybride avec keywords
- `modeles/model_temporal.py` - Modèle avec features temporelles
- `modeles/model.py` - Modèle Isolation Forest de base

### Structure du pickle

```python
model_data = {
    'iso_forest': IsolationForest(...),      # Modèle scikit-learn
    'miner': TemplateMiner(...),             # Drain pré-entraîné
    'vectorizer': CountVectorizer(...),      # Vectorisation templates
    'encoder': OneHotEncoder(...),           # Encodage contexte K8s
    'threshold': 0.,                     # Seuil optimisé
    'threshold_percentile': 90,              # Percentile utilisé
    'critical_keywords': [...],              # Liste keywords
    'detection_method': 'hybrid'             # Méthode de détection
}
```

### Chargement et utilisation

```python
import pickle

# Charger le modèle
with open('hybrid_model.pkl', 'rb') as f:
    model_data = pickle.load(f)

iso = model_data['iso_forest']
miner = model_data['miner']
threshold = model_data['threshold']
keywords = model_data['critical_keywords']

# Prédire sur nouveau log
def predict(log):
    # . Preprocessing
    clean_msg = redact(log['message'])
    
    # . Template extraction
    template = miner.add_log_message(clean_msg)['template_mined']
    
    # . Feature engineering
    X = build_features(template, log['namespace'], log['pod'], ...)
    
    # . Détection hybride
    score_iso = -iso.decision_function(X)[0]
    is_anomaly_iso = score_iso >= threshold
    has_keyword = any(kw in clean_msg for kw in keywords)
    
    return {
        'is_anomaly': is_anomaly_iso or has_keyword,
        'method': 'keyword' if has_keyword else 'iso_forest',
        'confidence': 0.90 if has_keyword else score_iso / threshold
    }
```

---

## API FastAPI

### Endpoints

#### 1. `/health` - Health check
```bash
GET /health
Response: {"status": "healthy", "model_loaded": true}
```

#### 2. `/predict` - Détection d'anomalie
```bash
POST /predict
Content-Type: application/json

Body: {
    "message": "ERROR: Connection refused to database",
    "namespace": "production",
    "pod": "api-server-xyz",
    "timestamp": "2025-12-18T10:00:00Z"  # optionnel
}

Response: {
    "is_anomaly": true,
    "score": 0.0135,
    "threshold": -0.05,
    "template": "error: connection refused to database",
    "confidence": 0.90,
    "detection_method": "keyword_detection"
}
```

#### 3. `/metrics` - Métriques Prometheus
```bash
GET /metrics
Response: # Métriques Prometheus au format texte
anomalies_detected_total 254
predictions_total 5000
prediction_latency_seconds_bucket{le="0.1"} 4950
```

#### 4. `/ready` - Readiness probe
```bash
GET /ready
Response: {"status": "ready"}
```

### Format de sortie pour test_csv.py

Le script `deployment/test_csv.py` affiche les anomalies avec le format suivant :

```
┌──────────┬──────────┬─────────────────────────────────────┬──────────────────────┬────────────────────┐
│ Priority │ Score    │ Log                                 │ Location             │ Method             │
├──────────┼──────────┼─────────────────────────────────────┼──────────────────────┼────────────────────┤
│ 🔴 P1    │ -0.0500  │ FATAL: OOMKilled container api...   │ prod/api-xyz         │ hybrid_both        │
│ 🟠 P2    │ +0.0135  │ ERROR: Connection refused...        │ staging/db-01        │ keyword_detection  │
│ 🟡 P3    │ -0.0300  │ Unusual pattern detected...         │ dev/worker-5         │ isolation_forest   │
└──────────┴──────────┴─────────────────────────────────────┴──────────────────────┴────────────────────┘
```

**Niveaux de priorité** :
- 🔴 **P1** (Critical) : hybrid_both OU score < -0.1
- 🟠 **P2** (High) : keyword_detection
- 🟡 **P3** (Medium) : isolation_forest
- 🟢 **P4** (Low) : score proche du threshold
- ⚪ **P5** (Info) : autres

### Fichier JSON de résultats

Les résultats sont sauvegardés avec le format :

```json
{
  "summary": {
    "total_logs": 5000,
    "anomalies_count": 254,
    "anomaly_rate": 5.08,
    "detection_methods": {
      "keyword_detection": 200,
      "isolation_forest": 30,
      "hybrid_both": 24
    }
  },
  "anomalies": [
    {
      "priority": 2,
      "priority_label": "P2",
      "score": 0.0135,
      "log": "ERROR: Connection refused...",
      "location": {
        "namespace": "production",
        "pod": "api-server-xyz"
      },
      "detection_method": "keyword_detection",
      "confidence": 0.90,
      "template": "error: connection refused..."
    }
  ]
}
```

#### . `/metrics` - Métriques Prometheus
```bash
GET /metrics
Response: (format Prometheus)
# HELP anomaly_detector_predictions_total Total predictions
# TYPE anomaly_detector_predictions_total counter
anomaly_detector_predictions_total 
...
```

---

## Métriques et Monitoring

### Métriques Prometheus exposées

```python
# Compteurs
anomaly_detector_predictions_total         # Nb total prédictions
anomaly_detector_anomalies_detected_total  # Nb anomalies détectées
anomaly_detector_method_iso_total          # Détections ISO Forest
anomaly_detector_method_keyword_total      # Détections keywords

# Histogrammes
anomaly_detector_prediction_duration_seconds  # Latence prédiction
anomaly_detector_confidence_score             # Distribution confiance

# Gauges
anomaly_detector_model_load_time_seconds   # Temps chargement modèle
anomaly_detector_templates_count           # Nb templates Drain
```

### Dashboards Grafana

#### Dashboard : Détections
- Graphe temps réel: anomalies détectées par minute
- Répartition: ISO vs Keywords
- Top 0 namespaces avec anomalies
- Top 0 templates d'anomalies

#### Dashboard : Performance
- Latence p50, p95, p99
- Throughput (prédictions/seconde)
- Confiance moyenne des détections
- Taux d'erreurs API

#### Dashboard : Santé système
- CPU/RAM service
- Charge réseau
- Erreurs logs
- Uptime

---

## Déploiement Docker

### Architecture containers

```yaml
services:
  anomaly-detector:
    image: anomaly-detector:latest
    ports: ["8080:8080"]
    volumes: ["./model.pkl:/app/model.pkl"]
    
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]
    
  grafana:
    image: grafana/grafana:latest
    ports: ["000:000"]
    volumes: ["./dashboards:/etc/grafana/provisioning/dashboards"]
```

### Ressources requises

| Service | CPU | RAM | Disk |
|---------|-----|-----|------|
| anomaly-detector | - cores | - GB |  GB |
| prometheus | 0.5 core | - GB | 0 GB |
| grafana | 0.5 core | 5 MB |  GB |
| **Total** | **- cores** | **-7 GB** | ** GB** |

---

## Performance et Scalabilité

### Latence
- Prédiction single: **0-50ms**
- Prédiction batch (00 logs): **00-00ms**
- P95: <00ms
- P99: <00ms

### Throughput
- **00-00 logs/seconde** (single instance)
- Scalable horizontalement (stateless)

### Optimisations possibles
. Caching des templates Drain fréquents
. Batch processing pour features temporelles
. GPU pour Isolation Forest (optionnel)
. Compression du modèle (pickle  joblib)

---

## Limitations Connues

### . Nouveaux patterns
- ISO Forest peut mal performer sur patterns jamais vus
- Solution: Réentraînement périodique (mensuel)

### . Faux positifs
- 5-0% de faux positifs attendus
- Solution: Feedback loop + tuning seuil dynamique

### . Scalabilité
- Limite ~00 logs/sec par instance
- Solution: Load balancing + auto-scaling

### . Cold start
- Chargement modèle: - secondes
- Solution: Pre-warming + health checks

---

## Évolutions Futures

### Phase  (Court terme)
- Feedback loop pour réduire faux positifs
- Enrichissement contexte (service, version)
- Alerting avancé (PagerDuty, Slack)

### Phase  (Moyen terme)
- Clustering d'anomalies similaires
- Root cause analysis automatique
- Prédiction proactive (avant incident)

### Phase  (Long terme)
- Deep learning (transformers pour logs)
- Multi-modal (logs + métriques + traces)
- Auto-remediation sur incidents connus

---

## Références Techniques

### Librairies utilisées
- **scikit-learn .+** : Isolation Forest
- **drain 0.9+** : Template extraction
- **FastAPI 0.0+** : API REST
- **prometheus-client** : Métriques
- **pandas, numpy** : Manipulation données

### Papers de référence
- Isolation Forest: Liu et al. (008)
- Drain: He et al. (07)
- Log anomaly detection: Survey (0)

### Standards
- OpenMetrics pour Prometheus
- JSON pour API
- Semantic versioning pour releases
