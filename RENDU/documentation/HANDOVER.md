# Guide de Passation - Projet Détection d'Anomalies Kubernetes

## Vue d'ensemble

Ce projet fournit un système de détection d'anomalies pour les logs Kubernetes basé sur Isolation Forest, Drain et des règles métier.

## Livrables

### . Code source
- **Pipeline principal** : `src/`, `Pipeline/`
- **Service API** : `src/service.py` (FastAPI)
- **Scripts** : `batch_detect.py`, `stream_logs.py`
- **Notebook R&D** : `ISO_avec_Drain.ipynb` (développement et analyse)

### . Modèles entraînés
- **Fichiers binaires** : `hybrid_model.pkl`, `model_temporal.pkl`, `model.pkl`
- **Configurations Python** :
  - `hybrid_model.py` (6 KB) - ISO + Keywords + Temporel
  - `model_temporal.py` (5 KB) - ISO + Temporel
  - `model.py` ( KB) - ISO seul
- **Documentation** : `modeles/README.md`
- **Contenu** : Isolation Forest + Drain + keywords + features temporelles + latence
- **Performance** : Recall ~75-85%, Precision ~80%+

### . Infrastructure
- **Docker** : `docker-compose.yml` pour déploiement complet
- **Monitoring** : Prometheus + Grafana (dossier `monitoring/`)
- **Tests** : `test_critical_errors.sh`, `test_monitoring.sh`

### . Documentation
- `README.md` - Vue d'ensemble
- `README_PRODUCTION.md` - Guide de déploiement
- `RESULTATS_TEST_COMPLET.md` - Performances validées
- `docs/architecture.md` - Architecture technique

## Architecture technique

### Pipeline de détection
```
Log brut  Preprocessing (PII)  Drain (templates)  Vectorisation
           Feature engineering (contexte, temporel, latence)
           Détection hybride (ISO Forest + Keywords)
           Post-processing (filtrage burst)
           Alerte / Enregistrement
```

### Features utilisées (662 total)
- Templates Drain : 300 features
- Contexte K8s : 347 features (namespace, pod)
- Numériques : 8 features (length, tokens, ratios, time)
- Temporelles : 7 features (rate_5min, burst_ratio, std, acceleration)

### Détection hybride
. **Isolation Forest** : Détection statistique (patterns rares)
. **Keywords** :  mots-clés critiques (ERROR, FATAL, CRASH, OOMKilled, etc.)
. **Logique** : Anomalie si ISO Forest OU keywords

## Déploiement

### Prérequis
- Docker & Docker Compose
- Python .+ (pour développement local)

### Lancement rapide
```bash
# Démarrer le service
docker-compose up -d

# Vérifier la santé
curl http://localhost:8080/health

# Tester
bash test_critical_errors.sh
```

### Validation
```bash
# Doit afficher 0/0 erreurs détectées
bash test_critical_errors.sh

# Test sur dataset complet
python batch_detect.py sample_logs/staging_sample.jsonl --output results.json
```

## Performances

### Métriques validées
- **Recall** : 75-85% (détecte la majorité des incidents)
- **Precision** : 80%+ (peu de faux positifs)
- **F-Score** : 0.77-0.8
- **Taux de faux positifs** : 5-0%
- **Latence de prédiction** : <00ms par log

### Garanties
- **00% de détection** des logs contenant les keywords critiques
- **0 faux positifs** sur logs normaux sans patterns suspects

## Points d'attention

### . Limites connues
- **Biais labels** : Les labels "has_error" sont créés avec keywords (biais circulaire)
- **Validation réelle** : Nécessite monitoring production + feedback incidents
- **Cold start** : Pas de features temporelles sur premiers logs d'un pod

### . Maintenance
- **Réentraînement** : Recommandé tous les -6 mois avec nouveaux logs
- **Keywords** : À adapter selon l'évolution des messages d'erreur
- **Seuil** : Ajustable via percentile (90% par défaut)

### . Monitoring
- **Dashboards Grafana** : Pré-configurés dans `monitoring/`
- **Métriques clés** :
  - Taux d'anomalies détectées
  - Latence de prédiction
  - Distribution des méthodes de détection
- **Alertes** : À configurer selon les SLAs

## Évolutions futures recommandées

### Court terme (- mois)
. **Feedback loop** : Système de validation manuelle des alertes
. **Métriques business** : Intégration des KPIs métier (revenus, trafic, etc.)
. **Auto-labeling** : Utilisation des incidents réels pour améliorer les labels

### Moyen terme (-6 mois)
. **Approche supervisée** : Random Forest avec labels validés
. **Features enrichies** : Logs applicatifs, métriques système, traces distribuées
. **Détection causale** : Corrélation entre événements

### Long terme (6- mois)
. **Deep Learning** : LSTM/Transformer pour séquences de logs
. **Détection proactive** : Prédiction d'incidents avant occurrence
. **Auto-remediation** : Actions automatiques sur incidents détectés

## Contacts et ressources

### Documentation externe
- Isolation Forest : https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- Drain : https://github.com/logpai/Drain
- FastAPI : https://fastapi.tiangolo.com/

### Notebooks de référence
- `ISO_avec_Drain.ipynb` : Développement complet du modèle

### Tests et validation
- `test_critical_errors.sh` : Validation erreurs critiques
- `batch_detect.py` : Analyse batch de datasets
- `compare_models_with_validation.py` : Comparaison de modèles

## Checklist de passation

### Pour le repreneur
- [ ] Lire `README_PRODUCTION.md`
- [ ] Lancer `docker-compose up` et vérifier `/health`
- [ ] Exécuter `test_critical_errors.sh` (doit afficher 0/0)
- [ ] Consulter le notebook `ISO_avec_Drain.ipynb`
- [ ] Tester sur un échantillon de logs réels
- [ ] Configurer les dashboards Grafana
- [ ] Définir les SLAs et alertes

### Pour le développeur sortant
- [ ] Code committé et pushé sur GitHub
- [ ] Modèles exportés ( `.pkl` +  `.py` lisibles + README.md)
- [ ] Documentation à jour
- [ ] Tests passants
- [ ] Dashboards Grafana fonctionnels
- [ ] Ce guide de passation complété

## Questions fréquentes

**Q: Pourquoi le recall n'est pas plus élevé ?**
R: C'est un modèle non-supervisé. Un recall de 75-85% est excellent sans labels. L'approche supervisée (phase ) permettra d'atteindre 90%+.

**Q: Comment réduire les faux positifs ?**
R: Ajuster le percentile du seuil (9095%) ou filtrer par burst_ratio. Attention au trade-off recall/precision.

**Q: Le modèle détecte-t-il les nouveaux types d'erreurs ?**
R: Oui pour l'Isolation Forest (patterns statistiques). Non pour les keywords (liste fixe à étendre).

**Q: Peut-on utiliser en temps réel ?**
R: Oui, latence <00ms. Le service FastAPI est conçu pour du streaming.

**Q: Comment gérer les pods éphémères ?**
R: Les features temporelles s'adaptent. Les premiers logs ont des valeurs par défaut (rate=0).

---

**Projet** : AI-driven Anomaly Detection for Kubernetes Logs
