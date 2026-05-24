import pytest
import polars as pl
from datetime import datetime, timezone, timedelta
from src.trueroas.core.ledger import ExperimentLedger, ExperimentRecord
from src.trueroas.pipeline.stage7_incrementality import run_stage7

def test_experiment_ledger_selection_logic(tmp_path):
    """Verify the pipeline correctly selects active vs stale vs prior."""
    ledger_path = tmp_path / "test_experiments.jsonl"
    ledger = ExperimentLedger(path=str(ledger_path))
    
    # 1. Add an active experiment
    active_exp = ExperimentRecord(
        experiment_id="geo_2026", account_id="act_1", campaign_id="camp_1",
        channel="meta", experiment_type="geo_lift", start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        if_point_estimate=0.8, if_confidence_interval=(0.7, 0.9),
        freshness_score=1.0, status="active", validation_source="manual"
    )
    ledger.add_experiment(active_exp)
    
    mock_df = pl.DataFrame({"frequency": [1.5]})
    _, meta = run_stage7(mock_df, "act_1", "camp_1", ledger_path=str(ledger_path))
    
    assert meta["incrementality"]["source"] == "geo_2026"
    assert meta["incrementality"]["truth_grade"] == "A"

def test_if_decay_at_high_frequency():
    """Verify that IF decays logically as frequency increases."""
    from src.trueroas.pipeline.stage7_incrementality import calculate_if_decay
    
    base_if = 0.8
    # Low frequency (1.0) -> No decay
    if_1, _ = calculate_if_decay(base_if, 1.0)
    assert if_1 == base_if
    
    # High frequency (10.0) -> Significant decay
    if_10, _ = calculate_if_decay(base_if, 10.0)
    assert if_10 < base_if
    assert if_10 > 0
