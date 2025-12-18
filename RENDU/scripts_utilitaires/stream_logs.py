#!/usr/bin/env python
"""
Simulateur de logs Kubernetes en temps réel
Envoie des logs continus à l'API pour monitoring en direct
"""
import requests
import time
import random
from datetime import datetime

API_URL = "http://localhost:8080/predict"

# Patterns de logs réalistes
NORMAL_LOGS = [
    "INFO: Request processed successfully in {time}ms",
    "DEBUG: Cache hit for user session {id}",
    "INFO: Database query completed",
    "DEBUG: Processing batch {id}",
    "INFO: Health check passed",
    "INFO: Connection established to redis",
    "DEBUG: Fetching data from cache",
    "INFO: User authentication successful",
    "DEBUG: Loading configuration",
    "INFO: Service started successfully"
]

ERROR_LOGS = [
    "ERROR: Connection refused to database",
    "CRITICAL: OutOfMemoryError in worker process",
    "ERROR: Failed to connect to Redis",
    "EXCEPTION: NullPointerException in handler",
    "ERROR: Timeout waiting for response",
    "CRITICAL: Disk space critical on /data",
    "ERROR: Authentication failed",
    "FATAL: Unable to allocate memory",
    "ERROR: CrashLoopBackOff detected",
    "CRITICAL: Pod evicted due to resource limits"
]

NAMESPACES = ["default", "prod", "staging", "dev"]
PODS = ["api", "backend", "worker", "frontend", "database"]

def generate_log():
    """Génère un log aléatoire avec 80% normal, 0% erreurs"""
    is_error = random.random() < 0.10
    
    if is_error:
        message = random.choice(ERROR_LOGS)
        namespace = "prod" if random.random() < 0.7 else random.choice(NAMESPACES)
    else:
        message = random.choice(NORMAL_LOGS)
        namespace = random.choice(NAMESPACES)
        # Remplacer les placeholders
        message = message.format(
            time=random.randint(0, 500),
            id=random.randint(1000, 9999)
        )
    
    pod = f"{random.choice(PODS)}-{random.randint(1, 5)}"
    
    return {
        "message": message,
        "namespace": namespace,
        "pod": pod
    }

def send_log(log_entry):
    """Envoie un log à l'API"""
    try:
        response = requests.post(API_URL, json=log_entry, timeout=5)
        if response.status_code == 200:
            result = response.json()
            status = "ANOMALY" if result['is_anomaly'] else "NORMAL"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {status} | {log_entry['namespace']}/{log_entry['pod']} | {log_entry['message'][:60]}")
        else:
            print(f"[INFO] Error {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[INFO] Connection error: {e}")

def main():
    print("="*80)
    print("[INFO] STREAMING LOG SIMULATOR - Real-time monitoring")
    print("="*80)
    print(f"[INFO] Sending logs to: {API_URL}")
    print(f"[INFO] Grafana dashboard: http://localhost:3000")
    print(f"[INFO] Prometheus metrics: http://localhost:9090")
    print("")
    print("⏱  Rate: ~-5 logs/second (realistic production rate)")
    print("[INFO] Distribution: 80% normal, 0% errors")
    print("")
    print("Press Ctrl+C to stop...")
    print("="*80)
    print("")
    
    log_count = 0
    anomaly_count = 0
    
    try:
        while True:
            # Génère - logs par cycle
            batch_size = random.randint(1, 5)
            
            for _ in range(batch_size):
                log = generate_log()
                send_log(log)
                log_count += 1
                
                # Statistiques toutes les 50 logs
                if log_count % 50 == 0:
                    print("")
                    print(f"[INFO] Stats: {log_count} logs sent | Check Grafana for real-time graphs")
                    print("")
            
            # Pause aléatoire pour simuler trafic réaliste
            time.sleep(random.uniform(0., 0.8))
            
    except KeyboardInterrupt:
        print("")
        print("="*80)
        print("Stopping log stream...")
        print(f"[INFO] Total logs sent: {log_count}")
        print("[INFO] Check Grafana dashboard for final metrics")
        print("="*80)

if __name__ == "__main__":
    main()
