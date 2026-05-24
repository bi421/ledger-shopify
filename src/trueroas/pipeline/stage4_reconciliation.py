import polars as pl
import logging
from src.trueroas.schemas import FBInsightRaw, EventClean
from src.trueroas.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def reconcile_marketing_data(shopify_df: pl.DataFrame, meta_df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """
    Reconciles Shopify orders with Meta click and attribution data (Stage 4).
    Enforces a strict match-rate threshold safeguard.

    Args:
        shopify_df (pl.DataFrame): Shopify transaction records.
        meta_df (pl.DataFrame): Refined marketing dataset (Enriched FBInsightRaw/EventClean).
    """
    if shopify_df.is_empty():
        logging.warning("Shopify dataframe is empty. Skipping reconciliation step.")
        return pl.DataFrame(), {"match_rate": 0.0, "total_orders": 0}

    total_orders = shopify_df.height

    # --- Waterfall Identity Stitching (Milestone 1) ---

    # 1. Primary Deterministic Match: Email Hash
    # High confidence match based on user identity
    email_matches = shopify_df.join(
        meta_df,
        left_on=["email_hash"],
        right_on=["customer_email_hash"],
        how="left"
    ).with_columns(
        match_method=pl.lit("email_hash"),
        stitch_confidence=pl.lit(1.0),
        validation_source=pl.lit("exact_email_match")
    )

    # 2. Identify gaps (orders that failed to match via email)
    # We assume 'shopify_df' has a 'browser_id' column (mapped from fbp at checkout)
    unmatched_mask = pl.col("campaign_id").is_null()
    if "browser_id" in shopify_df.columns:
        gaps = email_matches.filter(unmatched_mask).select(shopify_df.columns)
        
        settings = get_settings()

        # Calculate ID Collision Metrics to prevent "Fake Truth" from shared devices
        # This is a heuristic confidence score based on device sharing frequency,
        # not a mathematically calibrated probability.
        collision_map = meta_df.filter(pl.col("fbp").is_not_null()).group_by("fbp").agg(
            pl.len().alias("collision_count")
        ).with_columns(
            collision_adjusted_confidence = (1.0 / pl.col("collision_count")).clip(settings.stitch_confidence_floor, settings.stitch_confidence_ceiling)
        )

        # 3. Secondary Probabilistic Match: Device Fingerprint (fbp)
        fingerprint_matches = gaps.join(
            meta_df.filter(pl.col("fbp").is_not_null()).join(collision_map, on="fbp", how="left"),
            left_on="browser_id",
            right_on="fbp",
            how="left"
        ).with_columns(
            match_method=pl.lit("device_fingerprint"),
            stitch_confidence=pl.col("collision_adjusted_confidence").fill_null(settings.stitch_confidence_floor),
            validation_source=pl.lit("probabilistic_fingerprint")
        ).drop(["collision_count", "collision_adjusted_confidence"])

        # Combine: take successful email matches and successful fingerprint matches
        reconciled_df = pl.concat([
            email_matches.filter(~unmatched_mask),
            fingerprint_matches
        ], how="diagonal_relaxed")
    else:
        logging.warning("Missing 'browser_id' in Shopify data. Probabilistic stitching disabled.")
        reconciled_df = email_matches

    # --- Final Normalization ---

    reconciled_df = reconciled_df.with_columns(
        pl.col("total_price").alias("true_revenue")
    )

    # Compute match rate based on presence of Facebook Click ID
    matched_orders = reconciled_df.filter(pl.col("fbclid").is_not_null()).height
    match_rate = (matched_orders / total_orders) * 100 if total_orders > 0 else 0
    
    logging.info(f"===> TrueROAS Stage 4 Match Rate: {match_rate:.2f}% ({matched_orders}/{total_orders})")

    # Milestone 12.4: Data Drift detection logic could be triggered here
    # Critical Safeguard: Alert if data density drops below baseline stability threshold
    if match_rate < 70.0:
        logging.error(
            f"CRITICAL WARNING: Match rate dropped to {match_rate:.2f}%! "
            f"Data density is below the 70% reliability baseline. TrueROAS calculations may be skewed."
        )

    metadata = {
        "match_rate": match_rate,
        "total_orders": total_orders,
        "matched_orders": matched_orders,
        "match_attribution": reconciled_df.group_by("match_method").len().to_dicts()
    }
    return reconciled_df, metadata

def run_stage4(shopify_df: pl.DataFrame, meta_df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """
    Orchestration wrapper matching the exact function name expected by pipeline.py

    Args:
        shopify_df (pl.DataFrame): Shopify transaction records.
        meta_df (pl.DataFrame): Refined marketing dataset (Enriched FBInsightRaw/EventClean).
    """
    return reconcile_marketing_data(shopify_df, meta_df)
