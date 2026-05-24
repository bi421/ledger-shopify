import pytest
import polars as pl
from src.trueroas.pipeline.stage4_reconciliation import run_stage4

def test_reconciliation_full_match():
    """Test that all orders are correctly matched to marketing data."""
    shopify_df = pl.DataFrame({
        "email_hash": ["hash_1", "hash_2"],
        "total_price": [100.0, 250.0]
    })
    meta_df = pl.DataFrame({
        "customer_email_hash": ["hash_1", "hash_2"],
        "fbclid": ["fb_1", "fb_2"]
    })

    result, meta = run_stage4(shopify_df, meta_df)

    assert result.height == 2
    assert "true_revenue" in result.columns
    assert result.filter(pl.col("email_hash") == "hash_1")["fbclid"][0] == "fb_1"
    assert result.filter(pl.col("email_hash") == "hash_2")["true_revenue"][0] == 250.0

def test_reconciliation_partial_match():
    """Test that unmatched orders still appear in the result with null marketing data."""
    shopify_df = pl.DataFrame({
        "email_hash": ["match", "no_match"],
        "total_price": [50.0, 75.0]
    })
    meta_df = pl.DataFrame({
        "customer_email_hash": ["match"],
        "fbclid": ["fb_matched"]
    })

    result, meta = run_stage4(shopify_df, meta_df)

    assert result.height == 2
    assert result.filter(pl.col("email_hash") == "match")["fbclid"][0] == "fb_matched"
    assert result.filter(pl.col("email_hash") == "no_match")["fbclid"][0] is None

def test_reconciliation_empty_shopify():
    """Test that an empty Shopify dataframe returns an empty result gracefully."""
    shopify_df = pl.DataFrame()
    meta_df = pl.DataFrame({
        "customer_email_hash": ["hash_1"],
        "fbclid": ["fb_1"]
    })

    result, meta = run_stage4(shopify_df, meta_df)
    assert result.is_empty()

def test_reconciliation_column_aliasing():
    """Verify that total_price is correctly aliased to true_revenue."""
    shopify_df = pl.DataFrame({
        "email_hash": ["h"],
        "total_price": [99.99]
    })
    meta_df = pl.DataFrame({"customer_email_hash": ["h"], "fbclid": ["c"]})
    result, meta = run_stage4(shopify_df, meta_df)
    assert result["true_revenue"][0] == 99.99

def test_reconciliation_identity_stitching_waterfall():
    """Verify that orders failing email match are recovered via device fingerprint (fbp)."""
    shopify_df = pl.DataFrame({
        "order_id": ["ORD_1", "ORD_2"],
        "email_hash": ["email_match", "email_fail"],
        "browser_id": ["fbp_1", "fbp_2"],
        "total_price": [100.0, 200.0]
    })
    
    meta_df = pl.DataFrame({
        "customer_email_hash": ["email_match", "different_email"],
        "fbp": ["fbp_1", "fbp_2"],
        "fbclid": ["click_1", "click_2"],
        "campaign_id": ["CAMP_1", "CAMP_2"]
    })

    result, metadata = run_stage4(shopify_df, meta_df)

    assert result.height == 2
    # Check match methods
    assert result.filter(pl.col("order_id") == "ORD_1")["match_method"][0] == "email_hash"
    assert result.filter(pl.col("order_id") == "ORD_2")["match_method"][0] == "device_fingerprint"
