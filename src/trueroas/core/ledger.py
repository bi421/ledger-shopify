from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Literal
import json
import os
from pydantic import BaseModel, ConfigDict


class ExperimentRecord(BaseModel):
    experiment_id: str
    account_id: str
    campaign_id: str
    channel: str
    experiment_type: Literal["geo_lift", "holdout", "conversion_lift", "mmm_inferred"]
    test_cr: Optional[float] = None
    control_cr: Optional[float] = None
    sample_size_test: Optional[int] = None
    sample_size_control: Optional[int] = None
    start_date: datetime
    end_date: datetime
    if_point_estimate: float
    if_confidence_interval: tuple[float, float]  # Wilson Score Interval
    freshness_score: float  # 0.0 to 1.0
    status: Literal["active", "stale", "invalidated", "unvalidated"]
    validation_source: str
    model_config = ConfigDict(from_attributes=True)


class Ledger:
    """
    Хатуу үнэний эх сурвалж.
    Дүрэм: ЗӨВХӨН append. Update/delete байхгүй.
    """

    def __init__(self, path: str = "data/ledger.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, event: Dict[str, Any]) -> None:
        """Raw event бичих — хэзээ ч өөрчлөгдөхгүй"""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "_immutable": True,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read(self, account_id: str, metric: str, days: int = 30) -> List[Dict]:
        """Бүх methodology эндээс уншина — read-only"""
        results = []
        if not os.path.exists(self.path):
            return results

        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    ev = rec["event"]
                    if ev.get("account_id") == account_id and ev.get("metric") == metric:
                        ts = datetime.fromisoformat(rec["ts"]).timestamp()
                        if ts >= cutoff:
                            results.append(ev)
                except Exception:
                    continue
        return results


class ExperimentLedger:
    """
    v0.3 Experiment-Aware Inference Layer.
    Manages the lifecycle of incrementality experiments.
    """

    def __init__(self, path: str = "data/experiments.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def add_experiment(self, record: ExperimentRecord):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

    def get_freshness_score(self, end_date: datetime) -> float:
        """Calculates freshness: 1.0 at end_date, decaying to 0.0 over 90 days."""
        days_since = (datetime.now(timezone.utc) - end_date).days
        return max(0.0, 1.0 - (days_since / 90.0))

    def get_active_experiment(self, account_id: str, campaign_id: str) -> Optional[ExperimentRecord]:
        """Queries the most recent active experiment for a campaign."""
        latest = None
        if not os.path.exists(self.path):
            return None

        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                rec = ExperimentRecord.model_validate_json(line)
                if rec.account_id == account_id and rec.campaign_id == campaign_id:
                    # Update freshness on the fly for logic checks
                    rec.freshness_score = self.get_freshness_score(rec.end_date)
                    if rec.status == "active" and rec.freshness_score > 0:
                        if not latest or rec.start_date > latest.start_date:
                            latest = rec
        return latest
