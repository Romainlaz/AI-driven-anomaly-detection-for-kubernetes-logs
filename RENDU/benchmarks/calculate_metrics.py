#!/usr/bin/env python3
"""
Calcul de métriques fiables sur dataset labellisé.
Utilise le dataset kubernetes_logs_labeled.csv avec ground truth.
"""

import pickle
import pandas as pd
import numpy as np
import sys
import os
import re
from datetime import datetime
from scipy.sparse import hstack
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    accuracy_score, confusion_matrix, classification_report,
    precision_recall_curve, roc_auc_score, average_precision_score
)

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, '..', 'modeles', 'hybrid_model.pkl')


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


def print_color(text, color=Colors.RESET):
    print(f"{color}{text}{Colors.RESET}")


# Keywords critiques (identique au modèle)
CRITICAL_KEYWORDS = [
    'error', 'fail', 'failed', 'exception', 'fatal', 'critical',
    'timeout', 'refused', 'denied', 'crash', 'killed',
    'oomkilled', 'crashloopbackoff', 'imagepullbackoff',
    'outofmemory', 'segmentation fault', 'panic', 'cannot',
    'unable', 'broken', 'corrupt', 'invalid'
]


def has_critical_keyword(message):
    """Vérifie si un message contient un mot-clé critique."""
    msg_lower = str(message).lower()
    return any(kw in msg_lower for kw in CRITICAL_KEYWORDS)


def redact_message(message):
    """Normalise et anonymise un message de log."""
    msg = str(message)
    msg = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', "<EMAIL>", msg)
    msg = re.sub(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', "<IP>", msg)
    msg = re.sub(r'\b\d+\b', "<NUM>", msg)
    msg = re.sub(r'/[A-Za-z0-9_\-\.]+', "<PATH>", msg)
    return msg.lower()


def calculate_temporal_features(df):
    """Calcule les features temporels (batch mode)."""
    if 'pod' not in df.columns:
        df['pod'] = 'unknown'
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['timestamp_5min'] = df['timestamp'].dt.floor('5min')
    df['timestamp_15min'] = df['timestamp'].dt.floor('15min')
    df['timestamp_1h'] = df['timestamp'].dt.floor('1h')
    
    df['has_error'] = df['message'].apply(has_critical_keyword).astype(int)
    
    errors_5min = df.groupby(['pod', 'timestamp_5min'])['has_error'].sum()
    errors_15min = df.groupby(['pod', 'timestamp_15min'])['has_error'].sum()
    errors_1h = df.groupby(['pod', 'timestamp_1h'])['has_error'].sum()
    
    df['rate_5min'] = df.set_index(['pod', 'timestamp_5min']).index.map(errors_5min).fillna(0).values
    df['rate_15min'] = df.set_index(['pod', 'timestamp_15min']).index.map(errors_15min).fillna(0).values
    df['rate_1h'] = df.set_index(['pod', 'timestamp_1h']).index.map(errors_1h).fillna(0).values
    
    std_5min = df.groupby(['pod', 'timestamp_5min'])['has_error'].std().fillna(0)
    std_15min = df.groupby(['pod', 'timestamp_15min'])['has_error'].std().fillna(0)
    df['std_5min'] = df.set_index(['pod', 'timestamp_5min']).index.map(std_5min).fillna(0).values
    df['std_15min'] = df.set_index(['pod', 'timestamp_15min']).index.map(std_15min).fillna(0).values
    
    df['acceleration'] = df['rate_5min'] - df['rate_15min']
    df['burst_ratio'] = df['rate_5min'] / (df['rate_1h'] + 1e-6)
    
    return df


def load_model():
    """Charge le modèle."""
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)


def predict_batch(df, model):
    """Prédit les anomalies sur un batch."""
    iso_forest = model['iso_forest']
    miner = model['miner']
    vectorizer = model['vectorizer']
    encoder = model['encoder']
    threshold = model['threshold']
    
    # Templates Drain3
    templates = []
    for msg in df['clean_message']:
        result = miner.match(msg)
        templates.append(result.get_template() if result else msg)
    df['template'] = templates
    
    # Vectorisation
    X_templates = vectorizer.transform(df['template'])
    
    # Contexte
    context_data = df[['namespace', 'pod']].values
    X_context = encoder.transform(context_data)
    
    # Features numériques
    df['length'] = df['message'].apply(len)
    df['num_tokens'] = df['message'].apply(lambda x: len(str(x).split()))
    df['digit_ratio'] = df['message'].apply(lambda x: sum(c.isdigit() for c in str(x)) / (len(str(x)) + 1e-5))
    df['upper_ratio'] = df['message'].apply(lambda x: sum(c.isupper() for c in str(x)) / (len(str(x)) + 1e-5))
    df['special_ratio'] = df['message'].apply(lambda x: sum(not c.isalnum() and not c.isspace() for c in str(x)) / (len(str(x)) + 1e-5))
    df['has_error_kw'] = df['message'].apply(has_critical_keyword).astype(float)
    df['word_density'] = df['num_tokens'] / (df['length'] + 1)
    df['has_stack_trace'] = df['message'].apply(lambda x: 1.0 if 'at ' in str(x) and '(' in str(x) else 0.0)
    
    numeric_features = ['length', 'num_tokens', 'digit_ratio', 'upper_ratio', 
                        'special_ratio', 'has_error_kw', 'word_density', 'has_stack_trace',
                        'rate_5min', 'rate_15min', 'rate_1h', 'std_5min', 'std_15min',
                        'acceleration', 'burst_ratio']
    
    X_numeric = df[numeric_features].values
    
    # Combiner features
    X_combined = hstack([X_templates, X_context, X_numeric])
    
    # Prédictions ISO Forest
    scores = iso_forest.score_samples(X_combined)
    iso_predictions = scores < threshold
    
    # Détection hybride
    keyword_flags = df['message'].apply(has_critical_keyword).values
    
    # Résultats
    results = []
    for i in range(len(df)):
        is_anomaly = iso_predictions[i] or keyword_flags[i]
        method = 'none'
        if iso_predictions[i] and keyword_flags[i]:
            method = 'hybrid_both'
        elif keyword_flags[i]:
            method = 'keyword_detection'
        elif iso_predictions[i]:
            method = 'isolation_forest'
        
        results.append({
            'is_anomaly': is_anomaly,
            'score': float(scores[i]),
            'method': method,
            'keyword_match': keyword_flags[i],
            'iso_forest_anomaly': iso_predictions[i]
        })
    
    return results


def main():
    print_color("=" * 70, Colors.CYAN)
    print_color("  CALCUL DES MÉTRIQUES - Dataset Labellisé", Colors.CYAN)
    print_color("=" * 70, Colors.CYAN)
    
    # Charger dataset labellisé
    dataset_path = os.path.join(SCRIPT_DIR, '..', '..', 'test', 'kubernetes_logs_labeled.csv')
    if not os.path.exists(dataset_path):
        print_color(f"❌ Dataset non trouvé: {dataset_path}", Colors.RED)
        sys.exit(1)
    
    print(f"\n[1/4] Chargement du dataset labellisé...")
    df = pd.read_csv(dataset_path)
    
    # Renommer colonnes pour compatibilité
    df = df.rename(columns={
        'wiremind.message': 'message',
        'kubernetes.namespace_name': 'namespace',
        'kubernetes.pod_name': 'pod'
    })
    
    # Ground truth
    y_true = (df['label'] == 'ANOMALIE').astype(int).values
    
    print(f"  Total: {len(df)} logs")
    print(f"  Anomalies (ground truth): {y_true.sum()} ({100*y_true.mean():.1f}%)")
    print(f"  Normal: {len(df) - y_true.sum()}")
    
    # Prétraitement
    print(f"\n[2/4] Prétraitement...")
    df['clean_message'] = df['message'].apply(redact_message)
    df = calculate_temporal_features(df)
    
    # Charger modèle
    print(f"\n[3/4] Chargement du modèle...")
    model = load_model()
    print(f"  Features: {model['iso_forest'].n_features_in_}")
    print(f"  Threshold: {model['threshold']}")
    
    # Prédictions
    print(f"\n[4/4] Prédictions...")
    results = predict_batch(df, model)
    
    # Extraire prédictions
    y_pred = np.array([r['is_anomaly'] for r in results]).astype(int)
    scores = np.array([r['score'] for r in results])
    methods = [r['method'] for r in results]
    
    # ========== MÉTRIQUES ==========
    print_color("\n" + "=" * 70, Colors.GREEN)
    print_color("  MÉTRIQUES DE PERFORMANCE", Colors.GREEN)
    print_color("=" * 70, Colors.GREEN)
    
    # Métriques de base
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)
    
    print(f"\n  {'Métrique':<20} {'Valeur':>10} {'Objectif':>12} {'Status':>10}")
    print(f"  {'-'*52}")
    print(f"  {'Precision':<20} {precision:>10.2%} {'>75%':>12} {'✅' if precision >= 0.75 else '❌':>10}")
    print(f"  {'Recall':<20} {recall:>10.2%} {'>70%':>12} {'✅' if recall >= 0.70 else '❌':>10}")
    print(f"  {'F1-Score':<20} {f1:>10.2%} {'>0.70':>12} {'✅' if f1 >= 0.70 else '❌':>10}")
    print(f"  {'Accuracy':<20} {accuracy:>10.2%} {'>85%':>12} {'✅' if accuracy >= 0.85 else '❌':>10}")
    
    # ROC-AUC (utiliser les scores inversés car score < 0 = anomalie)
    try:
        roc_auc = roc_auc_score(y_true, -scores)
        avg_precision = average_precision_score(y_true, -scores)
        print(f"  {'ROC-AUC':<20} {roc_auc:>10.2%} {'>0.80':>12} {'✅' if roc_auc >= 0.80 else '⚠️':>10}")
        print(f"  {'Avg Precision':<20} {avg_precision:>10.2%} {'>0.60':>12} {'✅' if avg_precision >= 0.60 else '⚠️':>10}")
    except Exception as e:
        print(f"  ROC-AUC: Erreur - {e}")
    
    # Matrice de confusion
    print_color("\n  MATRICE DE CONFUSION", Colors.YELLOW)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    print(f"""
                    Prédit
                  NEG    POS
  Réel  NEG    {tn:5d}  {fp:5d}   (FP Rate: {fp/(tn+fp):.1%})
        POS    {fn:5d}  {tp:5d}   (FN Rate: {fn/(fn+tp):.1%})
    """)
    
    # Détails par méthode
    print_color("  DÉTECTION PAR MÉTHODE", Colors.YELLOW)
    method_counts = pd.Series(methods).value_counts()
    for method, count in method_counts.items():
        if method != 'none':
            # Calculer précision par méthode
            method_mask = np.array([m == method for m in methods])
            method_tp = np.sum((y_true == 1) & method_mask & (y_pred == 1))
            method_fp = np.sum((y_true == 0) & method_mask & (y_pred == 1))
            method_precision = method_tp / (method_tp + method_fp) if (method_tp + method_fp) > 0 else 0
            print(f"    {method:<20}: {count:4d} détections (precision: {method_precision:.1%})")
    
    # Analyse des erreurs
    print_color("\n  ANALYSE DES ERREURS", Colors.YELLOW)
    
    # Faux positifs
    fp_mask = (y_true == 0) & (y_pred == 1)
    fp_examples = df[fp_mask]['message'].head(5).tolist()
    print(f"\n  Faux Positifs ({fp} total):")
    for i, msg in enumerate(fp_examples[:3], 1):
        print(f"    {i}. {msg[:70]}...")
    
    # Faux négatifs
    fn_mask = (y_true == 1) & (y_pred == 0)
    fn_examples = df[fn_mask]['message'].head(5).tolist()
    print(f"\n  Faux Négatifs ({fn} total):")
    for i, msg in enumerate(fn_examples[:3], 1):
        print(f"    {i}. {msg[:70]}...")
    
    # Résumé final
    print_color("\n" + "=" * 70, Colors.CYAN)
    print_color("  RÉSUMÉ FINAL", Colors.CYAN)
    print_color("=" * 70, Colors.CYAN)
    
    all_passed = precision >= 0.75 and recall >= 0.70 and f1 >= 0.70 and accuracy >= 0.85
    
    print(f"""
    Dataset:     {len(df)} logs ({y_true.sum()} anomalies, {len(df)-y_true.sum()} normal)
    Détectées:   {y_pred.sum()} anomalies
    
    Precision:   {precision:.2%}  {'✅' if precision >= 0.75 else '❌'}
    Recall:      {recall:.2%}  {'✅' if recall >= 0.70 else '❌'}
    F1-Score:    {f1:.2%}  {'✅' if f1 >= 0.70 else '❌'}
    
    Vrais Positifs:  {tp:4d}  (anomalies correctement détectées)
    Faux Positifs:   {fp:4d}  (fausses alertes)
    Faux Négatifs:   {fn:4d}  (anomalies manquées)
    Vrais Négatifs:  {tn:4d}  (logs normaux correctement classés)
    """)
    
    if all_passed:
        print_color("    ✅ TOUS LES OBJECTIFS ATTEINTS", Colors.GREEN)
    else:
        print_color("    ⚠️  CERTAINS OBJECTIFS NON ATTEINTS", Colors.YELLOW)
    
    print_color("=" * 70, Colors.CYAN)
    
    # Sauvegarder résultats
    results_dict = {
        'timestamp': datetime.now().isoformat(),
        'dataset_size': len(df),
        'anomalies_ground_truth': int(y_true.sum()),
        'anomalies_detected': int(y_pred.sum()),
        'metrics': {
            'precision': float(precision),
            'recall': float(recall),
            'f1_score': float(f1),
            'accuracy': float(accuracy),
            'true_positives': int(tp),
            'false_positives': int(fp),
            'false_negatives': int(fn),
            'true_negatives': int(tn)
        }
    }
    
    import json
    output_path = os.path.join(SCRIPT_DIR, 'metrics_results.json')
    with open(output_path, 'w') as f:
        json.dump(results_dict, f, indent=2)
    print(f"\n  📊 Résultats sauvegardés: {output_path}")


if __name__ == '__main__':
    main()
