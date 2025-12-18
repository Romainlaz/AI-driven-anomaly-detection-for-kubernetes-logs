#!/usr/bin/env python3
"""
Script de test CSV pour la detection d'anomalies avec affichage temps reel.

Usage:
    python test_csv.py mon_fichier.csv
    python test_csv.py mon_fichier.csv --url http://localhost:8080 --max 100

Formats CSV supportes:
    1. Format Wiremind (3 colonnes):
       @timestamp,wiremind.message,kubernetes.namespace_name

    2. Format simple (3+ colonnes):
       message,namespace,pod
"""

import csv
import json
import sys
import os
import argparse
import urllib.request
import urllib.error
import time
from datetime import datetime


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def print_color(text, color=Colors.RESET):
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.RESET}")
    else:
        print(text)


def check_csv_format(csv_path):
    """Detecte les colonnes du CSV."""
    errors = []
    column_mapping = {}
    
    if not os.path.exists(csv_path):
        errors.append(f"Le fichier '{csv_path}' n'existe pas")
        return None, errors
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            sample = f.read(4096)
            f.seek(0)
            
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
            except csv.Error:
                delimiter = ','
            
            reader = csv.DictReader(f, delimiter=delimiter)
            headers = reader.fieldnames
            
            if not headers:
                errors.append("Le fichier CSV est vide ou n'a pas d'en-tete")
                return None, errors
            
            headers_lower = [h.lower().strip() for h in headers]
            
            # Colonne message
            for candidate in ['message', 'wiremind.message', 'log', 'text']:
                if candidate in headers_lower:
                    idx = headers_lower.index(candidate)
                    column_mapping['message'] = headers[idx]
                    break
            
            if 'message' not in column_mapping:
                errors.append(f"Colonne 'message' non trouvee. Colonnes: {headers}")
                return None, errors
            
            # Colonne timestamp
            for candidate in ['@timestamp', 'timestamp', 'time', 'date']:
                if candidate in headers_lower:
                    idx = headers_lower.index(candidate)
                    column_mapping['timestamp'] = headers[idx]
                    break
            
            # Colonne namespace
            for candidate in ['namespace', 'kubernetes.namespace_name', 'ns']:
                if candidate in headers_lower:
                    idx = headers_lower.index(candidate)
                    column_mapping['namespace'] = headers[idx]
                    break
            
            # Colonne pod (optionnelle - pas d'avertissement)
            for candidate in ['pod', 'kubernetes.pod_name', 'pod_name']:
                if candidate in headers_lower:
                    idx = headers_lower.index(candidate)
                    column_mapping['pod'] = headers[idx]
                    break
            
            # Compter les lignes
            f.seek(0)
            line_count = sum(1 for _ in f) - 1
            if line_count == 0:
                errors.append("Le fichier CSV ne contient aucune ligne de donnees")
                return None, errors
            
            column_mapping['line_count'] = line_count
            column_mapping['delimiter'] = delimiter
            
    except UnicodeDecodeError:
        errors.append("Erreur d'encodage - le fichier doit etre en UTF-8")
        return None, errors
    except Exception as e:
        errors.append(f"Erreur lors de la lecture du CSV: {str(e)}")
        return None, errors
    
    return column_mapping, errors


def check_api_health(api_url):
    """Verifie que l'API est accessible."""
    try:
        req = urllib.request.urlopen(f"{api_url}/health", timeout=10)
        data = json.loads(req.read().decode())
        if not data.get('model_loaded', False):
            return False, "Modele non charge"
        return True, data
    except urllib.error.URLError as e:
        return False, f"API inaccessible: {e.reason}"
    except Exception as e:
        return False, str(e)


def format_anomaly(line_num, result, namespace, pod, timestamp=None):
    """Formate l'affichage d'une anomalie en temps reel."""
    method = result.get('detection_method', 'unknown')
    score = result.get('score', 0)
    confidence = result.get('confidence', 0)
    message = result.get('message', '')[:80]
    
    # Couleur selon la methode
    if method == 'hybrid_both':
        method_color = Colors.RED
        method_icon = "!!"
        priority = 1
    elif method == 'keyword_detection':
        method_color = Colors.YELLOW
        method_icon = "KW"
        priority = 2
    elif method == 'isolation_forest':
        method_color = Colors.MAGENTA
        method_icon = "IF"
        priority = 3
    else:
        method_color = Colors.DIM
        method_icon = "--"
        priority = 5
    
    # Ajuster priorité selon le score
    if score < -0.1:
        priority = max(1, priority - 1)
    
    # Format location
    location = f"{namespace}"
    if pod and pod != 'unknown':
        location += f"/{pod}"
    
    # Affichage format: priority | score | log | location | méthode
    priority_icons = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⚪"}
    priority_icon = priority_icons.get(priority, "⚪")
    
    # Tronquer le message à 80 caractères
    msg_display = message[:80] + "..." if len(message) > 80 else message
    
    print_color(f"  {priority_icon} P{priority} | score:{score:+.4f} | {msg_display}", method_color)
    print_color(f"       └─ location: {location} | method: {method}", Colors.DIM)


def test_csv(csv_path, api_url, max_logs=None):
    """Teste un fichier CSV avec affichage temps reel des anomalies."""
    
    print_color("\n" + "=" * 80, Colors.BLUE)
    print_color("  DETECTION D'ANOMALIES - Mode Streaming", Colors.BOLD)
    print_color("=" * 80, Colors.BLUE)
    
    # 1. Verifier le CSV
    print_color("\n[1/3] Chargement du fichier CSV...", Colors.BLUE)
    column_mapping, errors = check_csv_format(csv_path)
    
    if errors:
        for err in errors:
            print_color(f"  ERREUR: {err}", Colors.RED)
        return False
    
    print_color(f"  Fichier: {os.path.basename(csv_path)}", Colors.GREEN)
    print_color(f"  Lignes: {column_mapping['line_count']}", Colors.GREEN)
    print_color(f"  Colonnes: message={column_mapping['message']}", Colors.DIM)
    if 'timestamp' in column_mapping:
        print_color(f"           timestamp={column_mapping['timestamp']}", Colors.DIM)
    if 'namespace' in column_mapping:
        print_color(f"           namespace={column_mapping['namespace']}", Colors.DIM)
    if 'pod' in column_mapping:
        print_color(f"           pod={column_mapping['pod']}", Colors.DIM)
    
    # 2. Verifier l'API
    print_color("\n[2/3] Connexion a l'API...", Colors.BLUE)
    api_ok, api_result = check_api_health(api_url)
    
    if not api_ok:
        print_color(f"  ERREUR: {api_result}", Colors.RED)
        print_color("  Lancez: docker compose up -d", Colors.YELLOW)
        return False
    
    print_color(f"  API: {api_url} [OK]", Colors.GREEN)
    
    # 3. Streaming des logs
    print_color("\n[3/3] Analyse en cours...", Colors.BLUE)
    print_color("  Legende: [KW]=Keyword [IF]=IsolationForest [!!]=Les deux", Colors.DIM)
    print_color("-" * 80, Colors.DIM)
    
    results = []
    anomalies = []
    errors_count = 0
    
    # Stats par methode
    stats = {
        'keyword_detection': 0,
        'isolation_forest': 0,
        'hybrid_both': 0,
        'none': 0
    }
    
    total_logs = min(column_mapping['line_count'], max_logs) if max_logs else column_mapping['line_count']
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=column_mapping['delimiter'])
        start_time = time.time()
        last_progress = 0
        
        for i, row in enumerate(reader, 1):
            if max_logs and i > max_logs:
                break
            
            # Extraire les valeurs
            message = row.get(column_mapping['message'], '').strip()
            timestamp = row.get(column_mapping.get('timestamp', ''), None)
            namespace = row.get(column_mapping.get('namespace', ''), 'default') or 'default'
            pod = row.get(column_mapping.get('pod', ''), 'unknown') or 'unknown'
            
            if not message:
                continue
            
            try:
                log_entry = {
                    "message": message,
                    "namespace": namespace,
                    "pod": pod,
                    "timestamp": timestamp
                }
                
                req = urllib.request.Request(
                    f"{api_url}/predict",
                    data=json.dumps(log_entry).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                
                response = urllib.request.urlopen(req, timeout=10)
                result = json.loads(response.read().decode())
                result['message'] = message
                
                method = result.get('detection_method', 'none')
                stats[method] = stats.get(method, 0) + 1
                
                results.append({
                    'line': i,
                    'is_anomaly': result.get('is_anomaly', False),
                    'score': result.get('score', 0),
                    'confidence': result.get('confidence', 0),
                    'detection_method': method
                })
                
                if result.get('is_anomaly'):
                    # Calcul de la priorité
                    method = result.get('detection_method', 'none')
                    score = result.get('score', 0)
                    if method == 'hybrid_both':
                        priority = 1
                    elif method == 'keyword_detection':
                        priority = 2
                    elif method == 'isolation_forest':
                        priority = 3
                    else:
                        priority = 5
                    if score < -0.1:
                        priority = max(1, priority - 1)
                    
                    anomalies.append({
                        'priority': priority,
                        'score': result.get('score', 0),
                        'log': message,
                        'location': {
                            'namespace': namespace,
                            'pod': pod
                        },
                        'method': method,
                        'line': i,
                        'timestamp': timestamp,
                        'confidence': result.get('confidence', 0),
                        'template': result.get('template', '')
                    })
                    
                    # Affichage temps reel
                    format_anomaly(i, result, namespace, pod, timestamp)
                
            except Exception as e:
                errors_count += 1
            
            # Progression toutes les 500 lignes
            if i - last_progress >= 500:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                pct = 100 * i / total_logs
                anom_rate = 100 * len(anomalies) / i if i > 0 else 0
                print_color(f"  ... {i}/{total_logs} ({pct:.0f}%) - {len(anomalies)} anomalies ({anom_rate:.1f}%) - {rate:.0f} logs/s", Colors.DIM)
                last_progress = i
    
    elapsed_total = time.time() - start_time
    
    # Resultats
    print_color("-" * 80, Colors.DIM)
    print_color("\n" + "=" * 80, Colors.BLUE)
    print_color("  RESULTATS", Colors.BOLD)
    print_color("=" * 80, Colors.BLUE)
    
    print_color(f"\n  Logs analyses:    {len(results):,}", Colors.GREEN)
    print_color(f"  Anomalies:        {len(anomalies):,} ({100*len(anomalies)/max(len(results), 1):.2f}%)", Colors.RED if anomalies else Colors.GREEN)
    print_color(f"  Erreurs API:      {errors_count}", Colors.YELLOW if errors_count else Colors.GREEN)
    print_color(f"  Temps:            {elapsed_total:.1f}s ({len(results)/elapsed_total:.0f} logs/s)", Colors.BLUE)
    
    # Stats par methode
    print_color("\n  DETECTION PAR METHODE:", Colors.CYAN)
    if stats['keyword_detection'] > 0:
        print_color(f"    [KW] Mots-cles:        {stats['keyword_detection']:,}", Colors.YELLOW)
    if stats['isolation_forest'] > 0:
        print_color(f"    [IF] Isolation Forest: {stats['isolation_forest']:,}", Colors.MAGENTA)
    if stats['hybrid_both'] > 0:
        print_color(f"    [!!] Hybride (les 2):  {stats['hybrid_both']:,}", Colors.RED)
    
    # Features temporels utilises?
    if 'timestamp' in column_mapping:
        print_color(f"\n  Features temporels: ACTIFS (timestamps disponibles)", Colors.GREEN)
    else:
        print_color(f"\n  Features temporels: Partiels (pas de timestamps dans le CSV)", Colors.YELLOW)
    
    # Sauvegarder
    output_file = csv_path.replace('.csv', '_anomalies.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'file': csv_path,
                'total_logs': len(results),
                'anomalies_count': len(anomalies),
                'anomaly_rate': 100*len(anomalies)/max(len(results), 1),
                'detection_methods': stats,
                'temporal_features': 'timestamp' in column_mapping,
                'timestamp': datetime.now().isoformat()
            },
            'anomalies': anomalies
        }, f, indent=2, ensure_ascii=False)
    
    print_color(f"\n  Resultats: {output_file}", Colors.GREEN)
    print_color("=" * 80 + "\n", Colors.BLUE)
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Test CSV avec detection d\'anomalies')
    parser.add_argument('csv_file', help='Fichier CSV a analyser')
    parser.add_argument('--url', default='http://localhost:8080', help='URL de l\'API')
    parser.add_argument('--max', type=int, default=None, help='Nombre max de logs')
    
    args = parser.parse_args()
    success = test_csv(args.csv_file, args.url, args.max)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
