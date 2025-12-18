"""
Benchmarking script for anomaly detection service
"""
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
from concurrent.futures import ThreadPoolExecutor


def load_test(url: str, n_requests: int = 1000, n_workers: int = 10):
    """Load test the prediction endpoint"""
    
    sample_log = {
        "message": "ERROR: Connection refused to database",
        "namespace": "default",
        "pod": "api-server-xyz"
    }
    
    latencies = []
    errors = 0
    
    def send_request():
        try:
            start = time.time()
            response = requests.post(f"{url}/predict", json=sample_log)
            latency = time.time() - start
            
            if response.status_code == 200:
                return latency
            else:
                return None
        except Exception:
            return None
    
    print(f"[INFO] Load testing {url} with {n_requests} requests ({n_workers} workers)...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        results = list(executor.map(lambda _: send_request(), range(n_requests)))
    
    total_time = time.time() - start_time
    
    # Filter successes
    latencies = [r for r in results if r is not None]
    errors = len([r for r in results if r is None])
    
    # Stats
    print(f"\n Results:")
    print(f"[INFO]  Total time: {total_time:.2f}s")
    print(f"[INFO]  Throughput: {n_requests/total_time:.2f} req/s")
    print(f"[INFO]  Success: {len(latencies)}/{n_requests} ({len(latencies)/n_requests*100:.2f}%)")
    print(f"[INFO]  Errors: {errors}")
    print(f"\n⏱  Latencies:")
    print(f"[INFO]  Min: {min(latencies)*1000:.2f}ms")
    print(f"[INFO]  Mean: {sum(latencies)/len(latencies)*1000:.2f}ms")
    print(f"[INFO]  p50: {pd.Series(latencies).quantile(0.5)*1000:.2f}ms")
    print(f"[INFO]  p95: {pd.Series(latencies).quantile(0.95)*1000:.2f}ms")
    print(f"[INFO]  p99: {pd.Series(latencies).quantile(0.99)*1000:.2f}ms")
    print(f"[INFO]  Max: {max(latencies)*1000:.2f}ms")
    
    # Plot
    plt.figure(figsize=(10, 5))
    plt.hist(pd.Series(latencies)*1000, bins=50, alpha=0.7)
    plt.xlabel("Latency (ms)")
    plt.ylabel("Count")
    plt.title(f"Prediction Latency Distribution (n={len(latencies)})")
    plt.axvline(sum(latencies)/len(latencies)*1000, color='r', linestyle='--', label='Mean')
    plt.axvline(pd.Series(latencies).quantile(0.95)*1000, color='orange', linestyle='--', label='p95')
    plt.legend()
    plt.savefig("benchmark_latency.png")
    print(f"\n Saved plot to benchmark_latency.png")


if __name__ == "__main__":
    load_test(
        url="http://localhost:8080",
        n_requests=1000,
        n_workers=10
    )
