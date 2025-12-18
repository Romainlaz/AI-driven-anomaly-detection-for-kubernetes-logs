# ADR 01: Isolation Forest with Percentile Threshold

**Date**: 05--7  
**Status**: Accepted  
**Context**: Anomaly Detection for Kubernetes Logs MVP

## Context

We need to detect anomalies in Kubernetes logs with minimal supervision. The baseline Isolation Forest model achieved 55% precision with 5% false positives, which is too high for production.

## Decision

Use **Isolation Forest with percentile-based threshold** (95th percentile) instead of default contamination threshold.

## Rationale

### Problem with Default Approach
- Isolation Forest contamination parameter (0.05 = 5%) controls expected anomaly rate
- Higher values (0.1 = 10%) result in too many false positives
- Example: Rare startup logs flagged as anomalies (false positives)

### Why Percentile Threshold Works
1. **Adjustable sensitivity**: Can tune false positive rate
2. **Non-supervised**: Doesn't require labeled data
3. **Proven results**: 86.5% precision achieved with p95

### Alternatives Considered

| Approach | Precision | Recall | Pros | Cons |
|----------|-----------|--------|------|------|
| **ISO Forest (default)** | 55% | 6% | Simple | Too many false positives |
| **Temporal filtering** | 55% | 6% | Detects bursts | No improvement |
| **Combination (p90 + burst)** | 77% | 5% | High precision | Misses non-burst anomalies |
| **Percentile threshold (p90)**  | **85%** | **5%** | **Balanced** | **Lower recall** |

### Trade-offs

**Chosen: Percentile 90%**
-  85% precision (only 5% false positives)
-  Simple to implement
-  Tunable (can adjust percentile)
-  Lower recall (5%, misses some anomalies)

**Why not p95 or p98?**
- p95: 90% precision but only 0% recall (too many misses)
- p98: 95% precision but only 5% recall (misses most anomalies)
- p90 is the sweet spot for MVP

## Implementation

```python
# Calculate threshold
threshold = np.percentile(y_scores_iso, 90)

# Predict
y_pred = (y_scores_iso >= threshold).astype(int)
```

## Consequences

### Positive
-  85% precision meets MVP requirements (>80%)
-  Reduces alert fatigue (only 5% false positives)
-  Easy to tune (change percentile)
-  Works on unlabeled data

### Negative
-  5% recall (misses ~half of anomalies)
-  Requires retraining to update threshold
-  No semantic understanding (detects rarity, not meaning)

### Mitigation
- For missed anomalies: Use alongside keyword-based alerts
- For semantic understanding: Future work (supervised model)

## Validation

Tested on 5K logs (Wiremind_logs.csv + Wiremind_Logs_.csv):
- Train: 7K logs (70%)
- Test: 6K logs (0%)
- Result: 85% precision, 5% recall, F=0.67

## References
- Notebook: `ISO_avec_Drain.ipynb` cells 8-
- Code: `src/model.py` (AnomalyDetector class)
