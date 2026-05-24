import polars as pl
import structlog
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from src.trueroas.config import get_settings
from src.trueroas.fb_client import FBClient
from src.trueroas.shopify_client import ShopifyClient
from src.trueroas.pipeline.pipeline import TrueRoasPipeline
from src.trueroas.warehouse.warehouse import TrueRoasWarehouse
from src.trueroas.audit.scorer import score_account
from src.trueroas.core.reasoning import analyze_roas_drop
from src.trueroas.core.simulation import monte_carlo_budget_forecast
from src.trueroas.core.metrics import true_roas, true_cac
from src.trueroas.core.decision import DecisionIntelligence
from src.trueroas.core.ledger import Ledger

logger = structlog.get_logger("TrueRoasEngine")

class TrueRoasEngine:
    """
    Enterprise SaaS Orchestrator (v1.0).
    Handles asynchronous job lifecycle, tenant isolation, and governance.
    """

    def __init__(self):
        self.settings = get_settings()
        self.pipeline = TrueRoasPipeline()
        self.warehouse = TrueRoasWarehouse(connection_string=self.settings.paths["warehouse"])
        self.shopify = ShopifyClient(
            access_token=self.settings.SHOPIFY_ACCESS_TOKEN,
            store_url=self.settings.SHOPIFY_STORE_URL
        )
        self.execution_ledger = Ledger(path="data/execution_lineage.jsonl")
        self.worker_id = os.getenv("HOSTNAME", f"worker-{uuid.uuid4().hex[:8]}")
        self.warehouse.register_worker(self.worker_id)

    async def run_full_sync(
        self, 
        account_id: str, 
        since: str, 
        until: str, 
        org_id: str = "default", 
        trace_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        High-integrity asynchronous sync cycle. 
        Reconciles telemetry with financial truth and applies governance gates.
        """
        start_time = datetime.now()
        trace_id = trace_id or str(uuid.uuid4())
        job_id = f"job-{trace_id}"
        log = logger.bind(account_id=account_id, trace_id=trace_id, org_id=org_id)

        # 0. Idempotency & Heartbeat
        self.warehouse.register_worker(self.worker_id)
        existing_job = self.warehouse.check_idempotency(idempotency_key)
        if existing_job and existing_job["status"] == "COMMITTED":
            log.info("idempotency_hit", job_id=existing_job["job_id"])
            return {"status": "success", "duplicate": True, "job_id": existing_job["job_id"]}

        log.info("sync_started", since=since, until=until)
        self.warehouse.start_job(job_id, account_id, org_id, idempotency_key, self.worker_id)

        try:
            # 1. Marketing Ingestion (Meta Ads) with Resilience
            client = FBClient(
                access_token=self.settings.FB_ACCESS_TOKEN,
                app_id=self.settings.FB_APP_ID,
                app_secret=self.settings.FB_APP_SECRET
            )
            raw_meta = client.get_insights(account_id, since, until)
            
            # 2. Financial Reconciliation Context (Mock until Shopify ingestion is ready)
            empty_shopify = pl.DataFrame({"order_id": [], "email_hash": [], "total_price": [], "created_at": []})

            # 3. 7-Stage Polars Refinement Pipeline
            calibration_factor = self.warehouse.get_calibration_stats(account_id)
            recon_status = self.run_financial_reconciliation_loop(account_id)
            
            refined_df, pipeline_meta = self.pipeline.execute(
                account_id, raw_meta, empty_shopify, calibration_factor=calibration_factor
            )

            # 4. Audit & Causal Reasoning Synthesis
            historical_stats = self.warehouse.fetch_historical_stats(account_id)
            
            # Detect if an experiment is active for Causal vs Suggested drivers
            from src.trueroas.core.ledger import ExperimentLedger
            ledger = ExperimentLedger()
            campaign_id = raw_meta["campaign_id"][0] if not raw_meta.is_empty() else "unknown"
            has_experiment = ledger.get_active_experiment(account_id, campaign_id) is not None

            audit_report = score_account(refined_df, metadata=pipeline_meta, historical_stats=historical_stats)
            
            # Period-over-Period Causal Decomposition
            reasoning_report = self.get_reasoning_report(account_id)
            
            # 5. Decision Memory: Track the recommendation for self-learning
            audit_id = f"ref-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            self.warehouse.log_decision(
                account_id=account_id,
                audit_id=audit_id,
                reasoning=reasoning_report,
                metrics=pipeline_meta["probabilistic_layer"]["incrementality"]
            )

            # 5. Multi-tenant Persistence
            # Ensure critical metrics are attached for warehouse schema compatibility
            refined_df = refined_df.with_columns([
                (pl.col("true_revenue") / pl.col("normalized_spend").fill_null(1e-9)).alias("true_roas"),
                (pl.col("normalized_spend") / (pl.col("order_id").n_unique().cast(pl.Float64) * 
                 pl.lit(pipeline_meta["probabilistic_layer"]["incrementality"].get("point_estimate", 1.0)))
                ).alias("true_cac")
            ])

            # Pass job_id to save_metrics to allow for an atomic commit of both data and status
            self.warehouse.save_metrics(refined_df, job_id=job_id, metadata=pipeline_meta, trace_id=trace_id)
            log.info("sync_completed", execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000)

            # 6. v0.3 Truth-Aware Schema Synthesis
            prob_layer = pipeline_meta["probabilistic_layer"]
            truth_grade = prob_layer["incrementality"]["truth_grade"]
            confidence = prob_layer["confidence"]
            
            # Autonomous Eligibility Gate
            is_eligible = (
                confidence > 0.90 and 
                truth_grade == "A" and 
                not recon_status.get("autonomy_halted", False) and
                reasoning_report.get("driver_evidence", {}).get("method") == "causal_impact"
            )

            return {
                "deterministic_layer": pipeline_meta["deterministic_layer"],
                "probabilistic_layer": {
                    "incrementality": prob_layer["incrementality"],
                    "stitching": pipeline_meta["deterministic_layer"].get("stitching", {}),
                    "profit_roas": {
                        "point_estimate": pipeline_meta["probabilistic_layer"]["incrementality"]["point_estimate"],
                        "confidence_interval": pipeline_meta["probabilistic_layer"]["incrementality"]["if_confidence_interval"],
                        "truth_source": pipeline_meta["probabilistic_layer"]["incrementality"]["source"],
                        "truth_grade": truth_grade
                    }
                },
                "reasoning": {
                    "primary_driver": reasoning_report.get("primary_driver"),
                    "suggested_driver": reasoning_report.get("suggested_driver"),
                    "driver_evidence": reasoning_report.get("driver_evidence"),
                    "recommended_action": reasoning_report.get("recommendations")[0] if reasoning_report.get("recommendations") else "Maintain current scaling",
                    "autonomous_execution_eligible": is_eligible,
                    "eligibility_blockers": [] if is_eligible else ["low_confidence" if confidence < 0.9 else "truth_grade_not_a"]
                },
                "simulation": self.simulate_spend(refined_df["normalized_spend"].sum(), pipeline_meta["probabilistic_layer"]["incrementality"]["point_estimate"]),
                "meta": {
                    "pipeline_version": "0.3.0",
                    "account_id": account_id,
                    "trust_score": confidence,
                    "trust_grade": truth_grade,
                    "calibration_applied": calibration_factor,
                    "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "audit_id": audit_id,
                    "warning_flags": pipeline_meta["probabilistic_layer"]["incrementality"].get("warning_flags", [])
                },
            }

        except Exception as e:
            error_msg = str(e)
            self.warehouse.mark_job_failed_to_dlq(
                job_id=job_id, 
                account_id=account_id, 
                payload={"since": since, "until": until, "org_id": org_id},
                error=error_msg
            )
            log.error("sync_failed", error=str(e))
            return {
                "status": "error",
                "account_id": account_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def get_reasoning_report(self, account_id: str) -> Dict[str, Any]:
        """
        Generates a causal decomposition report explaining performance shifts.
        """
        history_df = self.warehouse.execute_query(
            "SELECT * FROM historical_metrics WHERE account_id = ? ORDER BY clean_date ASC", 
            [account_id]
        )
        
        if history_df.is_empty() or history_df.height < 2:
            return {"error": "Insufficient data for reasoning"}

        # Split data for period-over-period comparison
        mid = history_df.height // 2
        baseline = history_df.head(mid)
        current = history_df.tail(history_df.height - mid)
        
        return analyze_roas_drop(baseline, current)

    def simulate_spend(self, spend: float, historical_roas: float) -> Dict[str, Any]:
        """
        Runs Monte Carlo forecasting for budget scaling scenarios.
        """
        return monte_carlo_budget_forecast(spend, historical_roas)

    def run_financial_reconciliation_loop(self, account_id: str) -> Dict[str, Any]:
        """
        Weekly automated reconciliation comparing TrueROAS predicted revenue 
        against actual Shopify settled funds (Milestone 🛡️).
        
        If variance exceeds 10% for 2 consecutive weeks, autonomous features are disabled.
        """
        try:
            # 1. Fetch predicted weekly revenue from warehouse
            query = """
                SELECT 
                    date_trunc('week', clean_date) as week,
                    SUM(true_revenue) as predicted_revenue
                FROM historical_metrics 
                WHERE account_id = ? 
                GROUP BY 1 
                ORDER BY 1 DESC 
                LIMIT 2
            """
            weekly_predictions = self.warehouse.execute_query(query, [account_id])
            
            if weekly_predictions.is_empty():
                return {"status": "skipped", "reason": "Insufficient historical data", "autonomy_halted": False}

            # 2. Comparison Logic (Mocking 'Settled Funds' comparison)
            recon_data = []
            fail_count = 0
            
            for row in weekly_predictions.to_dicts():
                week_start = row["week"]
                week_end = week_start + timedelta(days=7)
                
                predicted = row["predicted_revenue"]
                actual = self.shopify.get_settled_revenue(week_start, week_end)
                variance = abs(predicted - actual) / max(actual, 1e-9)
                
                is_failed = variance > self.settings.recon_variance_threshold
                if is_failed:
                    fail_count += 1
                    
                recon_data.append({
                    "week": str(row["week"]),
                    "variance": round(variance, 4),
                    "status": "failed" if is_failed else "passed"
                })

            # 3. Kill Switch Logic: Detect consecutive failures or critical drift
            latest_variance = recon_data[0]["variance"] if recon_data else 0
            critical_variance = latest_variance > self.settings.recon_critical_variance_threshold
            autonomy_halted = (fail_count >= self.settings.recon_consecutive_weeks) or critical_variance
            
            if autonomy_halted:
                msg = f"CRITICAL DRIFT > {self.settings.recon_critical_variance_threshold:.0%}" if critical_variance else \
                      f"Persistent Variance > {self.settings.recon_variance_threshold:.0%} for {self.settings.recon_consecutive_weeks} weeks"
                logger.critical(f"[Kill Switch] {msg}. Disabling autonomy for {account_id}")
                self.warehouse.set_autonomy_state(account_id=account_id, enabled=False, reason=msg)

            return {
                "account_id": account_id,
                "reconciliation_history": recon_data,
                "autonomy_halted": autonomy_halted
            }
        except Exception as e:
            logger.error(f"Financial Reconciliation Loop Failure: {str(e)}")
            return {"status": "error", "error": str(e), "autonomy_halted": True} # Safety-first circuit break

# Export a singleton engine instance
engine = TrueRoasEngine()