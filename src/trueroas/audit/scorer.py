import polars as pl
import yaml
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Protocol

class AuditStrategy(Protocol):
    def evaluate(self, df: pl.DataFrame) -> bool:
        ...

class DynamicRuleStrategy:
    def __init__(self, condition_str: str):
        self.condition_str = condition_str

    def evaluate(self, df: pl.DataFrame) -> bool:
        try:
            # Evaluate the string as a Polars expression
            # Note: eval() is used carefully here as strings are sourced from internal rules.yaml
            mask = df.filter(eval(self.condition_str))
            return mask.height > 0
        except Exception:
            return False

def score_account(
    df: pl.DataFrame, 
    metadata: Dict[str, Any] = None, 
    historical_stats: Dict[str, float] = None
) -> Dict[str, Any]:
    """
    Evaluates marketing data against audit rules and returns a health score.
    """
    if df.is_empty():
        return {"score": 100, "violations": [], "reasoning": []}

    rules_path = Path(__file__).parent / "rules.yaml"
    if not rules_path.exists():
        return {"score": 100, "violations": [], "reasoning": []}

    with open(rules_path, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)

    total_penalty = 0
    violations_detected = []

    # 1. Batch Diagnostics (Drift & Reliability)
    if metadata and "stage_diagnostics" in metadata:
        if historical_stats:
            drift_violations = detect_drift(metadata, historical_stats)
            for v in drift_violations:
                total_penalty += v["penalty"]
                violations_detected.append(v)

    # 2. Causal Reasoning
    insights = decompose_performance_shifts(df, historical_stats)

    # 3. Vectorized Strategy Evaluation
    for rule in rules:
        strategy = DynamicRuleStrategy(rule["condition"])
        if strategy.evaluate(df):
            total_penalty += rule["weight"]
            violations_detected.append({
                "id": rule["id"],
                "name": rule["name"],
                "penalty": rule["weight"],
                "condition": rule["condition"]
            })

    score = 100 - total_penalty
    return {
        "score": max(0, score),
        "violations": violations_detected,
        "reasoning": insights
    }

def detect_drift(metadata: Dict[str, Any], historical_stats: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Compares current pipeline metadata against historical averages to detect 
    Milestone 12.4 data drift anomalies.
    """
    violations = []
    if not historical_stats or "stage_diagnostics" not in metadata:
        return violations

    diag = metadata["stage_diagnostics"]
    
    # 1. Match Rate Drift (Reconciliation Stability)
    current_mr = diag.get("reconciliation", {}).get("match_rate")
    avg_mr = historical_stats.get("avg_match_rate")
    
    if current_mr is not None and avg_mr is not None and avg_mr > 0:
        # Detect relative drop > 25%
        if current_mr < avg_mr * 0.75:
            violations.append({
                "id": "D01",
                "name": "Match Rate Drift Detected",
                "penalty": 15,
                "condition": f"current {current_mr:.2f}% < 75% of historical avg {avg_mr:.2f}%"
            })

    # 2. Invalid Traffic Volume Drift
    current_inv = diag.get("stage2_invalid", {}).get("invalid_traffic_count", 0)
    avg_inv = historical_stats.get("avg_invalid_count")
    
    if avg_inv is not None and avg_inv > 0:
        # Detect volume spike > 2x historical average
        if current_inv > avg_inv * 2.0:
            violations.append({
                "id": "D02",
                "name": "Invalid Traffic Volume Spike",
                "penalty": 10,
                "condition": f"current {current_inv} > 2x historical avg {avg_inv:.2f}"
            })

    return violations

def decompose_performance_shifts(df: pl.DataFrame, historical_stats: Optional[Dict[str, float]]) -> List[str]:
    """
    Milestone 15: AI Root-Cause Engine.
    Decomposes current performance compared to historical benchmarks to provide 
    confidence-aware explanations.
    """
    if not historical_stats or df.is_empty():
        return []

    insights = []
    
    # Calculate current leading indicators
    current_metrics = df.select([
        (pl.col("spend").sum() / pl.col("impressions").sum() * 1000).alias("cpm"),
        (pl.col("clicks").sum() / pl.col("impressions").sum()).alias("ctr"),
        (pl.col("true_revenue").sum() / pl.col("spend").sum()).alias("roas")
    ]).to_dicts()[0]

    # Baseline comparisons using real historical data from the Warehouse
    avg_cpm = historical_stats.get("avg_cpm") or 10.0
    avg_ctr = historical_stats.get("avg_ctr") or 0.01

    cpm_shift = (current_metrics["cpm"] - avg_cpm) / avg_cpm if avg_cpm else 0
    ctr_shift = (current_metrics["ctr"] - avg_ctr) / avg_ctr if avg_ctr else 0

    if abs(cpm_shift) > 0.15:
        direction = "increased" if cpm_shift > 0 else "decreased"
        insights.append(f"CPM has {direction} by {abs(cpm_shift):.1%} affecting cost efficiency.")

    if ctr_shift < -0.10:
        insights.append(f"CTR fell by {abs(ctr_shift):.1%}, suggesting potential creative fatigue thresholds.")

    # Detect if ROAS drop is primarily driven by Top-of-Funnel (CPM) vs Mid-Funnel (CTR)
    if cpm_shift > 0.2 and ctr_shift < -0.15:
        insights.append("Combined Anomaly: ROAS compression driven by simultaneous CPM inflation and creative decay.")
    elif cpm_shift > 0.2:
        insights.append("Cost Alert: Revenue stability is being offset by platform-wide CPM increases.")
    elif ctr_shift < -0.2:
        insights.append("Attention Alert: Performance drop is isolated to engagement decay; refresh creatives.")

    return insights