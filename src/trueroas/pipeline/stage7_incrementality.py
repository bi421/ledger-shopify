import polars as pl
import numpy as np
from src.trueroas.core.ledger import ExperimentLedger
from src.trueroas.core.wilson import wilson_score_interval
from src.trueroas.config import get_settings

def calculate_if(test_cr: float, control_cr: float) -> float:
    """Calculates the Incrementality Factor (IF)."""
    return max(0, min(1, (test_cr - control_cr) / test_cr)) if test_cr > 0 else 0.0

def calculate_if_decay(base_if: float, frequency: float, campaign_type: str = "prospecting") -> tuple[float, float]:
    """v0.3 Decay modeling based on audience saturation."""
    settings = get_settings()
    decay_rate = settings.paths.get(f"if_decay_rate_{campaign_type}", 0.05 if campaign_type == "prospecting" else 0.12)
    adjusted_if = base_if * np.exp(-decay_rate * (frequency - 1))
    return adjusted_if, decay_rate

def run_stage7(
    df: pl.DataFrame,
    account_id: str,
    campaign_id: str,
    ledger_path: str = "data/experiments.jsonl",
) -> tuple[pl.DataFrame, dict]:
    """
    Stage 7 v0.3 Refactor: Experiment-Aware Inference Layer.
    """
    ledger = ExperimentLedger(path=ledger_path)
    settings = get_settings()
    
    exp = ledger.get_active_experiment(account_id, campaign_id)
    truth_source = "default_prior"
    truth_grade = "C"
    base_if = 0.7  # Default prior mean
    ci = (0.55, 0.85)
    freshness = 0.0
    warning_flags = []
    
    if exp:
        base_if = exp.if_point_estimate
        ci = exp.if_confidence_interval
        truth_source = exp.experiment_id
        freshness = exp.freshness_score
        truth_grade = "A" if freshness > 0.7 else "B"
    else:
        warning_flags.append("if_from_default_prior")

    # Frequency-based decay
    avg_freq = df["frequency"].mean() if "frequency" in df.columns else 1.0
    final_if, rate_used = calculate_if_decay(base_if, avg_freq)
    
    df_final = df.with_columns([
        pl.lit(final_if).alias("if_factor"),
        pl.lit(truth_source).alias("truth_source"),
        pl.lit(truth_grade).alias("truth_grade")
    ])

    metadata = {
        "incrementality": {
            "point_estimate": round(final_if, 4),
            "confidence_interval": ci,
            "confidence_level": 0.95,
            "source": truth_source,
            "truth_grade": truth_grade,
            "decay_applied": avg_freq > 1.0,
            "decay_rate": rate_used,
            "freshness_score": round(freshness, 2),
            "warning_flags": warning_flags
        }
    }
    
    return df_final, metadata
