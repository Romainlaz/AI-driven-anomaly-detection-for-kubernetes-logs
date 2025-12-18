"""
Quick test script to validate model and service
"""
import requests
import json

def test_model_file():
    """Test that model file exists and loads"""
    print("[INFO] Testing model file...")
    try:
        from src.model import AnomalyDetector
        detector = AnomalyDetector.load("model.pkl")
        print(f"[INFO]    Model loaded (threshold: {detector.threshold:.2f})")
        return True
    except FileNotFoundError:
        print("[INFO]    model.pkl not found - train first!")
        return False
    except Exception as e:
        print(f"[INFO]    Error: {e}")
        return False

def test_prediction():
    """Test model prediction"""
    print("\n Testing prediction...")
    try:
        from src.model import AnomalyDetector
        detector = AnomalyDetector.load("model.pkl")
        
        log_entry = {
            'message': 'ERROR: Connection refused to database',
            'namespace': 'default',
            'pod': 'api-server-xyz'
        }
        
        result = detector.predict(log_entry)
        print(f"[INFO]    Prediction: {result['is_anomaly']}")
        print(f"[INFO]      Score: {result['score']:.2f}")
        print(f"[INFO]      Template: {result['template']}")
        return True
    except Exception as e:
        print(f"[INFO]    Error: {e}")
        return False

def test_service():
    """Test FastAPI service (must be running)"""
    print("\n Testing service (requires: anomaly-detector serve)...")
    try:
        # Health check
        response = requests.get("http://localhost:8080/health")
        if response.status_code == 200:
            print("[INFO]    Health check passed")
        else:
            print(f"[INFO]    Health check failed: {response.status_code}")
            return False
        
        # Prediction
        log_entry = {
            "message": "ERROR: Connection timeout",
            "namespace": "default",
            "pod": "api-"
        }
        response = requests.post("http://localhost:8080/predict", json=log_entry)
        
        if response.status_code == 200:
            result = response.json()
            print(f"[INFO]    Prediction API working")
            print(f"[INFO]      Is anomaly: {result['is_anomaly']}")
            print(f"[INFO]      Score: {result['score']:.2f}")
            return True
        else:
            print(f"[INFO]    Prediction failed: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("[INFO]     Service not running")
        print("[INFO]      Start with: anomaly-detector serve")
        return False
    except Exception as e:
        print(f"[INFO]    Error: {e}")
        return False

def test_metrics():
    """Test Prometheus metrics endpoint"""
    print("\n Testing metrics endpoint...")
    try:
        response = requests.get("http://localhost:8080/metrics")
        if response.status_code == 200:
            metrics = response.text
            if "predictions_total" in metrics:
                print("[INFO]    Metrics endpoint working")
                return True
            else:
                print("[INFO]    Metrics incomplete")
                return False
        else:
            print(f"[INFO]    Metrics failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[INFO]     Service not running")
        return False
    except Exception as e:
        print(f"[INFO]    Error: {e}")
        return False

if __name__ == "__main__":
    print("[INFO] Testing Anomaly Detection MVP\n")
    print("="*50)
    
    results = []
    results.append(("Model file", test_model_file()))
    results.append(("Model prediction", test_prediction()))
    results.append(("Service API", test_service()))
    results.append(("Metrics endpoint", test_metrics()))
    
    print("\n" + "="*50)
    print("[INFO] Test Summary:")
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"[INFO]   {status} {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n All tests passed! MVP is ready.")
    elif passed >= 3:
        print("\n  Core functionality working, but service needs attention.")
    else:
        print("\n Critical issues detected. Fix before deploying.")
