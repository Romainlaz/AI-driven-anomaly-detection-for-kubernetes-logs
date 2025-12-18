# Runbook - Anomaly Detection Service

## Déploiement

### Prérequis
- Kubernetes cluster
- Helm +
- kubectl configuré

### Installation
```bash
# Build image
docker build -t anomaly-detector:v.0.0 .

# Push to registry
docker tag anomaly-detector:v.0.0 your-registry/anomaly-detector:v.0.0
docker push your-registry/anomaly-detector:v.0.0

# Deploy with Helm
helm install anomaly-detector ./charts/anomaly-detector \
  --set image.repository=your-registry/anomaly-detector \
  --set image.tag=v.0.0
```

## Monitoring

### Métriques clés
- `anomalies_detected_total`: Nombre total d'anomalies
- `predictions_total`: Nombre total de prédictions
- `prediction_latency_seconds`: Latence des prédictions

### Alertes Grafana
```yaml
- alert: HighAnomalyRate
  expr: rate(anomalies_detected_total[5m]) > 0.
  for: 5m
  annotations:
    summary: "Taux d'anomalies élevé"

- alert: HighLatency
  expr: histogram_quantile(0.99, rate(prediction_latency_seconds_bucket[5m])) > 0.5
  for: 5m
  annotations:
    summary: "Latence p99 > 500ms"
```

## Troubleshooting

### Service ne démarre pas
```bash
# Vérifier logs
kubectl logs -l app.kubernetes.io/name=anomaly-detector

# Vérifier events
kubectl get events --sort-by='.lastTimestamp'

# Problème commun: modèle manquant
# Solution: Vérifier que model.pkl est dans l'image
```

### Latence élevée
```bash
# Vérifier CPU/Memory
kubectl top pods -l app.kubernetes.io/name=anomaly-detector

# Scale up
kubectl scale deployment anomaly-detector --replicas=
```

### Faux positifs élevés
```bash
# Réentraîner avec threshold plus restrictif
anomaly-detector train \
  --data new_logs.csv \
  --threshold-percentile 95  # Au lieu de 90
```

## Maintenance

### Mise à jour du modèle
```bash
# . Entraîner nouveau modèle
anomaly-detector train --data logs.csv --output model_v.pkl

# . Tester
anomaly-detector score --model model_v.pkl --file test.csv

# . Rebuild image avec nouveau modèle
docker build -t anomaly-detector:v..0 .

# . Rolling update
helm upgrade anomaly-detector ./charts/anomaly-detector \
  --set image.tag=v..0
```

### Backup
```bash
# Sauvegarder modèle
kubectl cp anomaly-detector-pod:/app/model.pkl ./model_backup.pkl
```

## Rollback
```bash
# Rollback Helm
helm rollback anomaly-detector

# Rollback Kubernetes
kubectl rollout undo deployment/anomaly-detector
```
