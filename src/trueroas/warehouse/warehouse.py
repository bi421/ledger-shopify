import threading
import os
import json
import re
from datetime import datetime
import duckdb
import polars as pl
from typing import Optional, Any, Dict, List

class TrueRoasWarehouse:
    """
    Manages the analytical storage layer using DuckDB. Handles local 
    database initialization, writing processed dataframes, and executing 
    high-speed OLAP aggregation queries.

    Architecture Note: In multi-replica deployments (K8s), this class must 
    connect to a centralized instance (e.g., MotherDuck or Postgres) to avoid 
    split-brain state and file corruption.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self, connection_string: Optional[str] = None):
        # Use environment variable as primary, parameter as secondary
        self.connection_string = connection_string or os.getenv("DATABASE_URL", "data/clean/trueroas_warehouse.db")
        self.is_remote = self.connection_string.startswith(("md:", "postgres://", "postgresql://"))
        
        if not self.is_remote:
            os.makedirs(os.path.dirname(self.connection_string), exist_ok=True)
            self._verify_distributed_safety()

        self._initialize_db()
        self.health_check()

    def _verify_distributed_safety(self):
        """
        Operational Realism Check: Warn if multiple pods are potentially 
        writing to a local file.
        """
        replica_count = os.getenv("KUBERNETES_REPLICAS", "1")
        if int(replica_count) > 1:
            print(f"[Architectural Warning] Detected {replica_count} replicas with a LOCAL DuckDB path. "
                  "This configuration is NOT safe for concurrent writes. Use MotherDuck (md:) or Postgres.")

    def _get_connection(self, read_only: bool = False) -> duckdb.DuckDBPyConnection:
        """Standardized connection factory."""
        # MotherDuck handles its own locking; local DuckDB needs explicit mode
        if self.is_remote:
            return duckdb.connect(self.connection_string)
        return duckdb.connect(self.connection_string, read_only=read_only)

    def health_check(self):
        """Verifies database file integrity and connection."""
        try:
            with self._get_connection(read_only=True) as conn:
                conn.execute("SELECT 1")
            print(f"[Warehouse] Health Check: Passed for {self.connection_string}")
        except Exception as e:
            raise ConnectionError(f"[Warehouse] Database Integrity Failure: {e}")

    def _initialize_db(self):
        """
        Ensures idempotency in schema creation across all distributed nodes.
        """
        with self._get_connection(read_only=False) as connection:
            try:
                # Use standard SQL types for compatibility across engines
                connection.execute("""
                CREATE TABLE IF NOT EXISTS historical_metrics (
                    account_id VARCHAR,
                    order_id VARCHAR,
                    clean_date TIMESTAMP,
                    normalized_spend DOUBLE,
                    true_revenue DOUBLE,
                    true_roas DOUBLE,
                    true_cac DOUBLE,
                    PRIMARY KEY (account_id, order_id)
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    account_id VARCHAR,
                    execution_timestamp TIMESTAMP,
                    trace_id VARCHAR,
                    pipeline_version VARCHAR,
                    diagnostics JSON
                );
                CREATE TABLE IF NOT EXISTS sync_jobs (
                    job_id VARCHAR PRIMARY KEY,
                    idempotency_key VARCHAR UNIQUE,
                    account_id VARCHAR,
                    org_id VARCHAR,
                    status VARCHAR, -- PENDING, IN_PROGRESS, VALIDATED, COMMITTED, FAILED
                    worker_id VARCHAR,
                    start_timestamp TIMESTAMP,
                    end_timestamp TIMESTAMP,
                    error_log VARCHAR
                );
                CREATE TABLE IF NOT EXISTS dead_letter_queue (
                    id VARCHAR PRIMARY KEY,
                    job_id VARCHAR,
                    account_id VARCHAR,
                    failed_at TIMESTAMP,
                    payload_snapshot JSON,
                    error_context VARCHAR,
                    retry_count INTEGER DEFAULT 0,
                    status VARCHAR DEFAULT 'PENDING' -- PENDING, REPLAYED, DISCARDED
                );
                CREATE TABLE IF NOT EXISTS worker_registry (
                    worker_id VARCHAR PRIMARY KEY,
                    last_heartbeat TIMESTAMP,
                    status VARCHAR, -- ACTIVE, DRAINED, DEAD
                    metadata JSON
                );
                CREATE TABLE IF NOT EXISTS account_autonomy (
                    account_id VARCHAR PRIMARY KEY,
                    autonomy_enabled BOOLEAN DEFAULT TRUE,
                    halt_reason VARCHAR,
                    last_updated TIMESTAMP DEFAULT now()
                );
                CREATE TABLE IF NOT EXISTS actions (
                    action_id VARCHAR PRIMARY KEY,
                    idempotency_key VARCHAR UNIQUE,
                    account_id VARCHAR,
                    org_id VARCHAR,
                    timestamp TIMESTAMP,
                    action_type VARCHAR,
                    action_params JSON,
                    status VARCHAR, -- PENDING_APPROVAL, APPROVED, REJECTED, EXECUTED, FAILED
                    context_summary JSON,
                    audit_ref VARCHAR,
                    truth_grade VARCHAR,
                    trust_score DOUBLE,
                    approver_id VARCHAR
                );
                CREATE TABLE IF NOT EXISTS decision_memory (
                    memory_id VARCHAR PRIMARY KEY,
                    account_id VARCHAR NOT NULL,
                    audit_id VARCHAR,
                    context_hash VARCHAR,
                    decision_type VARCHAR,
                    outcome DOUBLE,
                    predicted_outcome DOUBLE,
                    reward_signal DOUBLE,
                    timestamp TIMESTAMP,
                    recommendation VARCHAR,
                    primary_driver VARCHAR,
                    metrics_snapshot JSON,
                    outcome_score DOUBLE,
                    is_closed BOOLEAN DEFAULT FALSE
                );
                """)
                print(f"[Warehouse] Schema synchronized: {self.connection_string}")
            except Exception as e:
                print(f"[Warehouse] Schema Initialization Error: {e}")

    def get_autonomy_state(self, account_id: str) -> Dict[str, Any]:
        with self._get_connection(read_only=True) as conn:
            res = conn.execute(
                "SELECT autonomy_enabled, halt_reason FROM account_autonomy WHERE account_id = ?", 
                [account_id]
            ).fetchone()
            if not res:
                return {"enabled": True, "halt_reason": None}
            return {"enabled": res[0], "halt_reason": res[1]}

    def set_autonomy_state(self, account_id: str, enabled: bool, reason: Optional[str] = None):
        with self._get_connection(read_only=False) as conn:
            conn.execute("""
                INSERT INTO account_autonomy (account_id, autonomy_enabled, halt_reason, last_updated)
                VALUES (?, ?, ?, now())
                ON CONFLICT (account_id) DO UPDATE SET 
                    autonomy_enabled = EXCLUDED.autonomy_enabled, 
                    halt_reason = EXCLUDED.halt_reason, 
                    last_updated = now()
            """, [account_id, enabled, reason])

    def log_action(self, action_id: str, account_id: str, org_id: str, action_type: str, params: dict, 
                   status: str, summary: dict, audit_ref: str, grade: str, score: float, idempotency_key: str = None):
        with self._get_connection(read_only=False) as conn:
            conn.execute("""
                INSERT INTO actions (action_id, idempotency_key, account_id, org_id, timestamp, action_type, action_params, status, context_summary, audit_ref, truth_grade, trust_score, approver_id)
                VALUES (?, ?, ?, ?, now(), ?, ?, ?, ?, ?, ?, ?, NULL)
            """, [action_id, idempotency_key, account_id, org_id, action_type, json.dumps(params), status, json.dumps(summary), audit_ref, grade, score])

    def update_action_status(self, action_id: str, status: str, approver_id: Optional[str] = None):
        with self._get_connection(read_only=False) as conn:
            conn.execute("""
                UPDATE actions 
                SET status = ?, approver_id = ?, timestamp = now() 
                WHERE action_id = ?
            """, [status, approver_id, action_id])

    def get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection(read_only=True) as conn:
            res = conn.execute("SELECT * FROM actions WHERE action_id = ?", [action_id]).fetchone()
            if not res: return None
            # Correcting index mapping based on updated actions schema
            return {
                "action_id": res[0], "account_id": res[2], "org_id": res[3],
                "action_type": res[5], "params": json.loads(res[6]),
                "status": res[7], "grade": res[10], "score": res[11],
                "approver_id": res[12]
            }

    def get_action_by_idempotency(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        if not idempotency_key: return None
        with self._get_connection(read_only=True) as conn:
            res = conn.execute("SELECT action_id, status FROM actions WHERE idempotency_key = ?", [idempotency_key]).fetchone()
            return {"action_id": res[0], "status": res[1]} if res else None

    def get_latest_audit(self, account_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection(read_only=True) as conn:
            res = conn.execute("SELECT execution_timestamp, diagnostics FROM audit_logs WHERE account_id = ? ORDER BY execution_timestamp DESC LIMIT 1", [account_id]).fetchone()
            return {"timestamp": res[0], "diagnostics": json.loads(res[1])} if res else None

    def get_org_members(self, org_id: str) -> List[Dict[str, Any]]:
        """
        Returns organization roster for authorization checks.
        TODO: Connect to persistent org_members table.
        """
        # Returning a hardcoded roster for v0.3 validation
        return [{"user_id": "auth_admin_1", "role": "owner"}]

    def check_idempotency(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Returns existing job info if key exists, else None."""
        if not idempotency_key:
            return None
        with self._get_connection(read_only=True) as conn:
            res = conn.execute(
                "SELECT job_id, status, error_log FROM sync_jobs WHERE idempotency_key = ?", 
                [idempotency_key]
            ).fetchone()
            return {"job_id": res[0], "status": res[1], "error": res[2]} if res else None

    def register_worker(self, worker_id: str):
        """Heartbeat mechanism for pod health tracking."""
        with self._get_connection(read_only=False) as conn:
            conn.execute("""
                INSERT INTO worker_registry (worker_id, last_heartbeat, status)
                VALUES (?, now(), 'ACTIVE')
                ON CONFLICT (worker_id) DO UPDATE SET last_heartbeat = now(), status = 'ACTIVE'
            """, [worker_id])

    def mark_job_failed_to_dlq(self, job_id: str, account_id: str, payload: dict, error: str):
        """Moves a failed job's context to the DLQ for manual or auto replay."""
        import uuid
        with self._get_connection(read_only=False) as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute("""
                    INSERT INTO dead_letter_queue (id, job_id, account_id, failed_at, payload_snapshot, error_context)
                    VALUES (?, ?, ?, now(), ?, ?)
                """, [str(uuid.uuid4()), job_id, account_id, json.dumps(payload), error])
                
                conn.execute("UPDATE sync_jobs SET status = 'FAILED', error_log = ?, end_timestamp = now() WHERE job_id = ?", 
                             [error, job_id])
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def get_pending_dlq_tasks(self) -> pl.DataFrame:
        """Retrieves failed tasks from the DLQ that are eligible for retry."""
        with self._get_connection(read_only=True) as conn:
            return conn.execute("""
                SELECT * FROM dead_letter_queue 
                WHERE status = 'PENDING' AND retry_count < 3
                ORDER BY failed_at ASC
            """).pl()

    def update_dlq_status(self, task_id: str, status: str):
        """Updates the status and increments the retry count of a DLQ task."""
        with self._get_connection(read_only=False) as conn:
            conn.execute("""
                UPDATE dead_letter_queue 
                SET status = ?, retry_count = retry_count + 1 
                WHERE id = ?
            """, [status, task_id])

    def start_job(self, job_id: str, account_id: str, org_id: str, idempotency_key: str, worker_id: str):
        """Atomically registers a new job start."""
        with self._get_connection(read_only=False) as conn:
            conn.execute("""
                INSERT INTO sync_jobs (job_id, idempotency_key, account_id, org_id, status, worker_id, start_timestamp)
                VALUES (?, ?, ?, ?, 'IN_PROGRESS', ?, now())
            """, [job_id, idempotency_key, account_id, org_id, worker_id])

    def commit_job(self, job_id: str):
        """Marks a job as successfully completed."""
        with self._get_connection(read_only=False) as conn:
            conn.execute("UPDATE sync_jobs SET status = 'COMMITTED', end_timestamp = now() WHERE job_id = ?", [job_id])

    def _evolve_schema(self, df: pl.DataFrame, connection: duckdb.DuckDBPyConnection):
        """
        Detects new columns in the DataFrame and adds them to the DuckDB table.
        """
        # Query current table structure
        table_info = connection.execute("PRAGMA table_info('historical_metrics')").fetchall()
        existing_cols = [row[1] for row in table_info]  # Index 1 is the 'name' column

        for col in df.columns:
            if col not in existing_cols:
                # Map Polars types to DuckDB types
                dtype = str(df.schema[col])
                db_type = "DOUBLE"  # Default for metrics
                
                if "Int" in dtype:
                    db_type = "BIGINT"
                elif "String" in dtype or "Utf8" in dtype:
                    db_type = "VARCHAR"
                elif "Datetime" in dtype:
                    db_type = "TIMESTAMP"
                elif "Date" in dtype:
                    db_type = "DATE"
                elif "Boolean" in dtype:
                    db_type = "BOOLEAN"

                print(f"[Warehouse] Evolving schema: Adding column '{col}' ({db_type})")
                connection.execute(f"ALTER TABLE historical_metrics ADD COLUMN {col} {db_type}")

    def save_metrics(
        self, 
        df: pl.DataFrame, 
        job_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None, 
        trace_id: str = "internal"
    ):
        """
        Appends or updates processed Polars DataFrame rows directly into DuckDB.
        Uses an upsert strategy, stores pipeline metadata, and atomically commits the job status.
        """
        if df.is_empty():
            print("[Warehouse] Warning: Input DataFrame is empty. Skipping write operation.")
            return

        # Normalize clean_date to prevent DuckDB BLOB -> TIMESTAMP mismatch
        if "clean_date" in df.columns:
            def _normalize_value(value):
                if value is None:
                    return None
                if isinstance(value, (bytes, bytearray)):
                    value = value.decode("utf-8")
                if isinstance(value, str):
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                if isinstance(value, pl.Expr):
                    match = re.search(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?", str(value))
                    if match:
                        return datetime.fromisoformat(match.group(0))
                return value
            df = df.with_columns(pl.col("clean_date").map_elements(_normalize_value, return_dtype=pl.Datetime))

        with self._get_connection(read_only=False) as connection:
            connection.execute("BEGIN TRANSACTION")
            try:
                # Step 1: Ensure table structure matches the incoming data
                self._evolve_schema(df, connection)

                # Step 2: Upsert data using 'BY NAME' to match columns correctly
                connection.execute("INSERT OR REPLACE INTO historical_metrics BY NAME SELECT * FROM df")

                if metadata:
                    account_id = metadata.get("account_id", "unknown")
                    diag_json = json.dumps(metadata)
                    connection.execute("""
                        INSERT INTO audit_logs (account_id, execution_timestamp, trace_id, diagnostics) 
                        VALUES (?, now(), ?, ?)
                    """, [account_id, trace_id, diag_json])
                
                if job_id:
                    # Atomic state transition: Ensure the job is marked COMMITTED in the same transaction
                    connection.execute(
                        "UPDATE sync_jobs SET status = 'COMMITTED', end_timestamp = now() WHERE job_id = ?", 
                        [job_id]
                    )
                
                connection.execute("COMMIT")

            except Exception as e:
                connection.execute("ROLLBACK")
                raise RuntimeError(f"[Warehouse] Commit Failure: {e}")

    def log_decision(self, account_id: str, audit_id: str, reasoning: dict, metrics: dict):
        """Logs a strategic recommendation for future outcome tracking."""
        with self._get_connection(read_only=False) as connection:
            connection.execute("""
                INSERT INTO decision_memory (account_id, audit_id, timestamp, recommendation, primary_driver, metrics_snapshot)
                VALUES (?, ?, now(), ?, ?, ?)
            """, [
                account_id,
                audit_id,
                reasoning.get("recommended_action"),
                reasoning.get("primary_driver") or reasoning.get("suggested_driver"),
                json.dumps(metrics)
            ])

    def get_calibration_stats(self, account_id: str) -> float:
        """Retrieves the precision of past decisions to calibrate confidence."""
        with self._get_connection(read_only=True) as connection:
            res = connection.execute("""
                SELECT AVG(outcome_score) FROM decision_memory 
                WHERE account_id = ? AND is_closed = TRUE
            """, [account_id]).fetchone()
            # Normalize: if AVG is 0.5 (on -1 to 1 scale), return 0.75 calibration
            return (res[0] + 1) / 2 if res and res[0] is not None else 1.0

    def execute_query(self, query: str, params: list = None) -> pl.DataFrame:
        """Executes arbitrary SQL and returns a Polars DataFrame."""
        with self._get_connection(read_only=True) as connection:
            return connection.execute(query, params or []).pl()

    def fetch_summary_metrics(self) -> pl.DataFrame:
        """
        Queries historical storage to compute high-level macro aggregations:
        Total Spend, Total Revenue, Global True ROAS, and Blended True CAC.
        """
        with self._get_connection(read_only=True) as connection:
            query = """
                SELECT 
                    SUM(normalized_spend) as total_spend,
                    SUM(true_revenue) as total_revenue,
                    CASE 
                        WHEN SUM(normalized_spend) > 0 THEN SUM(true_revenue) / SUM(normalized_spend)
                        ELSE 0.0 
                    END as blended_roas,
                    CASE 
                        WHEN COUNT(order_id) > 0 THEN SUM(normalized_spend) / COUNT(order_id)
                        ELSE 0.0 
                    END as blended_cac
                FROM historical_metrics;
            """
            return connection.execute(query).pl()

    def fetch_historical_stats(self, account_id: str, days: int = 30) -> dict:
        """
        Computes historical averages for diagnostic metrics over a rolling window.
        Used for Milestone 12.4 Drift Detection.
        """
        with self._get_connection(read_only=True) as connection:
            # Extracts metrics from stored JSON diagnostics and calculates averages
            query = """
                SELECT 
                    AVG(CAST(json_extract(diagnostics, '$.stage_diagnostics.reconciliation.match_rate') AS DOUBLE)) as avg_match_rate,
                    AVG(CAST(json_extract(diagnostics, '$.probabilistic_layer.confidence') AS DOUBLE)) as avg_confidence,
                    -- Marketing metrics must be pulled from the historical_metrics table for accuracy
                    (SELECT AVG((normalized_spend / NULLIF(impressions, 0)) * 1000) 
                     FROM historical_metrics WHERE account_id = audit_logs.account_id) as avg_cpm,
                    (SELECT AVG(CAST(clicks AS DOUBLE) / NULLIF(impressions, 0)) 
                     FROM historical_metrics WHERE account_id = audit_logs.account_id) as avg_ctr
                FROM audit_logs 
                WHERE account_id = ? 
                AND execution_timestamp >= now() - make_interval(days := CAST(? AS INTEGER));
            """
            
            row = connection.execute(query, [account_id, str(days)]).fetchone()
            if not row or row[0] is None:
                return {}
            
            return {
                "avg_match_rate": row[0],
                "avg_confidence": row[1],
                "avg_cpm": row[2],
                "avg_ctr": row[3]
            }

    def fetch_audit_logs(self, account_id: str, limit: int = 10) -> pl.DataFrame:
        """
        Retrieves the last N audit logs for a specific account.
        """
        with self._get_connection(read_only=True) as connection:
            query = """
                SELECT execution_timestamp, diagnostics 
                FROM audit_logs 
                WHERE account_id = ? 
                ORDER BY execution_timestamp DESC 
                LIMIT ?;
            """
            return connection.execute(query, [account_id, limit]).pl()
