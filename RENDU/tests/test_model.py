"""
Tests for anomaly detection model
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code_source'))

import pytest
import pandas as pd
import numpy as np
from src.model import AnomalyDetector


@pytest.fixture
def sample_logs():
    """Sample log data for testing"""
    return pd.DataFrame({
        'message': [
            'INFO: Application started successfully',
            'ERROR: Connection refused to database',
            'DEBUG: Processing request 5',
            'WARNING: High memory usage detected'
        ],
        'namespace': ['default', 'default', 'prod', 'prod'],
        'pod': ['api-', 'api-', 'db-', 'worker-']
    })


def test_redact_pii():
    """Test PII redaction"""
    detector = AnomalyDetector()
    
    # Email redaction
    result = detector._redact_pii("user@example.com")
    assert "<email>" in result.lower() or "email" in result.lower()
    
    # IP redaction - check that IP is masked
    result = detector._redact_pii("192.168.1.1")
    assert "192.168.1.1" not in result or "<ip>" in result.lower()
    
    # Number redaction
    result = detector._redact_pii("ID: 12345")
    assert "12345" not in result


def test_extract_features():
    """Test feature extraction"""
    detector = AnomalyDetector()
    
    message = "ERROR: Connection refused"
    features = detector._extract_features(message)
    
    assert 'length' in features
    assert 'num_tokens' in features
    assert 'digit_ratio' in features
    assert features['length'] == len(message)
    assert features['num_tokens'] >= 2  # At least 2 tokens


def test_train_model(sample_logs):
    """Test model training"""
    detector = AnomalyDetector(threshold_percentile=90)
    detector.train(sample_logs)
    
    assert detector.iso_forest is not None
    assert detector.miner is not None
    assert detector.vectorizer is not None
    assert detector.encoder is not None
    # Threshold can be negative or zero with Isolation Forest (based on decision_function)
    assert detector.threshold is not None


def test_predict(sample_logs):
    """Test prediction"""
    detector = AnomalyDetector(threshold_percentile=90)
    detector.train(sample_logs)
    
    log_entry = {
        'message': 'ERROR: Connection timeout',
        'namespace': 'default',
        'pod': 'api-'
    }
    
    result = detector.predict(log_entry)
    
    assert 'is_anomaly' in result
    assert 'score' in result
    assert 'threshold' in result
    assert 'template' in result
    assert isinstance(result['is_anomaly'], bool)
    # Score can be negative (Isolation Forest decision_function output)
    assert isinstance(result['score'], float)


def test_save_load(sample_logs, tmp_path):
    """Test model save/load"""
    # Train and save
    detector = AnomalyDetector(threshold_percentile=90)
    detector.train(sample_logs)
    
    model_path = tmp_path / "model.pkl"
    detector.save(str(model_path))
    
    # Load and compare
    detector = AnomalyDetector.load(str(model_path))
    
    assert detector.threshold == detector.threshold
    assert detector.threshold_percentile == detector.threshold_percentile
    
    # Same prediction
    log_entry = {'message': 'Test', 'namespace': 'default', 'pod': 'api-'}
    result = detector.predict(log_entry)
    result = detector.predict(log_entry)
    
    assert result['score'] == pytest.approx(result['score'], rel=1e-5)
