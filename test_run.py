import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Ensure Python can find the project root to resolve the 'src' namespace
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import polars as pl
from src.trueroas.pipeline.pipeline import TrueRoasPipeline
from src.trueroas.warehouse.warehouse import TrueRoasWarehouse

def run_integration_test():
    print("=== Constructing Mock Datasets ===")
    
    # Mock Meta data updated for 7-stage audit requirements
    meta_mock = pl.DataFrame({
        "date": ["2026-05-24 07:00:00", "2026-05-24 07:05:00", "2026-05-24 07:10:00"],
        "campaign_id": ["CAM-1", "CAM-1", "CAM-2"],
        "adset_id": ["AS-1", "AS-1", "AS-2"],
        "ad_id": ["AD-1", "AD-2", "AD-3"],
        "event_id": ["EV-001", "EV-002", "EV-002"],
        "spend": [50.0, 20.0, 30.0],
        "impressions": [1000, 500, 800],
        "reach": [900, 450, 750],
        "clicks": [10, 150, 20],                           
        "lpv": [8, 140, 18],
        "purchase_value": [150.0, 150.0, 150.0],
        "attribution_setting": ["7d_click", "7d_click", "1d_view"],
        "customer_email_hash": ["hash_a", "hash_b", "hash_b"],
        "fbclid": ["fbc_1", "fbc_2", "fbc_2"]
    })

    # Mock Shopify data matching Stage 0 Contract
    shopify_mock = pl.DataFrame({
        "order_id": ["ORD-9910", "ORD-9911"],
        "email_hash": ["hash_a", "hash_b"],
        "total_price": [140.0, 135.0],
        "created_at": ["2026-05-24 08:00:00", "2026-05-24 08:30:00"]
    })

    print("\n=== Initializing TrueROAS Engine Pipeline ===")
    # Instantiate with specific FX and Incrementality factors
    pipeline = TrueRoasPipeline(fx_rate=1.0, if_factor=0.85)
    final_truth_df, pipeline_meta = pipeline.execute("act_integration_test", meta_mock, shopify_mock)
    
    # Add missing ROAS/CAC columns for warehouse compatibility if not in pipeline
    # In production, these would be handled by src.trueroas.core.metrics
    final_output = final_truth_df.with_columns([
        (pl.col("total_price") / pl.col("spend").fill_null(1e-9)).alias("true_roas"),
        (pl.col("spend") / pl.lit(1.0)).alias("true_cac")
    ])
    
    print("\n=== FINAL RECONCILED DATA ENGINE RESULTS ===")
    # The column 'clean_date' comes from Stage 1 technical normalization
    print(final_output.select([
        "order_id", "clean_date", "spend", 
        "true_revenue", "true_roas", "true_cac"
    ]) if "clean_date" in final_output.columns else "Columns missing in result")
    
    print("\n=== Initializing Storage Warehouse Engine ===")
    # This invokes the DuckDB setup and creates data/clean/trueroas_warehouse.db
    warehouse = TrueRoasWarehouse()
    
    # Write processed metrics to DuckDB tables
    warehouse.save_metrics(final_output, job_id=None, metadata=pipeline_meta)
    
    print("\n=== Querying Historical Aggregates from DuckDB ===")
    summary_df = warehouse.fetch_summary_metrics()
    print(summary_df)

if __name__ == "__main__":
    run_integration_test()
