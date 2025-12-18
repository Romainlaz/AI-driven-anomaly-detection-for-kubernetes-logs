#  Scripts Utilitaires

Scripts pour tester, valider et utiliser le système de détection d'anomalies.

---

## 📁 Contenu

### . `demo.py` -  Démo Interactive Complète
**Démo guidée montrant toutes les capacités du système.**

**Utilisation** :
```bash
python demo.py
```

**Scénarios démontrés** :
.  Erreurs critiques production (OOMKilled, CrashLoopBackOff)
.  Détection ML pure (patterns inhabituels)
.  Logs normaux (baseline)
.  Erreurs dev (priorité basse)
5.  Warnings (surveillance)
6. 🐳 Erreurs Docker (ImagePullBackOff)

**Durée** : ~ minutes (interactif)

---

### . `test_csv.py` -  Test sur Fichiers CSV
**Analyse batch de logs depuis un fichier CSV.**

**Utilisation** :
```bash
python test_csv.py fichier.csv
```

**Format CSV requis** :
```csv
message,namespace,pod
"ERROR: Connection refused",production,api-
"INFO: Request completed",production,api-
```

**Sortie** :
- Résumé des détections
- Détails par log (scores, sévérité, diagnostics)
- Export JSON (optionnel)

**Exemple** :
```bash
python test_csv.py ../donnees_test/example_logs.csv
```

---

### . `batch_detect.py` - ⚙ Traitement Batch
**Traitement batch optimisé pour gros volumes.**

**Utilisation** :
```bash
python batch_detect.py \
  --input logs.csv \
  --output results.json \
  --batch-size 1000
```

**Options** :
- `--input` : Fichier CSV source
- `--output` : Fichier JSON résultats
- `--batch-size` : Taille des batchs (défaut: 00)
- `--workers` : Threads parallèles (défaut: )
- `--filter` : Filtrer par sévérité (critical,high,medium,low)

**Performance** :
- ~000 logs/s sur MacBook Pro M
- Parallélisation automatique
- Gestion mémoire optimisée

---

### . `stream_logs.py` - 🌊 Simulation Streaming
**Simule un flux de logs temps réel.**

**Utilisation** :
```bash
python stream_logs.py \
  --source logs.csv \
  --rate 0 \
  --duration 60
```

**Options** :
- `--source` : Fichier CSV source
- `--rate` : Logs par seconde (défaut: 0)
- `--duration` : Durée en secondes (défaut: infini)
- `--shuffle` : Mélanger l'ordre (défaut: false)

**Cas d'usage** :
- Tester performance temps réel
- Valider features temporelles (burst, rate)
- Simuler charge production

**Exemple** :
```bash
# Simuler 100 logs/s pendant 5 minutes
python stream_logs.py --rate 100 --duration 300
```

---

##  Installation

Les scripts nécessitent les dépendances du projet :

```bash
# Depuis le dossier RENDU
pip install -r code_source/requirements.txt
```

Ou si vous utilisez Docker :

```bash
# Les scripts sont déjà dans le container
docker exec -it rendu-api- python /app/batch_detect.py --help
```

---

##  Exemples d'Utilisation

### Cas  : Validation Rapide (Démo)
```bash
# Démo interactive (min)
python demo.py
```
**But** : Vérifier que le système fonctionne

---

### Cas  : Test sur Vos Logs
```bash
# Préparer votre fichier CSV
echo "message,namespace,pod" > my_logs.csv
echo "ERROR: Database timeout,production,db-" >> my_logs.csv

# Analyser
python test_csv.py my_logs.csv
```
**But** : Tester avec données réelles

---

### Cas  : Analyse Batch (000+ logs)
```bash
# Traiter gros volume
python batch_detect.py \
  --input big_logs.csv \
  --output analysis.json \
  --batch-size 1000 \
  --workers 8 \
  --filter critical,high
```
**But** : Analyse à grande échelle

---

### Cas  : Test Temps Réel
```bash
# Simuler flux production
python stream_logs.py \
  --source ../donnees_test/example_logs.csv \
  --rate 50 \
  --duration 0 \
  --shuffle
```
**But** : Valider performance streaming

---

### Cas 5 : API Directe (curl)
```bash
# Test unitaire via API
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{
    "message": "FATAL: OOMKilled - pod terminated",
    "namespace": "production",
    "pod": "api-server-"
  }'
```
**But** : Intégration avec scripts existants

---

##  Workflows Recommandés

### Workflow  : Première Validation (5min)
```bash
# . Démarrer le service
cd ../deployment && docker compose up -d

# . Vérifier santé
curl http://localhost:8080/health

# . Lancer démo
cd ../scripts_utilitaires
python demo.py

# . Test avec exemple
python test_csv.py ../donnees_test/example_logs.csv
```

---

### Workflow  : Analyse Production (0min)
```bash
# . Exporter logs Kubernetes
kubectl logs -n production --all-containers --since=h > prod_logs.txt

# . Convertir en CSV
python convert_to_csv.py prod_logs.txt prod_logs.csv

# . Analyser
python batch_detect.py --input prod_logs.csv --output prod_analysis.json

# . Filtrer critiques
jq '.[] | select(.severity=="critical")' prod_analysis.json
```

---

### Workflow  : Test de Charge (h)
```bash
# . Générer dataset synthétique
python generate_synthetic_logs.py --output synthetic_0k.csv --count 0000

# . Test streaming
python stream_logs.py --source synthetic_0k.csv --rate 100 --duration 300

# . Analyser métriques
curl http://localhost:8080/metrics | grep anomaly_detection
```

---

##  Sorties des Scripts

### demo.py - Format Console
```
================================================================================
 SYSTÈME DE DÉTECTION D'ANOMALIES IA - KUBERNETES LOGS
================================================================================

SCÉNARIO  :  ERREUR CRITIQUE EN PRODUCTION
────────────────────────────────────────────────────────────────────────────────
 Test . - OOM Kill en Production (CRITIQUE)
Message: FATAL: OOMKilled - container memory limit exceeded, pod terminated
Context: production/api-server-

 ANOMALIE DÉTECTÉE
 Sévérité: CRITICAL (Priorité P)
 Confiance: 69%
 Impact:  CRITICAL - Production service DOWN or DEGRADED

 Scores de Détection:
    ML Model:     0. (%)
    Keywords:     .00 (00%)
    Temporal:     0.00 (0%)
    Context:      .50x
     Combined:     0.69

🔬 Méthode: Keywords + Context

 Diagnostic:
   •  Critical error pattern detected: FATAL OOMKilled
   •  PRODUCTION ENVIRONMENT - High priority alert

 Actions Recommandées:
   . ⚡ URGENT: Increase memory limits in deployment
   .  Investigate memory leaks in application
   .  Check memory usage trends
   .  Consider horizontal scaling
```

---

### test_csv.py - Format JSON
```json
{
  "summary": {
    "total_logs": 0,
    "anomalies_detected": 5,
    "detection_rate": "50%",
    "average_confidence": 0.6
  },
  "detections": [
    {
      "log_number": ,
      "message": "ERROR: HTTP 500 Internal Server Error",
      "is_anomaly": true,
      "confidence": 0.6,
      "severity": "high",
      "priority": "P",
      "scores": {...},
      "diagnostics": [...],
      "recommended_actions": [...]
    }
  ]
}
```

---

### batch_detect.py - Format JSON
```json
{
  "metadata": {
    "processed": 000,
    "anomalies": 7,
    "duration_seconds": .5,
    "logs_per_second": 80
  },
  "results": [...]
}
```

---

##  Dépannage

### Erreur : "Connection refused"
**Cause** : Service API non démarré  
**Solution** :
```bash
cd ../deployment && docker compose up -d
```

---

### Erreur : "Module not found"
**Cause** : Dépendances manquantes  
**Solution** :
```bash
pip install -r ../code_source/requirements.txt
```

---

### Erreur : "File not found"
**Cause** : Mauvais chemin relatif  
**Solution** :
```bash
# Toujours exécuter depuis scripts_utilitaires/
cd /chemin/vers/RENDU/scripts_utilitaires
python demo.py
```

---

### Performance Lente
**Cause** : Trop de logs en parallèle  
**Solution** :
```bash
# Réduire batch size
python batch_detect.py --batch-size 100 --workers 
```

---

##  Ressources Complémentaires

- **Documentation API** : http://localhost:8080/docs
- **Métriques** : http://localhost:8080/metrics
- **Guide complet** : ../QUICKSTART.md
- **Architecture** : ../documentation/ARCHITECTURE.md

---

##  Checklist de Validation

Avant d'utiliser les scripts, vérifiez :

- [ ] Service API démarré (`docker compose up -d`)
- [ ] Health check OK (`curl http://localhost:8080/health`)
- [ ] Dépendances installées (`pip install -r requirements.txt`)
- [ ] CSV bien formaté (colonnes: message, namespace, pod)
- [ ] Chemins relatifs corrects (depuis scripts_utilitaires/)

---

 **Tous les scripts sont prêts à l'emploi !**
