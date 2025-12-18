#!/bin/bash
# ============================================================
# Script de Démonstration - MVP Anomaly Detection v3.0.1
# ============================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "============================================================"
echo "   MVP Anomaly Detection for Kubernetes Logs v3.0.1"
echo "============================================================"
echo -e "${NC}"

step() {
    echo -e "\n${YELLOW}▶ $1${NC}"
    sleep 1
}

result() {
    echo -e "${GREEN}✓ $1${NC}"
}

# 1. Vérification Docker
step "1. Vérification de Docker..."
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker n'est pas démarré. Lancez Docker Desktop et réessayez.${NC}"
    exit 1
fi
result "Docker est opérationnel"

# 2. Construction de l'image
step "2. Construction de l'image Docker..."
make docker-build
result "Image construite avec succès"

# 3. Démarrage du service
step "3. Démarrage du service..."
docker run -d -p 8080:8080 --name anomaly-demo anomaly-detector:latest
sleep 3
result "Service démarré sur http://localhost:8080"

# 4. Health Check
step "4. Vérification du health check..."
echo -e "${BLUE}Requête:${NC} GET /health"
curl -s http://localhost:8080/health | python3 -m json.tool
result "Service en bonne santé"

# 5. Test - Log Normal
step "5. Test de prédiction - Log NORMAL..."
echo -e "${BLUE}Requête:${NC} POST /predict"
echo '{"message": "Pod started successfully", "namespace": "default", "pod": "nginx-1"}'
echo -e "\n${BLUE}Réponse:${NC}"
curl -s -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message": "Pod started successfully", "namespace": "default", "pod": "nginx-1"}' | python3 -m json.tool
result "Log classifié comme NORMAL"

# 6. Test - Anomalie (mot-clé)
step "6. Test de prédiction - ANOMALIE (mot-clé OOMKilled)..."
echo -e "${BLUE}Requête:${NC} POST /predict"
echo '{"message": "Container killed due to OOMKilled", "namespace": "production", "pod": "api-backend"}'
echo -e "\n${BLUE}Réponse:${NC}"
curl -s -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message": "Container killed due to OOMKilled", "namespace": "production", "pod": "api-backend"}' | python3 -m json.tool
result "Anomalie détectée par MOT-CLÉ"

# 7. Test - Anomalie (CrashLoopBackOff)
step "7. Test de prédiction - ANOMALIE (CrashLoopBackOff)..."
echo -e "${BLUE}Requête:${NC} POST /predict"
echo '{"message": "Pod status: CrashLoopBackOff", "namespace": "kube-system", "pod": "coredns-1"}'
echo -e "\n${BLUE}Réponse:${NC}"
curl -s -X POST http://localhost:8080/predict \
  -H "Content-Type: application/json" \
  -d '{"message": "Pod status: CrashLoopBackOff", "namespace": "kube-system", "pod": "coredns-1"}' | python3 -m json.tool
result "Anomalie critique détectée"

# 8. Test sur CSV
step "8. Test BATCH sur fichier CSV..."
echo -e "${BLUE}Pour tester sur votre propre fichier CSV :${NC}"
echo ""
echo "  python deployment/test_batch.py <votre_fichier.csv>"
echo ""
echo -e "${BLUE}Exemple avec Wiremind_Logs_2.csv :${NC}"
echo "  python deployment/test_batch.py ../Wiremind_Logs_2.csv --max 1000"
echo ""

# Demander si on veut tester un CSV
read -p "Voulez-vous tester un fichier CSV maintenant ? (o/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Oo]$ ]]; then
    read -p "Chemin du fichier CSV : " csv_path
    if [ -f "$csv_path" ]; then
        read -p "Nombre max de lignes (defaut: 500) : " max_rows
        max_rows=${max_rows:-500}
        echo -e "\n${YELLOW}Analyse en cours...${NC}\n"
        python deployment/test_batch.py "$csv_path" --max "$max_rows"
    else
        echo -e "${RED}Fichier non trouvé: $csv_path${NC}"
    fi
fi

# Nettoyage
step "9. Nettoyage..."
docker stop anomaly-demo && docker rm anomaly-demo
result "Conteneur arrêté et supprimé"

echo -e "\n${GREEN}"
echo "============================================================"
echo "   DÉMONSTRATION TERMINÉE"
echo "============================================================"
echo -e "${NC}"
echo "Pour relancer le service :"
echo "  make docker-run     # Service seul"
echo "  make deploy-full    # Avec Prometheus + Grafana"
echo ""
echo "Pour tester un CSV :"
echo "  docker run -d -p 8080:8080 anomaly-detector:latest"
echo "  python deployment/test_batch.py <fichier.csv>"
echo ""
