import pytest
import polars as pl
import json
import os
from src.trueroas.warehouse.warehouse import TrueRoasWarehouse

@pytest.fixture
def test_warehouse(tmp_path):
    """Provides a warehouse instance using a temporary database file."""
    db_file = tmp_path / "test_trueroas.db"
    return TrueRoasWarehouse(connection_string=str(db_file))

def test_save_metrics_stores_audit_log(test_warehouse):
    """Verify that saving metrics with metadata populates the audit_logs table."""
    account_id = "act_123"
    metadata = {
        "account_id": account_id,
        "status": "success",
        "stage_diagnostics": {"stage1_technical": {"dropped_nulls": 0}}
    }
    
    # Create a minimal valid dataframe for the historical_metrics table
    df = pl.DataFrame({
        "account_id": [account_id],
        "order_id": ["ORD_001"],
        "clean_date": [pl.datetime(2026, 5, 24)],
        "normalized_spend": [50.0],
        "true_revenue": [200.0],
        "true_roas": [4.0],
        "true_cac": [50.0]
    })

    test_warehouse.save_metrics(df, metadata=metadata)
    
    # Retrieve logs
    logs = test_warehouse.fetch_audit_logs(account_id)
    
    assert logs.height == 1
    assert "execution_timestamp" in logs.columns
    assert "diagnostics" in logs.columns
    
    # Verify JSON content
    diag_data = json.loads(logs["diagnostics"][0])
    assert diag_data["account_id"] == account_id
    assert diag_data["status"] == "success"
    assert diag_data["stage_diagnostics"]["stage1_technical"]["dropped_nulls"] == 0

def test_fetch_audit_logs_limit_and_ordering(test_warehouse):
    """Verify that audit logs are returned in descending order and respect the limit."""
    account_id = "act_456"
    
    # Save 5 distinct logs with increasing IDs
    for i in range(5):
        df = pl.DataFrame({
            "account_id": [account_id],
            "order_id": [f"ORD_{i}"],
            "clean_date": [pl.datetime(2026, 5, 24)],
            "normalized_spend": [10.0],
            "true_revenue": [50.0],
            "true_roas": [5.0],
            "true_cac": [10.0]
        })
        metadata = {"account_id": account_id, "iteration": i}
        test_warehouse.save_metrics(df, metadata=metadata)
    
    # Fetch with a limit of 3
    logs = test_warehouse.fetch_audit_logs(account_id, limit=3)
    
    assert logs.height == 3
    
    # Verify ordering (DuckDB 'now()' in save_metrics ensures timestamp increases)
    # The first row in a DESC sort should be the last iteration inserted
    diags = [json.loads(d) for d in logs["diagnostics"].to_list()]
    assert diags[0]["iteration"] == 4
    assert diags[1]["iteration"] == 3
    assert diags[2]["iteration"] == 2

def test_fetch_audit_logs_empty_result(test_warehouse):
    """Verify behavior when no logs exist for an account."""
    # Ensure table is initialized but query for unknown ID
    logs = test_warehouse.fetch_audit_logs("non_existent_account")
    assert logs.height == 0
    assert isinstance(logs, pl.DataFrame)