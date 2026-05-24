import polars as pl
import logging
from src.trueroas.pipeline.stage1_technical import clean_technical
from src.trueroas.pipeline.stage2_invalid import flag_invalid
from src.trueroas.pipeline.stage3_dedup import dedup_events
from src.trueroas.pipeline.stage4_attribution import normalize_attribution
from src.trueroas.pipeline.stage5_overlap import correct_overlap
from src.trueroas.pipeline.stage6_outlier import flag_outliers
from src.trueroas.pipeline.stage7_incrementality import run_stage7
from src.trueroas.pipeline.stage4_reconciliation import run_stage4

logger = logging.getLogger("TrueRoasPipeline")

class TrueRoasPipeline:
    """
    Central orchestrator that executes the full data refinement cycle sequentially.
    Ensures that raw marketing telemetry data is normalized, filtered for fraud,
    deduplicated, and reconciled against official store financial records.
    """
    def __init__(self, fx_rate: float = 1.0, if_factor: float = 1.0):
        self.fx_rate = fx_rate
        self.if_factor = if_factor

    def execute(self, account_id: str, raw_meta_df: pl.DataFrame, raw_shopify_df: pl.DataFrame, calibration_factor: float = 1.0) -> tuple[pl.DataFrame, dict]:
        """
        Executes all four pipelines sequentially.
        
        Args:
            account_id (str): The Meta Account ID for multi-tenant isolation.
            raw_meta_df (pl.DataFrame): Raw ad platform dataset.
            raw_shopify_df (pl.DataFrame): Raw transaction backend ledger from Shopify.
            calibration_factor (float): Self-learning multiplier from past decision accuracy.
            
        Returns:
            tuple[pl.DataFrame, dict]: Unified dataset and diagnostic metadata.
        """
        logger.info(f"[Pipeline] Initiating refinement cycle for account_id: {account_id}")
        metadata = {"account_id": account_id, "stage_diagnostics": {}}

        # Stage 1: Technical normalization (Time zones and currencies)
        logger.info("[Stage 1] Executing Technical Normalization")
        stage1_df, metadata["stage_diagnostics"]["stage1_technical"] = clean_technical(raw_meta_df)

        # Stage 2: Invalid Traffic and Bot Filtering
        logger.info("[Stage 2] Executing IVT/Bot Filtering")
        stage2_df, metadata["stage_diagnostics"]["stage2_invalid"] = flag_invalid(stage1_df)

        # Stage 3: Transactional Deduplication
        logger.info("[Stage 3] Executing Transactional Deduplication")
        stage3_df, metadata["stage_diagnostics"]["stage3_dedup"] = dedup_events(stage2_df)

        # Stage 4: Attribution Normalization
        logger.info("[Stage 4] Executing Attribution Normalization")
        stage4_df, metadata["stage_diagnostics"]["stage4_attribution"] = normalize_attribution(stage3_df)

        # Stage 5: Overlap Correction
        logger.info("[Stage 5] Executing Reach Overlap Correction")
        stage5_df, metadata["stage_diagnostics"]["stage5_overlap"] = correct_overlap(stage4_df)

        # Stage 6: Outlier Detection
        logger.info("[Stage 6] Executing Statistical Outlier Audit")
        stage6_df, metadata["stage_diagnostics"]["stage6_outlier"] = flag_outliers(stage5_df)

        # Financial Reconciliation (Truth Bridge)
        logger.info("[Reconciliation] Executing Financial Truth Bridge")
        reconciled_df, metadata["stage_diagnostics"]["reconciliation"] = run_stage4(raw_shopify_df, stage6_df)

        # Stage 7: Incrementality Application
        logger.info("[Stage 7] Executing Probabilistic Inference Layer")
        campaign_id = raw_meta_df["campaign_id"][0] if not raw_meta_df.is_empty() else "unknown"
        final_truth_df, stage7_meta = run_stage7(reconciled_df, account_id, campaign_id)
        metadata["stage_diagnostics"]["stage7_incrementality"] = stage7_meta

        # Inject account_id for Milestone 11 Tenant Isolation
        final_truth_df = final_truth_df.with_columns(account_id=pl.lit(account_id))

        # Confidence Calculation
        base_confidence = 0.95
        warning_flags = []
        incrementality_meta = stage7_meta["incrementality"]
        if incrementality_meta["source"] == "default_prior":
            base_confidence = 0.75
            warning_flags.append("if_from_default_prior")

        # Self-Learning Calibration: Adjust confidence based on historical precision
        calibrated_confidence = base_confidence * calibration_factor

        # Construct v0.3 Truth-Aware Schema Metadata
        v03_output = {
            "deterministic_layer": {
                "status": "passed",
                "duplicate_events_removed": metadata["stage_diagnostics"]["stage3_dedup"]["duplicates_removed"],
                "bot_traffic_filtered": metadata["stage_diagnostics"]["stage2_invalid"]["invalid_traffic_count"],
                "stitching": {
                    "match_rate": metadata["stage_diagnostics"]["reconciliation"]["match_rate"],
                    "total_orders": metadata["stage_diagnostics"]["reconciliation"]["total_orders"]
                }
            },
            "probabilistic_layer": {
                "incrementality": incrementality_meta,
                "confidence": calibrated_confidence,
                "warning_flags": warning_flags
            }
        }
        logger.info(f"[Pipeline] Refinement cycle complete. Calibrated Confidence: {calibrated_confidence:.2f}")
        return final_truth_df, v03_output
