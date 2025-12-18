# Système de Détection d'Anomalies pour Logs Kubernetes

Version 3.0.1 - Production Ready

---

## Table des Matières

1. [Démarrage Rapide](#démarrage-rapide)
2. [Vue d'Ensemble](#vue-densemble)
3. [Architecture](#architecture)
4. [Installation](#installation)
5. [Utilisation](#utilisation)
6. [Configuration](#configuration)
7. [Tests](#tests)
8. [Documentation](#documentation)

---

## Démarrage Rapide

```bash
# Démarrer le service
cd deployment && docker compose up -d

# Vérifier l'état
curl http://localhost:8080/health

# Tester avec vos logs
cd .. && python scripts_utilitaires/test_csv.py votre_fichier.csv
```

---

## Vue d'Ensemble

Système de détection d'anomalies temps réel pour logs Kubernetes utilisant une approche **hybride** combinant Machine Learning, règles métier et analyse temporelle.

### Approche Hybride

Le système combine 2 méthodes de détection complémentaires :

1. **Keywords Métier** - 22 mots-clés critiques Kubernetes (Precision ~85%)
2. **Isolation Forest** - Détection de patterns rares avec 664 features (Precision ~65%)

### Métriques de Performance (Estimations Réalistes)

| Métrique | Valeur | Intervalle | Notes |
|----------|--------|------------|-------|
| **Precision** | ~72% | 65-80% | ~28% de faux positifs |
| **Recall** | ~85% | 80-90% | ~15% d'anomalies manquées |
| **F1-Score** | ~78% | 72-84% | Équilibre precision/recall |
| **Taux FP** | ~0.5% | 0.3-1% | Sur l'ensemble des logs |
| **Détection Garantie** | 100% | - | Keywords critiques |

#### Répartition par méthode (sur 50K logs Wiremind)

| Méthode | Détections | Precision estimée |
|---------|------------|-------------------|
| Keywords seuls | 331 (35%) | ~85% |
| ISO Forest seuls | 614 (65%) | ~65% |
| **Total** | **945** | **~72%** |

### Limitations Connues

- **Faux Positifs (~28%)** : Logs avec "error" ou "failed" dans un contexte non-critique
- **Faux Négatifs (~15%)** : Anomalies silencieuses sans keywords explicites
- **ISO Forest** : Détecte des patterns rares qui ne sont pas toujours des anomalies

---

## Architecture

### Composants Principaux

```
┌─────────────────────────────────────────┐
│         Logs Kubernetes                 │
└──────────────┬──────────────────────────┘
               │
               v
┌─────────────────────────────────────────┐
│      API FastAPI (Port 8080)            │
├─────────────────────────────────────────┤
│  . Preprocessing (Drain)              │
│  . Feature Extraction (6 features)   │
│  . Multi-Modal Scoring                 │
│  . Classification & Severity           │
└──────────────┬──────────────────────────┘
               │
               v
┌─────────────────────────────────────────┐
│      Response JSON                      │
│  - Anomalie : oui/non                   │
│  - Confidence : 0-                     │
│  - Sévérité : critical/high/medium/low  │
│  - Scores détaillés                     │
│  - Actions recommandées                 │
└─────────────────────────────────────────┘
```

### Feature Engineering

Le système extrait **664 features** par log :

- **300 features** : Templates Drain (patterns de logs via CountVectorizer)
- **347 features** : Contexte Kubernetes (namespace, pod via OneHotEncoder)
- **10 features** : Métriques numériques (longueur, tokens, ratios, keywords)
- **7 features** : Patterns temporels (rate, burst, accélération)

### Modèle Machine Learning

- **Algorithme** : Isolation Forest (hybride avec Keywords)
- **Estimateurs** : 300 arbres
- **Features** : 664 (300 TF-IDF + 347 context + 17 numériques)
- **Threshold** : Calibré au percentile 90
- **Keywords** : 22 mots-clés critiques Kubernetes

---

## Installation

### Prérequis

- Docker et Docker Compose
- Python 3.9+
- 4GB RAM minimum
- Ports disponibles : 8080 (API), 9090 (Prometheus), 000 (Grafana)

### Installation Standard

```bash
# Cloner le repository
git clone <repository-url>
cd RENDU

# Démarrer avec Docker
cd deployment
docker compose up -d

# Vérifier le déploiement
curl http://localhost:8080/health
```

### Installation avec Monitoring

```bash
# Démarrer avec Prometheus et Grafana
cd deployment
docker compose -f docker-compose.yml up -d

# Accès aux interfaces
# - API : http://localhost:8080
# - Prometheus : http://localhost:9090
# - Grafana : http://localhost:3000 (admin/admin)
```

---

## Utilisation

### 1. API REST

#### Endpoint Principal : /predict

```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "message": "FATAL: OOMKilled - container memory limit exceeded",
    "namespace": "production",
    "pod": "api-server-xyz"
  }'
```

#### Réponse

```json
{
  "is_anomaly": true,
  "score": -0.05,
  "threshold": -0.03,
  "template": "fatal: oomkilled - container memory limit exceeded",
  "confidence": 0.95,
  "detection_method": "hybrid_both"
}
```

### 2. Test avec fichier CSV

```bash
# Tester avec vos logs Kubernetes
python deployment/test_csv.py votre_fichier.csv --max 5000

# Format de sortie :
# ┌──────────┬──────────┬─────────────────────────────────────┬──────────────────────┬────────────────────┐
# │ Priority │ Score    │ Log                                 │ Location             │ Method             │
# ├──────────┼──────────┼─────────────────────────────────────┼──────────────────────┼────────────────────┤
# │ 🔴 P1    │ -0.0500  │ FATAL: OOMKilled...                 │ prod/api-xyz         │ hybrid_both        │
# │ 🟠 P2    │ +0.0135  │ ERROR: Connection refused...        │ staging/db-01        │ keyword_detection  │
# │ 🟡 P3    │ -0.0300  │ Unusual pattern detected...         │ dev/worker-5         │ isolation_forest   │
# └──────────┴──────────┴─────────────────────────────────────┴──────────────────────┴────────────────────┘
```

**Niveaux de priorité** :
- 🔴 **P1** (Critical) : Détection hybride (keywords + ML) ou score très bas
- 🟠 **P2** (High) : Détection par mots-clés critiques
- 🟡 **P3** (Medium) : Détection par Isolation Forest uniquement
- 🟢 **P4** (Low) : Score proche du seuil
- ⚪ **P5** (Info) : Informationnel
}
```

### . Scripts Utilitaires

#### Test sur CSV

```bash
python scripts_utilitaires/test_csv.py logs.csv
```

Format CSV requis :
```csv
message,namespace,pod
"ERROR: Connection timeout",production,api-
"INFO: Request completed",production,api-
```

#### Traitement Batch

```bash
python scripts_utilitaires/batch_detect.py \
  --input logs.csv \
  --output results.json \
  --batch-size 000
```

#### Simulation Streaming

```bash
python scripts_utilitaires/stream_logs.py \
  --source logs.csv \
  --rate 0 \
  --duration 60
```

### . Documentation API Interactive

Accédez à la documentation Swagger : http://localhost:8080/docs

---

## Configuration

### Variables d'Environnement

```bash
# Modèle à utiliser
MODEL_PATH=/app/modeles/hybrid_model.pkl

# Configuration API
API_PORT=8080
LOG_LEVEL=INFO

# Performance
WORKERS=
MAX_WORKERS=0
TIMEOUT=0
```

### Seuils de Détection

Modifiables dans `code_source/src/service.py` :

```python
# Seuil de détection globale
ANOMALY_THRESHOLD = 0.50

# Seuils de sévérité
SEVERITY_THRESHOLDS = {
    'critical': 0.85,
    'high': 0.70,
    'medium': 0.50
}

# Poids des scores
SCORE_WEIGHTS = {
    'ml': 0.5,
    'keywords': 0.0,
    'temporal': 0.5,
    'context': 0.0
}
```

---

## Tests

### Tests Automatisés

```bash
# Tests complets
cd tests
./test_complete.sh

# Tests erreurs critiques
./test_critical_errors.sh

# Tests unitaires
pytest test_service.py test_model.py
```

### Validation Manuelle

```bash
# Test health check
curl http://localhost:8080/health

# Test prediction simple
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message":"ERROR: test","namespace":"default","pod":"test-"}'

# Vérifier les métriques
curl http://localhost:8080/metrics
```

---

## Documentation

### Structure de la Documentation

```
RENDU/
├── INDEX.md                          # Ce fichier
├── GUIDE_UTILISATION.md              # Guide rapide
├── README.md                         # Documentation détaillée
│
├── code_source/
│   ├── src/                          # Code source commenté
│   └── README.md
│
├── documentation/
│   ├── ARCHITECTURE.md               # Architecture technique
│   ├── HANDOVER.md                   # Guide de passation
│   └── README_PRODUCTION.md          # Déploiement production
│
├── modeles/
│   └── README.md                     # Documentation des modèles
│
└── RD_Notebook/
    ├── ISO_avec_Drain.ipynb         # Notebook de recherche
    └── README.md
```

### Guides par Profil

#### Développeurs
. Lire `documentation/ARCHITECTURE.md`
. Explorer `code_source/src/`
. Consulter `RD_Notebook/ISO_avec_Drain.ipynb`

#### DevOps/SRE
. Lire `documentation/README_PRODUCTION.md`
. Configurer `deployment/docker-compose.yml`
. Vérifier `tests/test_complete.sh`

#### Data Scientists
. Ouvrir `RD_Notebook/ISO_avec_Drain.ipynb`
. Analyser `modeles/README.md`
. Lire `documentation/ARCHITECTURE.md` (section Features)

---

## Cas d'Usage

### Erreurs Kubernetes Critiques

Le système détecte automatiquement :

- **OOMKilled** : Dépassement mémoire
- **CrashLoopBackOff** : Redémarrages en boucle
- **ImagePullBackOff** : Image non trouvée
- **Segmentation Fault** : Erreur mémoire application
- **Panic** : Erreur fatale runtime

### Patterns Anormaux

Détection via Machine Learning de :

- Patterns inhabituels non répertoriés
- Comportements statistiquement anormaux
- Nouveaux types d'erreurs

### Bursts d'Erreurs

Détection temporelle de :

- Pics soudains d'erreurs similaires
- Accélération du taux d'erreur
- Patterns temporels anormaux

---

## Métriques et Monitoring

### Métriques Prometheus Exposées

```
# Nombre total de prédictions
anomaly_detector_predictions_total

# Nombre d'anomalies détectées
anomaly_detector_anomalies_detected_total

# Durée des prédictions
anomaly_detector_prediction_duration_seconds

# Temps de chargement du modèle
anomaly_detector_model_load_time_seconds
```

### Dashboards Grafana

Dashboards pré-configurés disponibles :

. **Vue d'ensemble** : Métriques globales du système
. **Détections** : Anomalies par namespace, pod, sévérité
. **Performance** : Latence, throughput, erreurs
. **Santé** : CPU, mémoire, disponibilité

---

## Dépannage

### Service ne démarre pas

```bash
# Vérifier les logs
docker compose logs -f

# Vérifier les ports
lsof -i :8080

# Redémarrer proprement
docker compose down
docker compose up -d
```

### Latence élevée

- Réduire `WORKERS` dans les variables d'environnement
- Utiliser le modèle de base au lieu du modèle hybride
- Désactiver les features temporelles si non nécessaires

### Trop de faux positifs

- Augmenter `ANOMALY_THRESHOLD` (ex: 0.60 au lieu de 0.50)
- Ajuster les poids dans `SCORE_WEIGHTS`
- Affiner les seuils de sévérité

---

## Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Runtime | Python | . |
| API | FastAPI | 0.0+ |
| ML | scikit-learn | .+ |
| Log Parsing | Drain | 0.9+ |
| Validation | Pydantic | .0+ |
| Container | Docker | 0.0+ |
| Orchestration | Docker Compose | .0+ |
| Monitoring | Prometheus | .0+ |
| Dashboards | Grafana | 9.0+ |

---

## Maintenance

### Réentraînement du Modèle

```bash
# Exporter nouveaux logs
kubectl logs -n production --all-containers > new_logs.txt

# Relancer le notebook R&D
jupyter notebook RD_Notebook/ISO_avec_Drain.ipynb

# Remplacer le modèle
cp new_model.pkl modeles/hybrid_model.pkl

# Redémarrer le service
docker compose restart
```

### Ajout de Keywords

Modifier `code_source/src/service.py` :

```python
CRITICAL_KEYWORDS = {
    'fatal', 'oomkilled', 'panic', 'segmentation fault',
    # Ajouter vos keywords ici
    'nouveaumotcle': .0
}
```

---

## Livrables

### Code Source
- API FastAPI complète et documentée
-  modèles ML entraînés
- Scripts de preprocessing et feature extraction
- Tests unitaires et intégration

### Déploiement
- Dockerfile optimisé (build 0s)
- docker-compose.yml avec healthcheck
- Configuration monitoring Prometheus/Grafana
- Scripts de déploiement

### Documentation
- Guide d'architecture technique
- Guide de passation équipe
- Guide de déploiement production
- Documentation API Swagger
- Notebook R&D complet

### Validation
- Tests automatisés (00% passent)
- Résultats de validation
- Métriques de performance

---

## Support

### Documentation API
- Swagger UI : http://localhost:8080/docs
- Health Check : http://localhost:8080/health
- Métriques : http://localhost:8080/metrics

### Fichiers de Support
- `documentation/ARCHITECTURE.md` : Architecture détaillée
- `documentation/HANDOVER.md` : Guide de passation
- `documentation/README_PRODUCTION.md` : Guide production
- `RD_Notebook/ISO_avec_Drain.ipynb` : Recherche et développement

---

## Licence

Propriétaire - Tous droits réservés
