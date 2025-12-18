# Deployment - Guide Rapide

## Demarrage en 1 commande

```bash
./start.sh
```

Ce script:
1. Verifie que tous les fichiers necessaires existent
2. Nettoie les anciens containers
3. Construit et demarre les services

## Services disponibles

| Service | URL | Description |
|---------|-----|-------------|
| API Anomaly Detection | http://localhost:8080 | Detection d'anomalies |
| Prometheus | http://localhost:9090 | Metriques |
| Grafana | http://localhost:3000 | Dashboards (admin/admin) |

## Modes de test

### Mode BATCH (recommande pour evaluation)

Utilise `test_batch.py` pour analyser un fichier CSV complet avec les **features temporels calcules correctement** sur tout le dataset:

```bash
# Test sur dataset complet
python test_batch.py /chemin/vers/Wiremind_logs.csv

# Test rapide sur 10000 logs
python test_batch.py /chemin/vers/logs.csv --max 10000
```

Ce mode calcule les features temporels (burst_ratio, acceleration, rate_5min, etc.) de la meme maniere que l'entrainement du modele.

### Mode Streaming (temps reel via API)

Utilise `test_csv.py` pour envoyer les logs un par un a l'API:

```bash
python test_csv.py /chemin/vers/logs.csv --max 1000
```

**Note:** En mode streaming, les features temporels se remplissent progressivement. Les premieres minutes donnent des resultats moins precis.

## Format CSV attendu

Le fichier CSV doit avoir **au minimum une colonne `message`**. Les colonnes `namespace` et `pod` sont optionnelles.

**Format recommande:**
```csv
message,namespace,pod
"Error: connection refused",production,api-server-xyz
"INFO: request completed",default,worker-abc
```

**Format minimal (1 colonne):**
```csv
message
"Error: connection refused"
"INFO: request completed"
```

**Format Wiremind (compatible):**
```csv
wiremind.message,kubernetes.namespace_name,kubernetes.pod_name
"Error: connection refused",production,api-server-xyz
```

### Commandes de test

```bash
# Tester avec le fichier d'exemple
python test_csv.py exemple_logs.csv

# Tester votre propre fichier
python test_csv.py votre_fichier.csv

# Limiter le nombre de logs (pour un test rapide)
python test_csv.py gros_fichier.csv --max 100

# Mode verbeux (voir chaque anomalie)
python test_csv.py votre_fichier.csv -v
```

### Resultats

Le script genere un fichier `votre_fichier_anomalies.json` contenant:
- Resume (nombre de logs, anomalies, taux, méthodes de détection)
- Liste des anomalies detectees avec priorité, score, location et méthode

**Format d'affichage dans le terminal:**
```
┌──────────┬──────────┬─────────────────────────────────────┬──────────────────────┬────────────────────┐
│ Priority │ Score    │ Log                                 │ Location             │ Method             │
├──────────┼──────────┼─────────────────────────────────────┼──────────────────────┼────────────────────┤
│ 🔴 P1    │ -0.0500  │ FATAL: OOMKilled...                 │ prod/api-xyz         │ hybrid_both        │
│ 🟠 P2    │ +0.0135  │ ERROR: Connection refused...        │ staging/db-01        │ keyword_detection  │
│ 🟡 P3    │ -0.0300  │ Unusual pattern...                  │ dev/worker-5         │ isolation_forest   │
└──────────┴──────────┴─────────────────────────────────────┴──────────────────────┴────────────────────┘
```

**Priorités:**
- 🔴 P1: Critical (hybrid_both ou score < -0.1)
- 🟠 P2: High (keyword_detection)
- 🟡 P3: Medium (isolation_forest)
- 🟢 P4: Low (score proche du seuil)
- ⚪ P5: Info

## Erreurs courantes

### "Le fichier n'existe pas"
- Verifiez le chemin du fichier
- Utilisez le chemin complet: `python test_csv.py /chemin/complet/fichier.csv`

### "Colonne 'message' non trouvee"
- Renommez votre colonne de logs en `message`
- Ou utilisez `wiremind.message` si c'est le format Wiremind

### "Impossible de contacter l'API"
- Verifiez que Docker est lance
- Relancez `./start.sh`
- Verifiez que le port 8080 n'est pas utilise par une autre application

### "Erreur d'encodage"
- Sauvegardez votre CSV en UTF-8
- Dans Excel: Fichier > Enregistrer sous > CSV UTF-8

## Arreter les services

```bash
docker compose down
```

## Structure du dossier

```
deployment/
├── start.sh              # Script de demarrage
├── test_csv.py           # Script de test CSV
├── exemple_logs.csv      # Fichier CSV d'exemple
├── docker-compose.yml    # Configuration Docker
├── Dockerfile            # Image Docker du service
├── prometheus.yml        # Configuration Prometheus
└── grafana-provisioning/ # Dashboards Grafana
```
