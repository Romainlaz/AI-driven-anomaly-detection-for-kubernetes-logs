"""
Convert notebook-trained model to production-ready AnomalyDetector class
Run this AFTER training in ISO_avec_Drain.ipynb
"""

def convert_notebook_to_production():
    """
    This function should be run at the END of ISO_avec_Drain.ipynb
    to convert the trained model to production format
    """
    
    # Import production class
    import sys
    sys.path.append('..')
    from src.model import AnomalyDetector
    
    print("[INFO] Converting notebook model to production format...")
    
    # Create production detector
    detector = AnomalyDetector(threshold_percentile=90)
    
    # Copy trained components from notebook
    detector.iso_forest = iso
    detector.miner = miner
    detector.vectorizer = vect_templates
    detector.encoder = encoder
    
    # Calculate threshold
    import numpy as np
    y_scores_iso = -iso.decision_function(X_test)
    detector.threshold = np.percentile(y_scores_iso, 90)
    
    # Save
    detector.save("model.pkl")
    
    print("[INFO] Model converted and saved!")
    print(f"[INFO]   Threshold: {detector.threshold:.2f}")
    print(f"[INFO]   Use: anomaly-detector serve --model model.pkl")
    
    return detector

# Usage in notebook:
# %run scripts/convert_model.py
# detector = convert_notebook_to_production()
