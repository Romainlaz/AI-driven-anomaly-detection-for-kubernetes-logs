#!/usr/bin/env python
"""
Prometheus Exporter pour le modèle de détection d'anomalies
Expose les scores d'anomalie et métriques en temps réel
"""

import time
import pickle
import pandas as pd
import numpy as np
from prometheus_client import Gauge, Counter, Histogram, Info, start_http_server
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from scipy.sparse import hstack, csr_matrix
import re
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# MÉTRIQUES PROMETHEUS
# ============================================================================

# Scores d'anomalie par namespace et pod
anomaly_score = Gauge(
    'log_anomaly_score',
    'Score d\'anomalie du dernier log traité',
    ['namespace', 'pod', 'log_level']
)

# Taux d'anomalies global
anomaly_rate = Gauge(
    'log_anomaly_rate',
    'Pourcentage de logs anormaux sur la dernière fenêtre',
    ['namespace']
)

# Nombre total d'anomalies détectées
anomaly_count = Counter(
    'log_anomaly_total',
    'Nombre total d\'anomalies détectées depuis le démarrage',
    ['namespace', 'severity']
)

# Escalade d'erreurs progressive
error_escalation = Gauge(
    'log_error_escalation_detected',
    'Détection d\'escalade progressive d\'erreurs (0 ou )',
    ['namespace']
)

# Pente de l'escalade
error_escalation_slope = Gauge(
    'log_error_escalation_slope',
    'Pente de l\'escalade d\'erreurs (régression linéaire)',
    ['namespace']
)

# Distribution des scores (histogram)
score_distribution = Histogram(
    'log_anomaly_score_distribution',
    'Distribution des scores d\'anomalie',
    buckets=[-.0, -0.5, -0., -0., -0., -0.05, 0, 0., 0., 0.5]
)

# Métriques de performance du modèle
model_prediction_time = Histogram(
    'log_anomaly_prediction_seconds',
    'Temps de prédiction du modèle en secondes'
)

# Informations sur le modèle
model_info = Info('log_anomaly_model', 'Informations sur le modèle de détection')

# ============================================================================
# CLASSE EXPORTER
# ============================================================================

class AnomalyDetectorExporter:
    """
    Exporte les métriques de détection d'anomalies vers Prometheus
    """
    
    def __init__(self, model_path='model/isolation_forest.pkl', 
                 vectorizer_path='model/vectorizer.pkl',
                 scaler_path='model/scaler.pkl',
                 encoder_path='model/encoder.pkl',
                 window_size=100):
        """
        Initialise l'exporteur
        
        Parameters:
        -----------
        model_path : str
            Chemin vers le modèle Isolation Forest sauvegardé
        vectorizer_path : str
            Chemin vers le vectorizer TF-IDF sauvegardé
        scaler_path : str
            Chemin vers le scaler sauvegardé
        encoder_path : str
            Chemin vers l'encoder OneHot sauvegardé
        window_size : int
            Taille de la fenêtre temporelle pour l'analyse
        """
        self.window_size = window_size
        self.threshold = -0.05
        self.log_buffer = []  # Buffer pour l'analyse temporelle
        
        # Charger le modèle et les transformers
        logger.info("Chargement du modèle et des transformers...")
        try:
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
            with open(vectorizer_path, 'rb') as f:
                self.vectorizer = pickle.load(f)
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            with open(encoder_path, 'rb') as f:
                self.encoder = pickle.load(f)
            
            logger.info("Modèle chargé avec succès")
            
            # Mettre à jour les infos du modèle
            model_info.info({
                'algorithm': 'IsolationForest',
                'contamination': str(self.model.contamination),
                'n_estimators': str(self.model.n_estimators),
                'threshold': str(self.threshold)
            })
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle: {e}")
            raise
    
    def normalize_log(self, text):
        """Normalise le message de log"""
        text = re.sub(r'\d+', '<NUM>', text)
        text = re.sub(r'/[A-Za-z0-9_\-\.]+', '<PATH>', text)
        text = re.sub(r'blk_\d+', 'blk_<ID>', text)
        text = re.sub(r'[\[\]\(\)\{\}]', '', text)
        return text.lower()
    
    def extract_features(self, df):
        """Extrait les features pour la prédiction"""
        # Renommer les colonnes pour correspondre au modèle
        df = df.rename(columns={'wiremind.message': 'message'}) if 'wiremind.message' in df.columns else df
        
        # Features numériques
        df['length'] = df['message'].apply(len)
        df['num_tokens'] = df['message'].apply(lambda x: len(x.split()))
        df['num_digits'] = df['message'].apply(lambda x: sum(c.isdigit() for c in x))
        df['num_upper'] = df['message'].apply(lambda x: sum(c.isupper() for c in x))
        df['digit_ratio'] = df['num_digits'] / (df['length'] + 1e-5)
        df['upper_ratio'] = df['num_upper'] / (df['length'] + 1e-5)
        df['has_error'] = df['message'].str.contains(
            'error|fail|exception|critical|alert|timeout', 
            flags=re.IGNORECASE
        ).astype(int)
        
        # Normaliser le texte
        df['normalized'] = df['message'].apply(self.normalize_log)
        
        # TF-IDF
        X_tfidf = self.vectorizer.transform(df['normalized'])
        
        # Features numériques
        numeric_cols = ['length', 'num_tokens', 'num_digits', 'digit_ratio', 'upper_ratio', 'has_error']
        X_num = self.scaler.transform(df[numeric_cols])
        
        # Context (namespace, pod)
        X_context = self.encoder.transform(df[['kubernetes.namespace_name', 'kubernetes.pod_name']])
        
        # Combiner
        X_combined = hstack([X_tfidf, csr_matrix(X_num), X_context])
        
        return X_combined, df
    
    def detect_escalation(self, error_counts):
        """
        Détecte une escalade progressive d'erreurs
        
        Parameters:
        -----------
        error_counts : list
            Liste du nombre d'erreurs par sous-intervalle
            
        Returns:
        --------
        is_escalating : bool
        slope : float
        """
        if len(error_counts) < 10:
            return False, 0.0
        
        # Régression linéaire
        from sklearn.linear_model import LinearRegression
        X = np.array(range(len(error_counts))).reshape(-1, 1)
        y = np.array(error_counts)
        
        if len(np.unique(y)) == 1:
            return False, 0.0
        
        model = LinearRegression()
        model.fit(X, y)
        slope = model.coef_[0]
        
        return slope > 0.5, slope
    
    def process_logs(self, logs_df):
        """
        Traite un batch de logs et met à jour les métriques Prometheus
        
        Parameters:
        -----------
        logs_df : DataFrame
            DataFrame avec colonnes: message, namespace, pod, log_level
        """
        if len(logs_df) == 0:
            return
        
        start_time = time.time()
        
        try:
            # Extraire les features
            X, df = self.extract_features(logs_df)
            
            # Prédiction
            scores = self.model.decision_function(X)
            predictions = scores < self.threshold
            
            # Temps de prédiction
            prediction_time = time.time() - start_time
            model_prediction_time.observe(prediction_time)
            
            # Mettre à jour les métriques par log
            for idx, (_, log) in enumerate(df.iterrows()):
                namespace = log['kubernetes.namespace_name']
                pod = log['kubernetes.pod_name']
                log_level = log.get('log.level', 'unknown')
                score = scores[idx]
                is_anomaly = predictions[idx]
                
                # Score individuel
                anomaly_score.labels(
                    namespace=namespace,
                    pod=pod,
                    log_level=log_level
                ).set(score)
                
                # Distribution
                score_distribution.observe(score)
                
                # Compter les anomalies
                if is_anomaly:
                    severity = 'critical' if score < -0.5 else 'high' if score < -0.0 else 'medium'
                    anomaly_count.labels(namespace=namespace, severity=severity).inc()
            
            # Métriques par namespace
            for namespace in df['kubernetes.namespace_name'].unique():
                namespace_logs = df[df['kubernetes.namespace_name'] == namespace]
                namespace_scores = scores[df['kubernetes.namespace_name'] == namespace]
                namespace_anomalies = predictions[df['kubernetes.namespace_name'] == namespace]
                
                # Taux d'anomalies
                rate = namespace_anomalies.sum() / len(namespace_anomalies) if len(namespace_anomalies) > 0 else 0
                anomaly_rate.labels(namespace=namespace).set(rate)
            
            # Ajouter au buffer pour analyse temporelle
            self.log_buffer.extend(df.to_dict('records'))
            if len(self.log_buffer) > self.window_size:
                self.log_buffer = self.log_buffer[-self.window_size:]
            
            # Analyser les escalades si buffer suffisant
            if len(self.log_buffer) >= 0:
                self._analyze_escalations()
            
            logger.info(f"Traité {len(logs_df)} logs en {prediction_time:.2f}s - "
                       f"{predictions.sum()} anomalies détectées")
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement des logs: {e}")
    
    def _analyze_escalations(self):
        """Analyse les escalades d'erreurs sur le buffer"""
        try:
            buffer_df = pd.DataFrame(self.log_buffer)
            
            # Diviser en 5 intervalles
            n_intervals = 5
            interval_size = len(buffer_df) // n_intervals
            
            error_counts = []
            for i in range(n_intervals):
                start = i * interval_size
                end = start + interval_size if i < n_intervals - 1 else len(buffer_df)
                interval_errors = buffer_df.iloc[start:end]['has_error'].sum()
                error_counts.append(interval_errors)
            
            # Détecter l'escalade
            is_escalating, slope = self.detect_escalation(error_counts)
            
            # Mettre à jour les métriques par namespace
            for namespace in buffer_df['kubernetes.namespace_name'].unique():
                error_escalation.labels(namespace=namespace).set(1 if is_escalating else 0)
                error_escalation_slope.labels(namespace=namespace).set(slope)
                
                if is_escalating:
                    logger.warning(f"Escalade détectée dans namespace {namespace} - Pente: {slope:.2f}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des escalades: {e}")


# ============================================================================
# SIMULATEUR DE LOGS (pour tests)
# ============================================================================

def simulate_logs(n_logs=50):
    """Générer des logs simulés pour le test"""
    import random
    from datetime import datetime
    
    namespaces = ['production', 'staging', 'development']
    pods = [f'pod-{i}' for i in range(0)]
    log_levels = ['INFO', 'WARNING', 'ERROR', 'CRITICAL', 'DEBUG']
    
    messages = [
        'Request processed successfully',
        'Connection timeout after 0s',
        'Database query executed',
        'Memory usage at 85%',
        'Exception in thread main',
        'Failed to connect to service',
        'API response time: 50ms',
        'Disk space low on /var/log',
        'User authentication successful',
        'Error: null pointer exception'
    ]
    
    logs = []
    for _ in range(n_logs):
        log = {
            'kubernetes.namespace_name': random.choice(namespaces),
            'kubernetes.pod_name': random.choice(pods),
            'log.level': random.choice(log_levels),
            'wiremind.message': random.choice(messages),
            'timestamp': datetime.now().isoformat()
        }
        logs.append(log)
    
    return logs


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Prometheus Exporter pour détection d\'anomalies')
    parser.add_argument('--port', type=int, default=8000, help='Port pour l\'exporter Prometheus')
    parser.add_argument('--model-dir', type=str, default='model', help='Répertoire contenant les modèles')
    parser.add_argument('--interval', type=int, default=60, help='Intervalle de scraping en secondes')
    parser.add_argument('--simulate', action='store_true', help='Mode simulation avec logs générés')
    
    args = parser.parse_args()
    
    # Démarrer le serveur Prometheus
    logger.info(f"Démarrage de l'exporter Prometheus sur le port {args.port}")
    start_http_server(args.port)
    logger.info(f"Métriques disponibles sur http://localhost:{args.port}/metrics")
    
    # Initialiser l'exporter
    exporter = AnomalyDetectorExporter(
        model_path=f'{args.model_dir}/isolation_forest.pkl',
        vectorizer_path=f'{args.model_dir}/vectorizer.pkl',
        scaler_path=f'{args.model_dir}/scaler.pkl',
        encoder_path=f'{args.model_dir}/encoder.pkl'
    )
    
    # Charger les logs Wiremind
    wiremind_logs = None
    try:
        wiremind_logs = pd.read_csv('Wiremind_logs.csv')
        logger.info(f"✓ Chargé {len(wiremind_logs)} logs depuis Wiremind_logs.csv")
    except Exception as e:
        logger.warning(f"Fichier Wiremind_logs.csv non trouvé: {e}")
    
    batch_index = 0
    batch_size = 50
    
    # Boucle principale
    logger.info("Début de la collecte de métriques...")
    try:
        while True:
            if args.simulate and wiremind_logs is not None:
                # Mode simulation avec vrais logs Wiremind
                start_idx = (batch_index * batch_size) % len(wiremind_logs)
                end_idx = min(start_idx + batch_size, len(wiremind_logs))
                logs_df = wiremind_logs.iloc[start_idx:end_idx].copy()
                logs_df = logs_df.dropna(subset=['wiremind.message'])
                logger.info(f"Batch {batch_index + 1}: {len(logs_df)} logs Wiremind")
                batch_index += 1
            elif args.simulate:
                # Fallback vers logs simulés
                logs_list = simulate_logs(n_logs=50)
                logs_df = pd.DataFrame(logs_list)
                logger.info("  Simulation: génération de logs fictifs")
            else:
                # Mode production
                logger.warning("Mode production non implémenté - utilisez --simulate")
                time.sleep(args.interval)
                continue
            
            # Traiter les logs
            exporter.process_logs(logs_df)
            
            # Attendre l'intervalle
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.info("Arrêt de l'exporter")


if __name__ == '__main__':
    main()
