# 🎯 Guide de Démonstration - MVP Anomaly Detection v3.0.1

## Prérequis
- Docker Desktop installé et **démarré**
- Terminal ouvert dans le dossier `RENDU/`

---

## 📋 Étapes de la Démonstration

### 1️⃣ Présentation du Projet (1 min)

```bash
make help
```

Expliquer :
- **MVP de détection d'anomalies** dans les logs Kubernetes
- **Modèle hybride** : Isolation Forest + 22 mots-clés critiques
- **API REST** pour intégration facile
- **Monitoring** avec Prometheus/Grafana

---

### 2️⃣ Construction de l'Image Docker (1-2 min)

```bash
make docker-build
```

Points à montrer :
- Le Dockerfile utilise Python 3.11-slim
- Le modèle (4.9 MB) est embarqué dans l'image
- Image légère et optimisée pour la production

---

### 3️⃣ Lancement du Service (30 sec)

**Option A - Service seul :**
```bash
make docker-run
```

**Option B - Stack complète avec monitoring :**
```bash
make deploy-full
```

---

### 4️⃣ Test de l'API (2 min)

#### Health Check
```bash
curl http://localhost:8080/health | python -m json.tool
```

Résultat attendu :
```json
{
    "status": "healthy",
    "model_version": "hybrid_v3.0.1"
}
```

#### Prédiction - Log Normal
```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message": "Pod started successfully", "namespace": "production", "pod": "api-1"}' | python -m json.tool
```

Résultat :
```json
{
    "is_anomaly": false,
    "confidence": 0.85,
    "detection_method": "isolation_forest"
}
```

#### Prédiction - Anomalie (mot-clé critique)
```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message": "FATAL: OOMKilled - container exceeded memory limit", "namespace": "production", "pod": "api-1"}' | python -m json.tool
```

Résultat :
```json
{
    "is_anomaly": true,
    "confidence": 0.99,
    "detection_method": "keyword",
    "matched_keyword": "OOMKilled"
}
```

#### Prédiction - Anomalie (pattern rare)
```bash
curl -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message": "Unusual spike: 5000 connections per second detected on port 443", "namespace": "monitoring", "pod": "nginx-1"}' | python -m json.tool
```

---

### 5️⃣ Batch Detection (1 min)

```bash
# Tester sur 100 logs
python deployment/test_batch.py --file tests/test_sample.csv --limit 100
```

Montrer :
- Nombre d'anomalies détectées
- Répartition keywords vs Isolation Forest
- Performance (logs/seconde)

---

### 6️⃣ Monitoring Grafana (si deploy-full)

1. Ouvrir http://localhost:3000
2. Login : admin / admin
3. Dashboard "Anomaly Detection"

Métriques visibles :
- Requêtes par seconde
- Anomalies détectées
- Latence de réponse
- Répartition par méthode de détection

---

### 7️⃣ Tests Unitaires (30 sec)

```bash
make test
```

Attendu : 5 tests passent (100%)

---

## 📊 Métriques du Modèle

| Métrique | Valeur | Description |
|----------|--------|-------------|
| Precision | ~72% | Vrais positifs parmi les alertes |
| Recall | ~85% | Anomalies détectées parmi toutes |
| F1-Score | ~78% | Moyenne harmonique |
| FPR | ~0.5% | Taux de faux positifs |
| Mots-clés garantis | 100% | OOMKilled, CrashLoopBackOff, etc. |

---

## 🛑 Arrêt des Services

```bash
# Arrêter le service Docker
docker stop $(docker ps -q --filter ancestor=anomaly-detector)

# Ou arrêter la stack complète
cd deployment && docker compose down
```

---

## 💡 Points Clés à Mentionner

1. **Double détection** : Mots-clés (précis) + ML (patterns inconnus)
2. **22 mots-clés critiques** Kubernetes couverts
3. **Isolation Forest** détecte 65% des anomalies rares
4. **API REST** prête pour intégration CI/CD
5. **Helm Charts** fournis pour déploiement Kubernetes
