#  Documentation Technique

Documentation complète du système de détection d'anomalies.

---

## 📁 Contenu

### . [ARCHITECTURE.md](./ARCHITECTURE.md)
**Architecture technique détaillée du système**

**Sections** :
- Vue d'ensemble de l'architecture
- Composants du système
- Pipeline de traitement
- Modèle de détection (Isolation Forest + Keywords + Temporal)
- Features engineering (6 features)
- API REST FastAPI
- Déploiement Docker
- Monitoring Prometheus/Grafana

**Audience** : Développeurs, Architectes

---

### . [HANDOVER.md](./HANDOVER.md)
**Guide de passation pour l'équipe de maintenance**

**Sections** :
- Responsabilités de l'équipe
- Connaissances requises
- Structure du code
- Workflows de développement
- Procédures de déploiement
- Maintenance et monitoring
- Troubleshooting
- Roadmap

**Audience** : Équipe de maintenance, DevOps

---

### . [README_PRODUCTION.md](./README_PRODUCTION.md)
**Guide de déploiement et opération en production**

**Sections** :
- Prérequis infrastructure
- Installation étape par étape
- Configuration (variables d'environnement)
- Monitoring et alerting
- Procédures opérationnelles
- Incident response
- Scalabilité
- Sécurité
- Backup et recovery

**Audience** : DevOps, SRE, Ops

---

### . [api_reference.md](./api_reference.md) *(à créer si nécessaire)*
**Référence complète de l'API REST**

**Sections** :
- Endpoints disponibles
- Schémas de requêtes/réponses
- Codes d'erreur
- Exemples d'utilisation
- Rate limiting
- Authentication (si applicable)

**Alternative** : Documentation Swagger interactive disponible à http://localhost:8080/docs

---

##  Guides par Rôle

### Pour Développeurs Backend
. **Commencez par** : [ARCHITECTURE.md](./ARCHITECTURE.md)
. **Ensuite** : Code source dans `../code_source/src/`
. **Tests** : `../tests/`
. **Notebook R&D** : `../RD_Notebook/ISO_avec_Drain.ipynb`

### Pour DevOps/SRE
. **Commencez par** : [README_PRODUCTION.md](./README_PRODUCTION.md)
. **Ensuite** : Docker dans `../deployment/`
. **Monitoring** : `../deployment/docker-compose-monitoring.yml`
. **Troubleshooting** : [HANDOVER.md](./HANDOVER.md)

### Pour Data Scientists
. **Commencez par** : `../RD_Notebook/ISO_avec_Drain.ipynb`
. **Ensuite** : `../modeles/` pour les modèles entraînés
. **Features** : [ARCHITECTURE.md](./ARCHITECTURE.md) section Feature Engineering
. **Métriques** : `../resultats_validation/README.md`

### Pour Chef de Projet
. **Commencez par** : `../PRESENTATION.md`
. **Ensuite** : `../CHECKLIST.md`
. **Résultats** : `../resultats_validation/README.md`
. **Passation** : [HANDOVER.md](./HANDOVER.md)

---

## 📖 Concepts Clés

### Isolation Forest
**Algorithme de détection d'anomalies non supervisé**

- Construit des arbres aléatoires sur les features
- Anomalies = points faciles à isoler (peu de splits)
- Score entre -1 (anomalie) et 1 (normal)
- Notre modèle : 300 estimateurs, contamination=0.05

**Référence** : Liu et al. (2008) - "Isolation Forest"

---

### Drain3
**Algorithme de log parsing pour extraire templates**

- Parse les logs en templates + variables
- Exemple : `"Error on line 42"` → `"Error on line <*>"`
- Groupement automatique de logs similaires
- Utilisé pour feature engineering (300 templates)

**Référence** : He et al. (2017) - "Drain: An Online Log Parsing"

---

### Feature Engineering
**662 features extraites par log** :

1. **Templates (300)** : One-hot encoding des 300 templates Drain les plus fréquents
2. **Contexte K8s (347)** : Encodage namespace + pod
3. **Numériques (8)** : Longueur, tokens, ratios, time...
4. **Temporelles (7)** : Rate 5min/15min/1h, std, burst_ratio, acceleration

---

### Scoring Multi-Modal
** méthodes combinées avec pondération** :

```python
final_score = (
    ml_score * 0.5 +           # Isolation Forest
    keyword_score * 0.0 +      # Domain knowledge
    temporal_score * 0.5 +     # Time patterns
    context_multiplier * 0.0   # Environment
)
```

**Seuils de détection** :
- `final_score ≥ 0.50` → Anomalie
- `final_score ≥ 0.85` → CRITICAL
- `0.70 ≤ final_score < 0.85` → HIGH
- `0.50 ≤ final_score < 0.70` → MEDIUM

---

### Keywords Critiques
** mots-clés métier avec pondération** :

| Niveau | Score | Mots-clés |
|--------|-------|-----------|
| **Critical** | .0 | FATAL, OOMKilled, Panic, Segmentation fault |
| **High** | 0.7 | ERROR, Exception, Failed, Timeout |
| **Medium** | 0. | WARN, Warning, Deprecated |

---

### Features Temporelles
**Détection de patterns temporels** :

- **rate_5min** : Erreurs/minute sur fenêtre 5min
- **rate_5min** : Erreurs/minute sur fenêtre 5min
- **rate_h** : Erreurs/minute sur fenêtre h
- **std_5min** : Écart-type (variabilité)
- **burst_ratio** : Ratio 5min/5min (détection burst)
- **acceleration** : Tendance (aggravation ou amélioration)

**Cold start** : Features à 0 au démarrage, s'activent après 5min

---

## 🔬 Métriques de Performance

### Métriques de Classification

| Métrique | Formule | Valeur Projet |
|----------|---------|---------------|
| **Recall** | TP / (TP + FN) | 75-85% |
| **Precision** | TP / (TP + FP) | 80%+ |
| **F-Score** |  * (P * R) / (P + R) | 0.77-0.8 |
| **Accuracy** | (TP + TN) / Total | 85%+ |

**Légende** :
- TP = True Positives (anomalies détectées)
- FP = False Positives (faux positifs)
- TN = True Negatives (normaux corrects)
- FN = False Negatives (anomalies manquées)

---

### Métriques de Performance

| Métrique | Cible | Mesuré |
|----------|-------|--------|
| **Latence P50** | <50ms | ~5ms |
| **Latence P95** | <00ms | ~8ms |
| **Latence P99** | <00ms | ~65ms |
| **Throughput** | 500 logs/s | 000 logs/s |

---

##  Architecture Technique

### Vue d'Ensemble

```
┌─────────────┐
│  Kubernetes │
│    Logs     │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Service (Port 8080)     │
├─────────────────────────────────────────┤
│  . Preprocessing (PII Redaction)       │
│  . Drain Parsing (Template Extract)   │
│  . Feature Engineering (6 features)  │
│  . Multi-Modal Scoring                 │
│     - Isolation Forest (5%)            │
│     - Keywords (0%)                    │
│     - Temporal (5%)                    │
│     - Context (0%)                     │
│  5. Severity Classification             │
│  6. Diagnostic + Actions                │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│        Response JSON                    │
├─────────────────────────────────────────┤
│  - is_anomaly: bool                     │
│  - confidence: float                    │
│  - severity: str                        │
│  - scores: dict                         │
│  - diagnostics: list                    │
│  - recommended_actions: list            │
│  - impact: str                          │
└─────────────────────────────────────────┘
```

---

### Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| **Langage** | Python | . |
| **API** | FastAPI | 0.0+ |
| **ML** | scikit-learn | .+ |
| **Log Parsing** | Drain | 0.9+ |
| **Validation** | Pydantic | .0+ |
| **Container** | Docker | 0.0+ |
| **Orchestration** | Docker Compose | .0+ |
| **Monitoring** | Prometheus | .0+ |
| **Dashboards** | Grafana | 9.0+ |

---

##  Configuration

### Variables d'Environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `MODEL_PATH` | Chemin modèle .pkl | `/app/modeles/hybrid_model.pkl` |
| `LOG_LEVEL` | Niveau de log | `INFO` |
| `API_PORT` | Port API | `8080` |
| `WORKERS` | Gunicorn workers | `` |
| `MAX_WORKERS` | Thread pool | `0` |
| `TIMEOUT` | Timeout requête | `0s` |

---

### Fichiers de Configuration

#### `config.yaml` (optionnel)
```yaml
model:
  path: "./modeles/hybrid_model.pkl"
  threshold: -0.05
  
scoring:
  weights:
    ml: 0.5
    keywords: 0.0
    temporal: 0.5
    context: 0.0
    
  thresholds:
    critical: 0.85
    high: 0.70
    medium: 0.50
```

---

##  Troubleshooting

### Problème : Latence élevée
**Symptômes** : Réponses >00ms

**Causes possibles** :
. Modèle trop lourd → Utiliser `model.pkl` (base) au lieu de `hybrid_model.pkl`
. Features temporelles coûteuses → Désactiver si pas nécessaire
. Trop de workers → Réduire à -

**Solution** :
```yaml
# docker-compose.yml
environment:
  - MODEL_PATH=/app/modeles/model.pkl
  - WORKERS=
```

---

### Problème : Trop de faux positifs
**Symptômes** : >0% de faux positifs

**Causes possibles** :
. Seuil trop bas
. Keywords trop sensibles
. Contexte production trop prioritaire

**Solution** :
```python
# Ajuster dans service.py
threshold_critical = 0.90  # au lieu de 0.85
threshold_high = 0.75      # au lieu de 0.70
```

---

### Problème : Anomalies manquées
**Symptômes** : Recall <70%

**Causes possibles** :
. Seuil trop haut
. Nouveaux patterns non appris
. Keywords manquants

**Solution** :
. Réentraîner modèle avec nouveaux logs
. Ajouter keywords spécifiques
. Baisser seuil détection

---

##  Références

### Papers
- Liu et al. (008) - "Isolation Forest" - IEEE ICDM
- He et al. (07) - "Drain: An Online Log Parsing Approach" - ICWS

### Documentation
- FastAPI : https://fastapi.tiangolo.com/
- scikit-learn : https://scikit-learn.org/
- Drain : https://github.com/logpai/Drain

### Standards
- Kubernetes Logging : https://kubernetes.io/docs/concepts/cluster-administration/logging/
- Prometheus Metrics : https://prometheus.io/docs/

---

## 🎓 Formation Recommandée

### Pour Maintenir le Système
. **Python avancé** ( jours)
. **FastAPI** ( jours)
. **Machine Learning** (5 jours)
. **Kubernetes** ( jours)
5. **Docker** ( jours)

### Pour Améliorer le Modèle
. **Anomaly Detection** (5 jours)
. **Feature Engineering** ( jours)
. **Model Tuning** ( jours)
. **Production ML** ( jours)

---

##  Checklist Documentation

Vérifiez que vous avez consulté :

- [ ] [ARCHITECTURE.md](./ARCHITECTURE.md) - Architecture système
- [ ] [HANDOVER.md](./HANDOVER.md) - Guide de passation
- [ ] [README_PRODUCTION.md](./README_PRODUCTION.md) - Déploiement prod
- [ ] API docs - http://localhost:8080/docs
- [ ] Code source - `../code_source/src/`
- [ ] Tests - `../tests/`
- [ ] Notebook R&D - `../RD_Notebook/`

---

 **Documentation complète et à jour** - Version .0 Production-Ready
