#!/usr/bin/env python3
"""
Test BATCH pour detection d'anomalies avec features temporels corrects.

Ce script calcule les features temporels sur TOUT le dataset (comme l'entrainement)
au lieu d'utiliser des fenetres glissantes en temps reel.

Usage:
    python test_batch.py Wiremind_Logs_2.csv
    python test_batch.py Wiremind_Logs_2.csv --max 10000
"""

import pickle
import pandas as pd
import numpy as np
import re
import sys
import os
import argparse
from datetime import datetime
from scipy.sparse import hstack


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def print_color(text, color=Colors.RESET):
    if sys.stdout.isatty():
        print(f"{color}{text}{Colors.RESET}")
    else:
        print(text)


# Keywords critiques (meme liste que le modele)
CRITICAL_KEYWORDS = [
    'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
    'timeout', 'refused', 'denied', 'crash', 'killed',
    'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
    'outofmemory', 'segmentation fault', 'panic', 'cannot',
    'unable', 'broken', 'corrupt', 'invalid'
]

# Keywords de severite
SEVERITY_KEYWORDS = {
    'critical': ['fatal', 'panic', 'oomkilled', 'crashloopbackoff', 'segmentation fault', 'killed'],
    'high': ['error', 'exception', 'crash', 'timeout', 'refused', 'denied'],
    'medium': ['fail', 'failed', 'unable', 'cannot', 'broken', 'corrupt', 'invalid'],
    'low': ['warn', 'warning', 'deprecated']
}

# Multiplicateurs de priorite par environnement
ENV_PRIORITY = {
    'prod': 1.5,
    'production': 1.5,
    'staging': 1.2,
    'preprod': 1.2,
    'dev': 0.8,
    'development': 0.8,
    'test': 0.7,
    'default': 1.0
}


def get_severity(message, score):
    """Determine la severite basee sur le message et le score."""
    msg_lower = message.lower()
    
    # Check keywords par ordre de severite
    for severity, keywords in SEVERITY_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return severity
    
    # Sinon, basee sur le score ISO Forest
    if score < -0.05:
        return 'critical'
    elif score < -0.02:
        return 'high'
    elif score < 0:
        return 'medium'
    else:
        return 'low'


def get_priority(severity, namespace):
    """Calcule la priorite numerique (1-5, 1=plus urgent)."""
    severity_base = {'critical': 1, 'high': 2, 'medium': 3, 'low': 4}
    base = severity_base.get(severity, 3)
    
    # Ajuster selon l'environnement
    ns_lower = namespace.lower()
    multiplier = 1.0
    for env, mult in ENV_PRIORITY.items():
        if env in ns_lower:
            multiplier = mult
            break
    
    # Priorite finale (1-5)
    priority = max(1, min(5, int(base / multiplier)))
    return priority


# Keywords critiques (meme liste que le modele)
CRITICAL_KEYWORDS = [
    'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
    'timeout', 'refused', 'denied', 'crash', 'killed',
    'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
    'outofmemory', 'segmentation fault', 'panic', 'cannot',
    'unable', 'broken', 'corrupt', 'invalid'
]


def has_critical_keyword(message):
    """Verifie si un message contient un mot-cle critique."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in CRITICAL_KEYWORDS)


def redact_message(message):
    """Normalise et anonymise un message de log."""
    msg = str(message)
    msg = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "<EMAIL>", msg)
    msg = re.sub(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', "<IP>", msg)
    msg = re.sub(r'\b\d+\b', "<NUM>", msg)
    msg = re.sub(r'/[A-Za-z0-9_\-\.]+', "<PATH>", msg)
    return msg.lower()


def parse_timestamp(ts_str):
    """Parse differents formats de timestamp."""
    if pd.isna(ts_str):
        return None
    try:
        # Format Wiremind: "Nov 24, 2025 @ 14:05:37.637"
        if '@' in str(ts_str):
            ts_clean = str(ts_str).replace(' @ ', ' ')
            return pd.to_datetime(ts_clean, format='%b %d, %Y %H:%M:%S.%f')
        # Format ISO
        return pd.to_datetime(ts_str)
    except:
        return None


def calculate_temporal_features(df):
    """
    Calcule les features temporels agreges sur TOUT le dataset.
    IDENTIQUE a l'entrainement du modele (compare_approaches.py).
    
    Features temporels (7):
    - rate_5min: somme erreurs sur 5min par pod
    - rate_15min: somme erreurs sur 15min par pod  
    - rate_1h: somme erreurs sur 1h par pod
    - std_5min: ecart-type erreurs sur 5min
    - std_15min: ecart-type erreurs sur 15min
    - acceleration: rate_5min - rate_15min (augmentation recente)
    - burst_ratio: rate_5min / rate_1h (pic soudain)
    """
    print_color("  Calcul des features temporels (batch)...", Colors.DIM)
    
    # S'assurer qu'on a une colonne pod
    if 'pod' not in df.columns:
        df['pod'] = 'unknown'
    
    # Creer les fenetres temporelles
    df['timestamp_5min'] = df['timestamp'].dt.floor('5min')
    df['timestamp_15min'] = df['timestamp'].dt.floor('15min')
    df['timestamp_1h'] = df['timestamp'].dt.floor('1h')
    
    # Detecter les erreurs (meme logique que l'entrainement)
    df['has_error'] = df['message'].apply(has_critical_keyword).astype(int)
    
    # SOMME des erreurs par fenetre et par pod (comme l'entrainement)
    errors_5min = df.groupby(['pod', 'timestamp_5min'])['has_error'].sum()
    errors_15min = df.groupby(['pod', 'timestamp_15min'])['has_error'].sum()
    errors_1h = df.groupby(['pod', 'timestamp_1h'])['has_error'].sum()
    
    # Mapper les sommes sur chaque log
    df['rate_5min'] = df.set_index(['pod', 'timestamp_5min']).index.map(errors_5min).fillna(0).values
    df['rate_15min'] = df.set_index(['pod', 'timestamp_15min']).index.map(errors_15min).fillna(0).values
    df['rate_1h'] = df.set_index(['pod', 'timestamp_1h']).index.map(errors_1h).fillna(0).values
    
    # Ecart-type par fenetre
    std_5min = df.groupby(['pod', 'timestamp_5min'])['has_error'].std().fillna(0)
    std_15min = df.groupby(['pod', 'timestamp_15min'])['has_error'].std().fillna(0)
    df['std_5min'] = df.set_index(['pod', 'timestamp_5min']).index.map(std_5min).fillna(0).values
    df['std_15min'] = df.set_index(['pod', 'timestamp_15min']).index.map(std_15min).fillna(0).values
    
    # Features derives (detection de bursts)
    # acceleration > 0 = augmentation recente des erreurs
    df['acceleration'] = df['rate_5min'] - df['rate_15min']
    # burst_ratio > 1 = pic d'erreurs sur 5min par rapport a la moyenne 1h
    df['burst_ratio'] = df['rate_5min'] / (df['rate_1h'] + 1e-6)
    
    return df


def load_model(model_path):
    """Charge le modele pickle."""
    with open(model_path, 'rb') as f:
        return pickle.load(f)


def predict_batch(df, model):
    """
    Fait des predictions sur tout le dataset en batch.
    Utilise les features temporels pre-calcules.
    """
    iso_forest = model['iso_forest']
    miner = model['miner']
    vectorizer = model['vectorizer']
    encoder = model['encoder']
    threshold = model['threshold']
    
    results = []
    
    # Preparer les templates
    print_color("  Extraction des templates (Drain3)...", Colors.DIM)
    templates = []
    for msg in df['clean_message']:
        result = miner.match(msg)
        if result:
            templates.append(result.get_template())
        else:
            templates.append(msg)
    df['template'] = templates
    
    # Vectoriser les templates
    print_color("  Vectorisation...", Colors.DIM)
    X_templates = vectorizer.transform(df['template'])
    
    # Encoder le contexte (namespace, pod)
    # Le modele a ete entraine avec [namespace, pod]
    context_data = df[['namespace', 'pod']].values
    X_context = encoder.transform(context_data)
    
    # Features numeriques (identique au modele V3)
    print_color("  Calcul des features numeriques...", Colors.DIM)
    df['length'] = df['message'].apply(len)
    df['num_tokens'] = df['message'].apply(lambda x: len(str(x).split()))
    df['digit_ratio'] = df['message'].apply(lambda x: sum(c.isdigit() for c in str(x)) / (len(str(x)) + 1e-5))
    df['upper_ratio'] = df['message'].apply(lambda x: sum(c.isupper() for c in str(x)) / (len(str(x)) + 1e-5))
    df['special_ratio'] = df['message'].apply(lambda x: sum(not c.isalnum() and not c.isspace() for c in str(x)) / (len(str(x)) + 1e-5))
    df['has_error_kw'] = df['has_error'].astype(float)
    df['is_error_level'] = df['message'].apply(lambda x: 1.0 if any(lvl in str(x).upper() for lvl in ['ERROR', 'FATAL', 'CRITICAL']) else 0.0)
    df['is_warn_level'] = df['message'].apply(lambda x: 1.0 if 'WARN' in str(x).upper() else 0.0)
    df['has_traceback'] = df['message'].apply(lambda x: 1.0 if 'traceback' in str(x).lower() or 'exception' in str(x).lower() else 0.0)
    
    # Liste des features numeriques (modele V3)
    numeric_features = [
        'length', 'num_tokens', 'digit_ratio', 'upper_ratio',
        'has_error_kw', 'is_error_level', 'is_warn_level', 'has_traceback',
        'rate_5min', 'rate_15min', 'rate_1h', 'std_5min', 'std_15min',
        'acceleration', 'burst_ratio'
    ]
    
    X_numeric = df[numeric_features].values
    
    # Construire la matrice de features
    X_full = hstack([X_templates, X_context, X_numeric])
    
    print_color(f"  Matrice de features: {X_full.shape}", Colors.DIM)
    
    # Predictions ISO Forest
    print_color("  Prediction Isolation Forest...", Colors.DIM)
    scores = iso_forest.score_samples(X_full)  # score_samples pour coherence avec entrainement
    iso_anomalies = scores < threshold  # Score bas = anomalie
    print_color(f"  Scores ISO: min={scores.min():.4f}, max={scores.max():.4f}, threshold={threshold}", Colors.DIM)
    
    # Detection hybride: keywords OU ISO Forest
    print_color("  Detection hybride (Keywords + ISO Forest)...", Colors.DIM)
    keyword_anomalies = df['has_error'].values.astype(bool)
    
    # Resultats
    for i in range(len(df)):
        has_kw = keyword_anomalies[i]
        has_iso = iso_anomalies[i]
        
        is_anomaly = has_kw or has_iso
        
        if has_kw and has_iso:
            method = "hybrid_both"
            confidence = 0.95
        elif has_kw:
            method = "keyword_detection"
            confidence = 0.90
        elif has_iso:
            method = "isolation_forest"
            confidence = min(0.9, abs(threshold - scores[i]) / 0.1)
        else:
            method = "none"
            confidence = 0.0
        
        # Calcul severite et priorite
        namespace = df.iloc[i]['namespace']
        pod = df.iloc[i]['pod']
        message = df.iloc[i]['message']
        severity = get_severity(message, scores[i]) if is_anomaly else 'info'
        priority = get_priority(severity, namespace) if is_anomaly else 5
        
        results.append({
            'line': i + 1,
            'timestamp': str(df.iloc[i]['timestamp']),
            'namespace': namespace,
            'pod': pod,
            'location': f"{namespace}/{pod}",
            'message': message[:150],
            'is_anomaly': bool(is_anomaly),
            'severity': severity,
            'priority': priority,
            'score': float(scores[i]),
            'confidence': float(confidence),
            'detection_method': method,
            'temporal_metrics': {
                'burst_ratio': float(df.iloc[i]['burst_ratio']),
                'rate_5min': float(df.iloc[i]['rate_5min']),
                'rate_15min': float(df.iloc[i]['rate_15min']),
                'rate_1h': float(df.iloc[i]['rate_1h']),
                'acceleration': float(df.iloc[i]['acceleration'])
            }
        })
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Test batch avec features temporels corrects')
    parser.add_argument('csv_file', help='Fichier CSV a analyser')
    parser.add_argument('--max', type=int, default=None, help='Nombre max de logs')
    parser.add_argument('--model', default='../modeles/hybrid_model.pkl', help='Chemin du modele')
    
    args = parser.parse_args()
    
    print_color("\n" + "=" * 80, Colors.BLUE)
    print_color("  DETECTION D'ANOMALIES - Mode BATCH (features temporels corrects)", Colors.BOLD)
    print_color("=" * 80, Colors.BLUE)
    
    # 1. Charger le CSV
    print_color("\n[1/5] Chargement du CSV...", Colors.BLUE)
    
    df = pd.read_csv(args.csv_file, nrows=args.max)
    print_color(f"  {len(df):,} logs charges", Colors.GREEN)
    
    # Detecter les colonnes
    if 'wiremind.message' in df.columns:
        df['message'] = df['wiremind.message']
    if 'kubernetes.namespace_name' in df.columns:
        df['namespace'] = df['kubernetes.namespace_name']
    else:
        df['namespace'] = 'default'
    if 'kubernetes.pod_name' in df.columns:
        df['pod'] = df['kubernetes.pod_name']
    else:
        df['pod'] = 'unknown'
    if '@timestamp' in df.columns:
        df['timestamp'] = df['@timestamp'].apply(parse_timestamp)
    else:
        df['timestamp'] = pd.Timestamp.now()
    
    # Nettoyer les messages
    df['clean_message'] = df['message'].apply(redact_message)
    
    print_color(f"  Periode: {df['timestamp'].min()} -> {df['timestamp'].max()}", Colors.DIM)
    
    # 2. Calculer les features temporels (BATCH)
    print_color("\n[2/5] Calcul des features temporels...", Colors.BLUE)
    df = calculate_temporal_features(df)
    
    print_color(f"  rate_5min: min={df['rate_5min'].min():.1f}, max={df['rate_5min'].max():.1f}, mean={df['rate_5min'].mean():.2f}", Colors.DIM)
    print_color(f"  burst_ratio: min={df['burst_ratio'].min():.2f}, max={df['burst_ratio'].max():.2f}, mean={df['burst_ratio'].mean():.2f}", Colors.DIM)
    print_color(f"  acceleration: min={df['acceleration'].min():.2f}, max={df['acceleration'].max():.2f}", Colors.DIM)
    
    # 3. Charger le modele
    print_color("\n[3/5] Chargement du modele...", Colors.BLUE)
    model_path = os.path.join(os.path.dirname(__file__), args.model)
    model = load_model(model_path)
    print_color(f"  Modele: {model.get('version', 'unknown')}", Colors.GREEN)
    print_color(f"  Features attendus: {model['iso_forest'].n_features_in_}", Colors.DIM)
    print_color(f"  Threshold: {model['threshold']}", Colors.DIM)
    
    # 4. Predictions
    print_color("\n[4/5] Predictions...", Colors.BLUE)
    results = predict_batch(df, model)
    
    # 5. Resultats
    print_color("\n[5/5] Analyse des resultats...", Colors.BLUE)
    
    anomalies = [r for r in results if r['is_anomaly']]
    
    # Stats par methode
    stats = {}
    severity_stats = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
    for r in results:
        m = r['detection_method']
        stats[m] = stats.get(m, 0) + 1
        if r['is_anomaly']:
            severity_stats[r['severity']] = severity_stats.get(r['severity'], 0) + 1
    
    print_color("\n" + "=" * 80, Colors.BLUE)
    print_color("  RESULTATS DE DETECTION", Colors.BOLD)
    print_color("=" * 80, Colors.BLUE)
    
    print_color(f"\n  Logs analyses:    {len(results):,}", Colors.GREEN)
    print_color(f"  Anomalies:        {len(anomalies):,} ({100*len(anomalies)/len(results):.2f}%)", Colors.RED)
    
    # Stats par severite
    print_color("\n  PAR SEVERITE:", Colors.CYAN)
    severity_emoji = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}
    for sev in ['critical', 'high', 'medium', 'low']:
        if severity_stats.get(sev, 0) > 0:
            print_color(f"    {severity_emoji[sev]} {sev.upper():10s}: {severity_stats[sev]:,}", 
                       Colors.RED if sev == 'critical' else (Colors.YELLOW if sev in ['high', 'medium'] else Colors.GREEN))
    
    print_color("\n  PAR METHODE:", Colors.CYAN)
    if stats.get('keyword_detection', 0) > 0:
        print_color(f"    [KW] Mots-cles:        {stats['keyword_detection']:,}", Colors.YELLOW)
    if stats.get('isolation_forest', 0) > 0:
        print_color(f"    [IF] Isolation Forest: {stats['isolation_forest']:,}", Colors.MAGENTA)
    if stats.get('hybrid_both', 0) > 0:
        print_color(f"    [!!] Hybride (les 2):  {stats['hybrid_both']:,}", Colors.RED)
    if stats.get('none', 0) > 0:
        print_color(f"    [OK] Normal:           {stats['none']:,}", Colors.GREEN)
    
    # Afficher les anomalies par priorite
    print_color("\n" + "=" * 80, Colors.RED)
    print_color("  ANOMALIES PAR PRIORITE", Colors.BOLD)
    print_color("=" * 80, Colors.RED)
    
    # Trier par priorite (1=urgent) puis par score
    sorted_anomalies = sorted(anomalies, key=lambda x: (x['priority'], x['score']))[:30]
    
    for a in sorted_anomalies:
        ts = a['timestamp'].split()[1][:8] if ' ' in a['timestamp'] else a['timestamp'][:8]
        emoji = severity_emoji.get(a['severity'], '⚪')
        burst = a['temporal_metrics']['burst_ratio']
        burst_str = f"⚡{burst:.1f}" if burst > 1.0 else f"  {burst:.1f}"
        
        # Couleur selon priorite
        if a['priority'] <= 1:
            color = Colors.RED
        elif a['priority'] <= 2:
            color = Colors.YELLOW
        elif a['priority'] <= 3:
            color = Colors.CYAN
        else:
            color = Colors.DIM
        
        print_color(f"  {emoji} P{a['priority']} | {ts} | {burst_str} | {a['location'][:30]:30s} | {a['message'][:40]}...", color)
    
    # Anomalies critiques
    critical = [a for a in anomalies if a['severity'] == 'critical']
    if critical:
        print_color(f"\n  ⚠️  ANOMALIES CRITIQUES: {len(critical)}", Colors.RED + Colors.BOLD)
        print_color("-" * 80, Colors.DIM)
        for a in sorted(critical, key=lambda x: x['priority'])[:15]:
            ts = a['timestamp'].split()[1][:8] if ' ' in a['timestamp'] else a['timestamp'][:8]
            print_color(f"  🔴 P{a['priority']} | {ts} | {a['location'][:25]:25s} | {a['message'][:50]}...", Colors.RED)
    
    # Anomalies ISO Forest pures (patterns rares)
    iso_only = [a for a in anomalies if a['detection_method'] == 'isolation_forest']
    if iso_only:
        print_color(f"\n  🔮 PATTERNS RARES (ISO Forest): {len(iso_only)}", Colors.MAGENTA)
        print_color("-" * 80, Colors.DIM)
        for a in sorted(iso_only, key=lambda x: x['score'])[:10]:
            ts = a['timestamp'].split()[1][:8] if ' ' in a['timestamp'] else a['timestamp'][:8]
            print_color(f"  🔮 P{a['priority']} | {ts} | score={a['score']:.3f} | {a['location'][:25]:25s} | {a['message'][:40]}...", Colors.MAGENTA)
    
    # Sauvegarder
    import json
    
    # Stats pour burst
    burst_anomalies = [a for a in anomalies if a['temporal_metrics']['burst_ratio'] > 1.0]
    
    output_file = args.csv_file.replace('.csv', '_batch_results.json')
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_logs': len(results),
                'anomalies': len(anomalies),
                'rate': 100 * len(anomalies) / len(results),
                'severity': severity_stats,
                'methods': stats,
                'burst_anomalies': len(burst_anomalies),
                'critical_count': severity_stats.get('critical', 0),
                'high_count': severity_stats.get('high', 0)
            },
            'anomalies': anomalies
        }, f, indent=2, default=str)
    
    print_color(f"\n  📁 Resultats: {output_file}", Colors.GREEN)
    print_color("=" * 80 + "\n", Colors.BLUE)


if __name__ == '__main__':
    main()
