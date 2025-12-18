#!/bin/bash

echo " Test du monitoring - Génération de trafic"
echo "=============================================="
echo ""
echo " Accès aux interfaces:"
echo "  - API:        http://localhost:8080"
echo "  - Prometheus: http://localhost:9090"
echo "  - Grafana:    http://localhost:000 (admin/admin)"
echo ""
echo " Génération de trafic..."
echo ""

# Fonction pour envoyer une prédiction
send_prediction() {
    local message="$"
    local namespace="$"
    local pod="$"
    
    curl -s -X POST http://localhost:8080/predict \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$message\", \"namespace\": \"$namespace\", \"pod\": \"$pod\"}" \
        > /dev/null
}

# Phase : Logs normaux (80%)
echo " Phase : Envoi de 00 logs normaux..."
for i in {..00}; do
    messages=(
        "INFO: Request processed successfully"
        "DEBUG: Cache hit for user session"
        "INFO: Database query completed in 5ms"
        "DEBUG: Processing batch $i"
        "INFO: Health check passed"
    )
    message="${messages[$RANDOM % ${#messages[@]}]}"
    namespace="default"
    pod="api-$((i % 0))"
    
    send_prediction "$message" "$namespace" "$pod"
    
    # Afficher progression tous les 0 logs
    if [ $((i % 0)) -eq 0 ]; then
        echo "  ✓ $i logs envoyés..."
    fi
    
    sleep 0.05
done

echo " Phase  terminée"
echo ""

# Phase : Quelques anomalies (0%)
echo " Phase : Envoi de 5 logs avec anomalies..."
for i in {..5}; do
    errors=(
        "ERROR: Connection refused to database"
        "CRITICAL: OutOfMemoryError in worker process"
        "ERROR: Failed to connect to Redis"
        "EXCEPTION: NullPointerException in handler"
        "ERROR: Timeout waiting for response"
        "CRITICAL: Disk space critical on /data"
        "ERROR: Authentication failed for user"
        "FATAL: Unable to allocate memory"
    )
    error="${errors[$RANDOM % ${#errors[@]}]}"
    namespace="prod"
    pod="backend-$((i % 5))"
    
    send_prediction "$error" "$namespace" "$pod"
    
    # Afficher progression tous les 5 logs
    if [ $((i % 5)) -eq 0 ]; then
        echo "    $i anomalies envoyées..."
    fi
    
    sleep 0.
done

echo " Phase  terminée"
echo ""

# Phase : Burst d'erreurs (simulation incident)
echo "💥 Phase : Simulation d'incident (burst d'erreurs)..."
for i in {..0}; do
    send_prediction "ERROR: CrashLoopBackOff in pod worker-$i" "prod" "worker-$i"
    
    if [ $((i % 0)) -eq 0 ]; then
        echo "   $i erreurs en burst..."
    fi
    
    sleep 0.0  # Rapide pour simuler un burst
done

echo " Phase  terminée"
echo ""

# Vérifier les métriques
echo " Récupération des métriques..."
echo ""

# Métriques Prometheus
echo " Métriques brutes (Prometheus):"
curl -s http://localhost:8080/metrics | grep -E "(anomalies_detected_total|predictions_total|prediction_latency)" | head -0

echo ""
echo ""
echo " Test terminé !"
echo ""
echo " Consultez les dashboards:"
echo "  . Grafana: http://localhost:000"
echo "     - Login: admin / admin"
echo "     - Dashboard: 'Anomaly Detection MVP'"
echo ""
echo "  . Prometheus: http://localhost:9090"
echo "     - Requête: rate(anomalies_detected_total[m])"
echo "     - Requête: histogram_quantile(0.99, rate(prediction_latency_seconds_bucket[5m]))"
echo ""
echo " Statistiques attendues:"
echo "  - Total prédictions: ~55"
echo "  - Anomalies détectées: ~55 (5%)"
echo "  - Latence P99: < 00ms"
