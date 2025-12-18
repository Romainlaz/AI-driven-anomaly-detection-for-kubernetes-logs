import requests
import time
import random

API_URL = "http://localhost:8080/predict"

# Messages de test variés pour générer des métriques
test_messages = [
    {"message": "Error: OOMKilled", "namespace": "production", "pod": "api-server-"},
    {"message": "FATAL: Application crashed", "namespace": "production", "pod": "worker-"},
    {"message": "ERROR: Connection timeout", "namespace": "staging", "pod": "db-proxy-"},
    {"message": "WARN: High memory usage 85%", "namespace": "production", "pod": "cache-"},
    {"message": "ERROR: Failed to pull image", "namespace": "staging", "pod": "frontend-5"},
    {"message": "CRITICAL: Disk space low", "namespace": "production", "pod": "storage-6"},
    {"message": "ERROR: Database connection refused", "namespace": "production", "pod": "api-7"},
    {"message": "FATAL: Segmentation fault", "namespace": "staging", "pod": "worker-8"},
    {"message": "ERROR: Request rate exceeded", "namespace": "production", "pod": "gateway-9"},
    {"message": "WARN: CPU throttling detected", "namespace": "staging", "pod": "compute-0"},
]

print("[INFO] Test Grafana - Génération de métriques...")
print(f"[INFO] Envoi de {len(test_messages)} requêtes en boucle\n")

anomaly_count = 0
total_requests = 0

try:
    for i in range(50):  # 50 requêtes
        msg = random.choice(test_messages)
        
        try:
            response = requests.post(API_URL, json=msg, timeout=5)
            total_requests += 1
            
            if response.status_code == 200:
                anomaly_count += 1
                result = response.json()
                print(f"[INFO] [{i+1}/50] Anomalie détectée - Score: {result['anomaly_score']:.2f} - {msg['message'][:50]}")
            elif response.status_code == 0:
                print(f"[INFO] [{i+1}/50] Log normal - {msg['message'][:50]}")
            else:
                print(f"[INFO]  [{i+1}/50] Status {response.status_code}")
                
        except Exception as e:
            print(f"[INFO] [{i+1}/50] Erreur: {e}")
        
        time.sleep(0.1)  # 100ms entre chaque requête
        
except KeyboardInterrupt:
    print("\n\n  Test interrompu par l'utilisateur")

print(f"\n Résumé:")
print(f"[INFO]  • Total requêtes: {total_requests}")
print(f"[INFO]  • Anomalies: {anomaly_count}")
print(f"[INFO]  • Taux d'anomalies: {(anomaly_count/total_requests*100):.2f}%")
print(f"\n Vérifie Grafana: http://localhost:3000")
print(f"[INFO] Vérifie Prometheus: http://localhost:9090")
