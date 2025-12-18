#!/bin/bash
# Script de demarrage du stack de monitoring
# Ce script verifie les prerequis avant de lancer docker compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Verification des prerequis ==="

# Verifier que les fichiers de configuration existent
FILES_TO_CHECK=(
    "prometheus.yml"
    "grafana-provisioning/datasources/prometheus.yml"
    "grafana-provisioning/dashboards/dashboard.yml"
    "Dockerfile"
    "docker-compose.yml"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ ! -f "$file" ]; then
        echo "ERREUR: Fichier manquant: $file"
        exit 1
    fi
    echo "[OK] $file"
done

# Verifier que le modele existe
if [ ! -f "../modeles/hybrid_model.pkl" ]; then
    echo "ERREUR: Modele manquant: ../modeles/hybrid_model.pkl"
    exit 1
fi
echo "[OK] ../modeles/hybrid_model.pkl"

echo ""
echo "=== Demarrage des services ==="

# Nettoyer les anciens containers avec les memes noms
echo "Nettoyage des anciens containers..."
docker rm -f anomaly-detector prometheus grafana 2>/dev/null || true

docker compose down -v 2>/dev/null || true
docker compose build
docker compose up -d

echo ""
echo "=== Services demarres ==="
echo "Anomaly Detector: http://localhost:8080"
echo "  - Health: http://localhost:8080/health"
echo "  - Metrics: http://localhost:8080/metrics"
echo "Prometheus: http://localhost:9090"
echo "Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "=== Tests rapides ==="
echo "  curl http://localhost:8080/health"
echo ""
echo "=== Tester un fichier CSV ==="
echo "  python test_csv.py exemple_logs.csv"
echo "  python test_csv.py votre_fichier.csv --max 100"
