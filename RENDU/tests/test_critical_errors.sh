#!/bin/bash
# Script de test pour erreurs critiques connues
# Ce script teste si l'API détecte correctement les anomalies évidentes

BASE_URL="http://localhost:8080"

echo " Test de détection d'erreurs critiques"
echo "========================================="
echo ""

# Fonction pour tester une prédiction
test_prediction() {
    local message="$"
    local expected="$"
    
    echo " Test: $message"
    
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

# Test : ERROR keyword
test_prediction "ERROR: Connection refused to database" "True"

# Test : FATAL keyword
test_prediction "FATAL: Unable to allocate memory" "True"

# Test : CRITICAL keyword
test_prediction "CRITICAL: OutOfMemoryError in worker process" "True"

# Test : OOMKilled (Kubernetes)
test_prediction "Pod terminated: OOMKilled" "True"

# Test 5: CrashLoopBackOff (Kubernetes)
test_prediction "Container in CrashLoopBackOff state" "True"

# Test 6: Exception
test_prediction "EXCEPTION: NullPointerException at line " "True"

# Test 7: Timeout
test_prediction "Request timeout after 0 seconds" "True"

# Test 8: Normal log (should NOT be anomaly)
test_prediction "INFO: Connection established to redis" "False"

# Test 9: Debug log (should NOT be anomaly)
test_prediction "DEBUG: Processing batch " "False"

# Test 0: Health check (should NOT be anomaly)
test_prediction "Health check passed successfully" "False"

echo "========================================="
echo " Tests terminés"
