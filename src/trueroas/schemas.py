from datetime import date, datetime, timezone
from typing import Literal, Optional, Tuple, Dict, Any
from pydantic import BaseModel, ConfigDict

class FBInsightRaw(BaseModel):
    date: date
    account_id: str
    campaign_id: str
    adset_id: str
    ad_id: str
    spend: float
    impressions: int
    reach: int
    clicks: int
    lpv: int
    purchases: int
    purchase_value: float
    attribution_setting: str
    model_config = ConfigDict(from_attributes=True)

class EventClean(BaseModel):
    event_id: str
    event_time: datetime
    fbp: Optional[str] = None
    fbc: Optional[str] = None
    source: Literal['pixel', 'capi']
    event_name: str
    value: float
    is_duplicate: bool = False
    is_invalid: bool = False
    if_factor: float = 1.0
    model_config = ConfigDict(from_attributes=True)

class ExperimentRecord(BaseModel):
    experiment_id: str
    account_id: str
    campaign_id: str
    experiment_type: Literal["geo_lift", "holdout", "conversion_lift", "mmm_inferred"]
    test_cr: float
    control_cr: float
    sample_size_test: int
    sample_size_control: int
    start_date: datetime
    end_date: datetime
    if_point_estimate: float
    if_confidence_interval: Tuple[float, float]
    freshness_score: float = 1.0
    status: Literal["active", "stale", "invalidated"]

class AutonomousActionRequest(BaseModel):
    account_id: str
    org_id: str = "default"
    action_type: str
    params: Dict[str, Any]
    idempotency_key: Optional[str] = None

class AutonomousActionResponse(BaseModel):
    action_id: str
    status: str
    requires_approval: bool
    reason: Optional[str] = None

class ApprovalRequest(BaseModel):
    approver_id: str
    status: Literal["APPROVED", "REJECTED"]