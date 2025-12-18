#!/bin/bash
# Test complet : Keywords + ISO Forest (anomalies statistiques)
# Vérifie les deux types de détection

BASE_URL="http://localhost:8080"

echo " Test COMPLET - Détection Hybride"
echo "========================================="
echo ""

# Fonction pour tester une prédiction
test_prediction() {
    local message="$"
    local expected="$"
    local category="$"
    
    echo " [$category] $message"
    
    response=$(curl -s -X POST "$BASE_URL/predict" \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$message\",
            \"namespace\": \"prod\",
            \"pod\": \"test-pod-\"
        }")
    
    is_anomaly=$(echo "$response" | python -c "import sys, json; print(json.load(sys.stdin).get('is_anomaly', False))")
    confidence=$(echo "$response" | python -c "import sys, json; print(json.load(sys.stdin).get('confidence', 0))")
    method=$(echo "$response" | python -c "import sys, json; print(json.load(sys.stdin).get('detection_method', 'unknown'))")
    
    if [ "$is_anomaly" = "$expected" ]; then
        echo "    PASS - Anomaly=$is_anomaly, Confidence=$confidence, Method=$method"
    else
        echo "    FAIL - Expected=$expected, Got=$is_anomaly"
    fi
    echo ""
}

echo "═════════════════════════════════════════"
echo "CATÉGORIE  : Erreurs avec KEYWORDS (confiance ~0.90)"
echo "═════════════════════════════════════════"
echo ""

test_prediction "ERROR: Connection refused to database" "True" "Keywords"
test_prediction "FATAL: Unable to allocate memory" "True" "Keywords"
test_prediction "CRITICAL: OutOfMemoryError in worker process" "True" "Keywords"
test_prediction "Pod terminated: OOMKilled" "True" "Keywords"
test_prediction "Container in CrashLoopBackOff state" "True" "Keywords"
test_prediction "EXCEPTION: NullPointerException at line " "True" "Keywords"
test_prediction "Request timeout after 0 seconds" "True" "Keywords"

echo "═════════════════════════════════════════"
echo "CATÉGORIE  : Anomalies STATISTIQUES (sans keywords)"
echo "═════════════════════════════════════════"
echo ""
echo "Ces logs n'ont PAS de keywords évidents mais sont anormaux"
echo "ISO Forest devrait les détecter par analyse statistique"
echo ""

# Anomalies potentielles sans keywords
test_prediction "Response took 5ms to complete" "True/False" "Statistical"
test_prediction "Memory usage at 98% capacity" "True/False" "Statistical"
test_prediction "Queue depth exceeded 0000 messages" "True/False" "Statistical"
test_prediction "Retrying operation for the 50th time" "True/False" "Statistical"
test_prediction "Database connection pool exhausted" "True/False" "Statistical"

echo "  NOTE: Les anomalies statistiques dépendent du modèle"
echo "   ISO Forest peut les manquer (recall ~57%)"
echo "   Keywords garantissent 00% sur catégorie "
echo ""

echo "═════════════════════════════════════════"
echo "CATÉGORIE  : Logs NORMAUX (ne doivent PAS être détectés)"
echo "═════════════════════════════════════════"
echo ""

test_prediction "INFO: Connection established to redis" "False" "Normal"
test_prediction "DEBUG: Processing batch " "False" "Normal"
test_prediction "Health check passed successfully" "False" "Normal"
test_prediction "Request completed in 5ms" "False" "Normal"
test_prediction "User authentication successful" "False" "Normal"

echo "========================================="
echo " Tests terminés"
echo ""
echo " Résumé attendu:"
echo "   - Catégorie  (Keywords): 7/7 détectés "
echo "   - Catégorie  (Statistical): Variable (dépend du modèle)"
echo "   - Catégorie  (Normal): 0/5 détectés "
