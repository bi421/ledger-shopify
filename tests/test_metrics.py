import pytest
import polars as pl
from src.trueroas.core.metrics import true_roas, true_cac, mer, poas, marginal_roas
from src.trueroas.core.reasoning import analyze_roas_drop, generate_strategic_recommendations

@pytest.mark.parametrize("spend, revenue, refund, if_factor, expected", [
    (100.0, 300.0, 0.1, 0.8, 2.16),  # PROMPT 021: 300 revenue, 100 spend, 0.1 refund, 0.8 IF
    (0.0, 0.0, 0.1, 0.8, 0.0),       # PROMPT 021: Test zero spend => 0
    (100.0, 300.0, 0.0, 0.0, 0.0),   # PROMPT 021: Test if_factor 0 => 0
])
def test_true_roas(spend, revenue, refund, if_factor, expected):
    """
    Verify True ROAS calculation logic across various scenarios.
    Implements PROMPT 021 specifications.
    """
    assert true_roas(spend, revenue, refund, if_factor) == pytest.approx(expected)

def test_true_cac():
    """Verify True CAC calculation with base case and edge case for zero customers."""
    # Standard case
    assert true_cac(100.0, 10, 1.0) == 10.0
    # IF case
    assert true_cac(100.0, 10, 0.5) == 20.0
    # Zero customers case (denominator defaults to 1)
    assert true_cac(100.0, 0, 1.0) == 100.0

def test_mer():
    """Verify Blended ROAS (MER) calculation."""
    assert mer(1000.0, 200.0) == 5.0
    # Division by zero protection (1e-9)
    assert mer(1000.0, 0.0) == pytest.approx(1e12) 

def test_poas():
    """Verify Profit on Ad Spend calculation."""
    assert poas(100.0, 40.0, 20.0) == 3.0

def test_marginal_roas():
    """Verify Marginal ROAS calculation using Polars time-series differentiation."""
    df = pl.DataFrame({
        "clean_date": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "true_revenue": [100.0, 250.0, 450.0],
        "normalized_spend": [10.0, 20.0, 30.0]
    })
    # ΔRev: [None, 150, 200]
    # ΔSpend: [None, 10, 10]
    # Marginals: [15, 20]
    # Mean: 17.5
    assert marginal_roas(df) == pytest.approx(17.5)

def test_marginal_roas_insufficient_data():
    """Ensure Marginal ROAS returns 0 for dataframes with fewer than 2 rows."""
    df_empty = pl.DataFrame({"clean_date": [], "true_revenue": [], "normalized_spend": []})
    df_single = pl.DataFrame({"clean_date": ["2024-01-01"], "true_revenue": [100.0], "normalized_spend": [10.0]})
    
    assert marginal_roas(df_empty) == 0.0
    assert marginal_roas(df_single) == 0.0

def test_marginal_roas_zero_spend_change():
    """Ensure Marginal ROAS skips periods with no change in spend to avoid div by zero."""
    df = pl.DataFrame({
        "clean_date": ["2024-01-01", "2024-01-02"],
        "true_revenue": [100.0, 150.0],
        "normalized_spend": [10.0, 10.0]
    })
    assert marginal_roas(df) == 0.0

@pytest.mark.parametrize("shifts, expected_substring", [
    ({"roas": -0.1, "cpm": 0.2, "ctr": -0.05}, "Auction Pressure"),
    ({"roas": -0.1, "cpm": 0.05, "ctr": -0.15}, "Creative Fatigue"),
    ({"roas": -0.1, "cvr": -0.15}, "Conversion Friction"),
    ({"roas": -0.1}, "General Optimization"),
    ({"roas": 0.1}, "Growth Opportunity"),
    ({"roas": 0.01}, "Stable State"),
])
def test_generate_strategic_recommendations(shifts, expected_substring):
    """Verify that the strategic recommendation engine identifies the correct causal drivers."""
    recs = generate_strategic_recommendations(shifts)
    assert any(expected_substring in r for r in recs)

def test_analyze_roas_drop():
    """Verify the full causal decomposition loop in analyze_roas_drop."""
    # Baseline: ROAS 2.0, CPM 10.0, CTR 1.0%
    baseline_df = pl.DataFrame({
        "spend": [100.0],
        "impressions": [10000],
        "clicks": [100],
        "true_revenue": [200.0]
    })
    
    # Current: CPM increases to 15.0 (+50%), leading to ROAS drop
    current_df = pl.DataFrame({
        "spend": [150.0],
        "impressions": [10000],
        "clicks": [100],
        "true_revenue": [200.0]
    })
    
    result = analyze_roas_drop(baseline_df, current_df)
    
    assert result["baseline_roas"] == 2.0
    assert result["current_roas"] == pytest.approx(1.3333333)
    assert "CPM increase" in result["suggested_driver"]
    assert any("Auction Pressure" in r for r in result["recommendations"])
    assert result["metrics"]["cpm"] == pytest.approx(0.5)