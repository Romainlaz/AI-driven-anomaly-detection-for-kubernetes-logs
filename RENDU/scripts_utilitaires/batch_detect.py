#!/usr/bin/env python
"""
Batch Anomaly Detection Script
Traite un fichier de logs et génère un rapport de détection
"""
import json
import requests
import argparse
from pathlib import Path
from collections import Counter, defaultdict
import time


def process_logs(input_file, api_url="http://localhost:8080/predict", output_file=None):
    """
    Traite un fichier de logs et génère un rapport
    
    Format d'entrée attendu (JSONL):
    {"message": "...", "namespace": "...", "pod": "...", "timestamp": "..."}
    
    Ou CSV avec colonnes: message,namespace,pod,timestamp
    """
    print(f"[INFO] Lecture de {input_file}...")
    
    results = []
    anomalies = []
    detection_methods = Counter()
    confidence_distribution = defaultdict(int)
    
    # Détection du format
    is_jsonl = input_file.suffix == '.jsonl'
    
    with open(input_file, 'r') as f:
        if is_jsonl:
            # Format JSONL
            logs = [json.loads(line) for line in f if line.strip()]
        else:
            # Format CSV
            import csv
            reader = csv.DictReader(f)
            logs = list(reader)
    
    print(f"[INFO]   Total logs: {len(logs)}")
    print(f"\n Analyse en cours...")
    
    start_time = time.time()
    
    for i, log in enumerate(logs, ):
        # Préparation du payload
        payload = {
            "message": log.get("message", log.get("wiremind.message", "")),
            "namespace": log.get("namespace", log.get("kubernetes.namespace_name", "unknown")),
            "pod": log.get("pod", log.get("kubernetes.pod_name", "unknown")),
        }
        
        try:
            # Appel API
            response = requests.post(api_url, json=payload, timeout=5)
            response.raise_for_status()
            result = response.json()
            
            # Ajout du message original
            result['original_message'] = payload['message']
            result['namespace'] = payload['namespace']
            result['pod'] = payload['pod']
            
            results.append(result)
            
            # Statistiques
            if result['is_anomaly']:
                anomalies.append(result)
                detection_methods[result.get('detection_method', 'unknown')] += 1
                
                # Distribution de confiance
                conf_bucket = int(result['confidence'] * 10) / 10
                confidence_distribution[conf_bucket] += 1
            
            # Progress
            if i % 100 == 0:
                print(f"[INFO]   Traité {i}/{len(logs)} logs ({len(anomalies)} anomalies)")
        
        except Exception as e:
            print(f"[INFO]     Erreur log {i}: {e}")
            continue
    
    elapsed = time.time() - start_time
    
    # Rapport
    print(f"\n{'='*80}")
    print(f"[INFO] RAPPORT DE DÉTECTION")
    print(f"{'='*80}")
    print(f"\n Statistiques générales:")
    print(f"[INFO]   Total logs traités:    {len(results)}")
    print(f"[INFO]   Anomalies détectées:   {len(anomalies)} ({len(anomalies)/len(results)*100:.2f}%)")
    print(f"[INFO]   Temps total:           {elapsed:.2f}s")
    print(f"[INFO]   Débit:                 {len(results)/elapsed:.2f} logs/sec")
    
    print(f"\n Méthodes de détection:")
    for method, count in detection_methods.most_common():
        print(f"[INFO]   {method:20s}: {count:>5} ({count/len(anomalies)*100:>5.1f}%)")
    
    print(f"\n Distribution de confiance (anomalies):")
    for conf in sorted(confidence_distribution.keys(), reverse=True):
        count = confidence_distribution[conf]
        bar = "█" * int(count / max(confidence_distribution.values()) * 20)
        print(f"[INFO]   {conf:.2f}: {bar} {count}")
    
    # Top 0 anomalies par confiance
    print(f"\nTop 0 anomalies (confiance la plus élevée):")
    top_anomalies = sorted(anomalies, key=lambda x: x['confidence'], reverse=True)[:0]
    for i, a in enumerate(top_anomalies, ):
        msg = a['original_message'][:70]
        conf = a['confidence']
        method = a.get('detection_method', 'unknown')
        print(f"[INFO]   {i:}. [{conf:.2f}] [{method:5s}] {msg}")
    
    # Sauvegarde des résultats
    if output_file:
        output_path = Path(output_file)
        
        # JSON complet
        with open(output_path, 'w') as f:
            json.dump({
                'summary': {
                    'total_logs': len(results),
                    'anomalies_count': len(anomalies),
                    'anomaly_rate': len(anomalies) / len(results),
                    'detection_methods': dict(detection_methods),
                    'elapsed_seconds': elapsed
                },
                'anomalies': anomalies,
                'all_results': results
            }, f, indent=2)
        
        print(f"\n Résultats sauvegardés: {output_path}")
        
        # CSV des anomalies uniquement
        csv_path = output_path.with_suffix('.csv')
        with open(csv_path, 'w') as f:
            import csv
            writer = csv.DictWriter(f, fieldnames=[
                'confidence', 'detection_method', 'score', 'namespace', 'pod', 'original_message'
            ])
            writer.writeheader()
            for a in sorted(anomalies, key=lambda x: x['confidence'], reverse=True):
                writer.writerow({
                    'confidence': a['confidence'],
                    'detection_method': a.get('detection_method', 'unknown'),
                    'score': a['score'],
                    'namespace': a['namespace'],
                    'pod': a['pod'],
                    'original_message': a['original_message']
                })
        
        print(f"[INFO] Anomalies CSV: {csv_path}")
    
    print(f"\n{'='*80}")
    
    return results, anomalies


def main():
    parser = argparse.ArgumentParser(
        description="Batch anomaly detection on log files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyser un fichier JSONL
  python batch_detect.py logs.jsonl -o results.json
  
  # Analyser un CSV
  python batch_detect.py logs.csv -o results.json
  
  # Utiliser une API distante
  python batch_detect.py logs.jsonl --api http://remote:8080/predict
        """
    )
    
    parser.add_argument('input', type=str, help='Input log file (JSONL or CSV)')
    parser.add_argument('-o', '--output', type=str, help='Output JSON file for results')
    parser.add_argument('--api', type=str, default='http://localhost:8080/predict',
                       help='Anomaly detection API URL (default: http://localhost:8080/predict)')
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[INFO] Erreur: Fichier {input_path} introuvable")
        return 
    
    try:
        results, anomalies = process_logs(input_path, args.api, args.output)
        return 0
    except Exception as e:
        print(f"[INFO] Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 


if __name__ == '__main__':
    exit(main())
