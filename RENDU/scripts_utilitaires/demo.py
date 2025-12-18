#!/usr/bin/env python
"""
 DÉMO INTERACTIVE - Système de Détection d'Anomalies IA pour Kubernetes
Wiremind - Détection avancée avec ML + Keywords + Patterns Temporels
"""

import json
import urllib.request
import time
from datetime import datetime

API_URL = "http://localhost:8080"

def print_banner():
    print("\n" + "="*80)
    print("[INFO] SYSTÈME DE DÉTECTION D'ANOMALIES IA - KUBERNETES LOGS")
    print("="*80)
    print("[INFO]  Méthodes d'Analyse Combinées :")
    print("[INFO]   •  Machine Learning (Isolation Forest - 300 estimateurs, 662 features)")
    print("[INFO]   •  Keywords Métier (Critical/High/Medium patterns)")
    print("[INFO]   •  Patterns Temporels (Burst detection, accélération)")
    print("="*80 + "\n")

def check_health():
    print("[INFO] Vérification du service...")
    try:
        req = urllib.request.urlopen(f"{API_URL}/health")
        data = json.loads(req.read().decode())
        if data['model_loaded']:
            print("[INFO] Service OK - Modèle chargé\n")
            return True
    except Exception as e:
        print(f"[INFO] Service non disponible: {e}")
        print("[INFO] Démarrez d'abord: cd deployment && docker compose up -d\n")
        return False

def test_log(title, message, namespace, pod, show_full=True):
    print("\n" + "─"*80)
    print(f"[INFO] {title}")
    print("─"*80)
    print(f"Message: {message}")
    print(f"Context: {namespace}/{pod}\n")
    
    # Call API
    log_entry = {"message": message, "namespace": namespace, "pod": pod}
    req = urllib.request.Request(
        f"{API_URL}/predict",
        data=json.dumps(log_entry).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode())
        
        # Display result
        status = " ANOMALIE DÉTECTÉE" if result['is_anomaly'] else " LOG NORMAL"
        severity_emoji = {
            'critical': '',
            'high': '', 
            'medium': '',
            'low': ''
        }
        
        print(f"\n{status}")
        print(f"{severity_emoji.get(result['severity'], '')} Sévérité: {result['severity'].upper()} (Priorité {result['priority']})")
        print(f"[INFO] Confiance: {result['confidence']:.0%}")
        print(f"[INFO] Impact: {result['impact']}")
        
        # Scores breakdown
        scores = result['scores']
        print(f"\n Scores de Détection:")
        print(f"[INFO]    ML Model:     {scores['ml_model']:.2f} ({scores['ml_model']*100:.2f}%)")
        print(f"[INFO]    Keywords:     {scores['keywords']:.2f} ({scores['keywords']*100:.2f}%)")
        print(f"[INFO]    Temporal:     {scores['temporal_pattern']:.2f} ({scores['temporal_pattern']*100:.2f}%)")
        print(f"[INFO]    Context:      {scores['context_multiplier']:.2f}x")
        print(f"[INFO]     Combined:     {scores['combined']:.2f}")
        
        # Detection method
        print(f"\n🔬 Méthode: {result['detection_method']}")
        
        if show_full and result['diagnostics']:
            print(f"\n Diagnostic:")
            for diag in result['diagnostics']:
                print(f"[INFO]   • {diag}")
        
        if show_full and result['recommended_actions']:
            print(f"\n Actions Recommandées:")
            for i, action in enumerate(result['recommended_actions'], ):
                print(f"[INFO]   {i}. {action}")
        
        # Temporal metrics
        tm = result['temporal_metrics']
        if any(v > 0 for v in tm.values()):
            print(f"\n Métriques Temporelles:")
            print(f"[INFO]   Rate 5min: {tm['error_rate_5min']:.2f}/min")
            print(f"[INFO]   Burst ratio: {tm['burst_ratio']:.2f}")
            print(f"[INFO]   Acceleration: {tm['acceleration']:.2f}")
        
        # Technical details
        if show_full:
            print(f"\n Détails Techniques:")
            print(f"[INFO]   ISO Forest Score: {result['iso_forest_score']:.2f}")
            print(f"[INFO]   Threshold: {result['threshold']:.2f}")
            print(f"[INFO]   Template: {result['template'][:60]}...")
        
        time.sleep()  # Pause for readability
        
    except Exception as e:
        print(f"[INFO] Erreur: {e}")

def run_demo():
    print_banner()
    
    if not check_health():
        return
    
    print("[INFO] DÉMARRAGE DE LA DÉMO\n")
    input("Appuyez sur Entrée pour commencer...")
    
    # ========== SCÉNARIO  : Erreur Critique en Production ==========
    print("\n\n" + "="*80)
    print("SCÉNARIO  :  ERREUR CRITIQUE EN PRODUCTION")
    print("="*80)
    test_log(
        "Test . - OOM Kill en Production (CRITIQUE)",
        "FATAL: OOMKilled - container memory limit exceeded, pod terminated",
        "production",
        "api-server-"
    )
    
    input("\n  Appuyez sur Entrée pour continuer...")
    
    test_log(
        "Test . - CrashLoopBackOff (HAUTE PRIORITÉ)",
        "ERROR: CrashLoopBackOff - container exited with code 7, restarting",
        "production",
        "worker-pod-5"
    )
    
    # ========== SCÉNARIO  : Pattern ML Inhabituel ==========
    input("\n  Appuyez sur Entrée pour continuer...")
    print("\n\n" + "="*80)
    print("SCÉNARIO  :  DÉTECTION ML (Pattern Inhabituel)")
    print("="*80)
    
    test_log(
        "Test . - Pattern bizarre détecté par ML uniquement",
        "xyzabc unusual_request qwerty789 unexpected_behavior_detected random_string",
        "staging",
        "test-service-"
    )
    
    # ========== SCÉNARIO  : Logs Normaux ==========
    input("\n  Appuyez sur Entrée pour continuer...")
    print("\n\n" + "="*80)
    print("SCÉNARIO  :  LOGS NORMAUX (Baseline)")
    print("="*80)
    
    test_log(
        "Test . - Log INFO normal",
        "INFO: HTTP request completed successfully in 5ms, status=100",
        "production",
        "api-server-",
        show_full=False
    )
    
    test_log(
        "Test . - Log DEBUG normal",
        "DEBUG: Cache hit rate: 9%, memory usage: 50MB/GB",
        "production",
        "redis-cache-",
        show_full=False
    )
    
    # ========== SCÉNARIO  : Erreur Dev (Basse Priorité) ==========
    input("\n  Appuyez sur Entrée pour continuer...")
    print("\n\n" + "="*80)
    print("SCÉNARIO  :  ERREURS EN DEV (Priorité Basse)")
    print("="*80)
    
    test_log(
        "Test . - Erreur en environnement dev",
        "Error: connection timeout to database after 5s",
        "dev",
        "test-pod-",
        show_full=False
    )
    
    # ========== SCÉNARIO 5 : Warning ==========
    input("\n  Appuyez sur Entrée pour continuer...")
    print("\n\n" + "="*80)
    print("SCÉNARIO 5 :  WARNINGS (Surveillance)")
    print("="*80)
    
    test_log(
        "Test 5. - Warning mémoire",
        "WARN: High memory usage detected: 85% of limit, consider scaling",
        "monitoring",
        "prometheus-",
        show_full=False
    )
    
    # ========== SCÉNARIO 6 : Image Pull Error ==========
    input("\n  Appuyez sur Entrée pour continuer...")
    print("\n\n" + "="*80)
    print("SCÉNARIO 6 : 🐳 ERREUR IMAGE DOCKER")
    print("="*80)
    
    test_log(
        "Test 6. - ImagePullBackOff",
        "ERROR: ImagePullBackOff - failed to pull image my-app:v.., image not found in registry",
        "staging",
        "deployment-pod-8"
    )
    
    # ========== RÉSUMÉ FINAL ==========
    print("\n\n" + "="*80)
    print("[INFO] RÉSUMÉ DE LA DÉMO")
    print("="*80)
    print("""
 Le système a démontré :

.  Détection ML (Isolation Forest)
   • 6 features combinées (templates + context + numeric + temporal)
   • Détection de patterns inhabituels non répertoriés
   • Score normalisé 0- pour interprétabilité

.  Détection par Keywords
   •  niveaux : Critical (.0), High (0.7), Medium (0.)
   • Mots-clés métier : OOM, Crash, Error, Warning...
   • Connaissance du domaine Kubernetes

.  Analyse Temporelle
   • Détection de bursts (erreurs concentrées)
   • Accélération (trend positif = aggravation)
   • Rate 5min/5min/h pour contexte

.  Contexte Environnement
   • Production : priorité x.5
   • Staging : priorité x.
   • Dev : priorité x0.8

5.  Insights Production
   • Diagnostic automatique
   • Actions kubectl recommandées
   • Estimation de l'impact business

 Scoring Combiné Pondéré :
   ML (5%) + Keywords (0%) + Temporal (5%) + Context (0%)
    """)
    
    print("="*80)
    print("[INFO] DÉMO TERMINÉE")
    print("="*80)
    print("\n Pour tester avec vos propres logs :")
    print("[INFO]   python test_csv.py votre_fichier.csv")
    print("\n📖 Documentation complète : QUICKSTART.md")
    print("\n")

if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\n\n⏹  Démo interrompue par l'utilisateur")
    except Exception as e:
        print(f"\n Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
