# Système de Détection d'Anomalies pour Logs Kubernetes

Version 3.0.1 Production-Ready

## Démarrage Rapide

```bash
# 1. Démarrer le système
cd deployment && docker compose up -d

# 2. Vérifier l'état
curl http://localhost:8080/health

# 3. Tester avec vos logs
python scripts_utilitaires/test_csv.py votre_fichier.csv
```

Documentation complète : Voir README.md

## Vue d'Ensemble

Système de détection d'anomalies temps réel utilisant une approche **hybride** combinant :

- **Keywords Métier** : 22 mots-clés critiques Kubernetes (Precision ~85%)
- **Isolation Forest** : Détection de patterns rares avec 219 features (Precision ~65%)
- **Features Temporelles** : rate_5min, burst_ratio, acceleration (7 features)

### Métriques de Performance (Estimations Réalistes)

| Métrique | Valeur | Interprétation |
|----------|--------|----------------|
| **Precision** | ~72% | 28% de faux positifs |
| **Recall** | ~85% | 15% d'anomalies manquées |
| **F1-Score** | ~78% | Équilibre acceptable |
| **Taux FP** | ~0.5% | Sur l'ensemble des logs |
| **Détection Garantie** | 100% | Keywords critiques |

## Structure du Projet

```
RENDU/
├── INDEX.md                     # Ce fichier (point d'entrée)
├── README.md                    # Documentation principale
├── ANALYSE_PROJET.md            #  Analyse complète du projet (viabilité, limites)
│
├── .github/workflows/           #  CI/CD
│   └── ci.yml                   # Pipeline GitHub Actions
│
├── RD_Notebook/                 # 🔬 Recherche & Développement
│   ├── ISO_avec_Drain.ipynb    # Notebook d'expérimentation
│   └── README.md
│
├── code_source/                 #  Code source production
│   ├── src/                     # Services et modèles
│   │   ├── model.py             # Détecteur d'anomalies (AnomalyDetector)
│   │   ├── service.py           # API FastAPI + HybridPredictor
│   │   └── cli.py               # Interface CLI (train, serve, score)
│   ├── tests/                   # Tests unitaires
│   ├── scripts/                 # Scripts utilitaires
│   └── requirements.txt         # Dépendances Python
│
├── modeles/                     # 🧠 Modèles ML entraînés
│   ├── hybrid_model.pkl         # Modèle V3.0.1 (219 features, threshold=-0.55)
│   ├── model.pkl                # Modèle de base
│   └── model_temporal.pkl       # Modèle avec features temporelles
│
├── deployment/                  #  Configuration déploiement
│   ├── docker-compose.yml       # Stack complète (API + Prometheus + Grafana)
│   ├── Dockerfile               # Image de production
│   ├── prometheus.yml           # Configuration Prometheus
│   ├── grafana-provisioning/    # Dashboards et datasources Grafana
│   └── charts/                  #  Helm Chart Kubernetes
│       └── anomaly-detector/    # Chart complet avec ServiceMonitor, HPA
│
├── benchmarks/                  # 📊 Tests de performance et métriques
│   ├── METRIQUES.md             # Documentation des métriques
│   ├── metrics_credibles.json   # Métriques estimées réalistes
│   ├── load_test.py             # Script de charge
│   └── calculate_metrics.py     # Calcul des métriques
│
├── tests/                       #  Tests automatisés
│   ├── test_model.py            # Tests du modèle
│   ├── test_service.py          # Tests de l'API
│   └── test_*.sh                # Tests d'intégration shell
│
├── scripts_utilitaires/         # 🛠 Scripts d'utilisation
│   ├── demo.py                  # Démonstration interactive
│   ├── test_csv.py              # Test sur fichier CSV
│   ├── batch_detect.py          # Détection batch avec rapport
│   └── stream_logs.py           # Ingestion streaming
│
├── donnees_test/                # 📂 Données de test
│   ├── sample_100.csv           # Échantillon 00 logs
│   └── README.md
│
├── resultats_validation/        #  Résultats de validation
│
└── documentation/               #  Documentation technique
    ├── ARCHITECTURE.md          # Architecture système détaillée
    ├── HANDOVER.md              # Guide de passation
    ├── README_PRODUCTION.md     # Guide déploiement production
    ├── runbook.md               # Guide opérationnel SRE
    └── adr/                     # Architecture Decision Records
        ├── 001-isolation-forest-threshold.md
        └── 002-drain-template-extraction.md
```

## Utilisation

### . Démarrage

```bash
cd deployment
docker compose up -d
```

### . Test API

```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "message": "ERROR: Database connection failed",
    "namespace": "production",
    "pod": "api-server-"
  }'
```

### . Test Batch

```bash
python scripts_utilitaires/test_csv.py logs.csv
```

## Documentation

- **README.md** : Documentation principale
- **GUIDE_UTILISATION.md** : Guide démarrage rapide
- **documentation/ARCHITECTURE.md** : Architecture technique
- **documentation/HANDOVER.md** : Guide de passation
- **documentation/README_PRODUCTION.md** : Déploiement production

## Support

- API Swagger : http://localhost:8080/docs
- Health Check : http://localhost:8080/health
- Métriques : http://localhost:8080/metrics
