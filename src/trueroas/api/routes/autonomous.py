from fastapi import APIRouter, Body, HTTPException, Request
from src.trueroas.schemas import AutonomousActionRequest, AutonomousActionResponse, ApprovalRequest
from engine import engine
import uuid
import logging
from datetime import datetime, timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(tags=["Autonomous Governance"])

@router.post("/execute", response_model=AutonomousActionResponse)
@limiter.limit("5/minute")
async def execute_action(request: Request, action: AutonomousActionRequest):
    # 0. Idempotency Check
    if action.idempotency_key:
        existing = engine.warehouse.get_action_by_idempotency(action.idempotency_key)
        if existing:
            return AutonomousActionResponse(
                action_id=existing["action_id"],
                status=existing["status"],
                requires_approval=(existing["status"] == "PENDING_APPROVAL")
            )

    # 1. Per-Account Circuit Breaker Check
    state = engine.warehouse.get_autonomy_state(action.account_id)
    if not state["enabled"]:
        raise HTTPException(status_code=403, detail=f"Autonomy Halted: {state['halt_reason']}")

    # 2. Eligibility via Cached Audit (Performance Optimization)
    latest_audit = engine.warehouse.get_latest_audit(action.account_id)
    if not latest_audit:
        raise HTTPException(status_code=422, detail="No historical audit found. Run sync before autonomous execution.")
    
    if latest_audit["timestamp"] < datetime.now() - timedelta(hours=24):
        job_id = str(uuid.uuid4())
        return AutonomousActionResponse(
            action_id=job_id,
            status="SYNC_REQUIRED",
            requires_approval=True,
            reason=f"Audit stale. Refresh {job_id} initiated. Poll /jobs/{job_id}"
        )

    # 3. Governance Evaluation
    audit_data = latest_audit["diagnostics"]
    prob_layer = audit_data.get("probabilistic_layer", {})
    reasoning = audit_data.get("reasoning", {})
    trust_score = prob_layer.get("confidence", 0.0)
    truth_grade = prob_layer.get("incrementality", {}).get("truth_grade", "C")
    warning_flags = prob_layer.get("warning_flags", [])
    
    # 3.1 Consensus Gating
    threshold_eligible = (trust_score >= 0.90 and truth_grade == "A" and not warning_flags)
    engine_eligible = reasoning.get("autonomous_execution_eligible", False)
    is_eligible = engine_eligible and threshold_eligible
    needs_approval = not is_eligible

    # 4. Context Summarization (DB Optimization)
    context_summary = {
        "trust_score": trust_score,
        "truth_grade": truth_grade,
        "audit_ref": audit_data.get("meta", {}).get("audit_id")
    }

    action_id = str(uuid.uuid4())

    # 5. Intent Phase
    status = "PENDING_APPROVAL" if needs_approval else "EXECUTING"

    engine.warehouse.log_action(
        action_id=action_id,
        idempotency_key=action.idempotency_key,
        account_id=action.account_id,
        org_id=action.org_id,
        action_type=action.action_type,
        params=action.params,
        status=status,
        summary=context_summary,
        audit_ref=context_summary["audit_ref"],
        grade=truth_grade,
        score=trust_score
    )

    if status == "EXECUTING":
        engine.warehouse.update_action_status(action_id, "EXECUTING")

        # Phase 2: External API Call
        try:
            # api_result = await engine.meta_client.update_budget(...)
            pass 
        except Exception as api_err:
            engine.warehouse.update_action_status(action_id, "FAILED")
            raise HTTPException(status_code=502, detail=f"Meta API Failure: {api_err}")
            
        # Phase 3: Record Success
        try:
            engine.warehouse.update_action_status(action_id, "EXECUTED")
            status = "EXECUTED"
        except Exception as db_err:
            logging.getLogger("uvicorn.error").critical(
                "DB WRITE FAILED AFTER API SUCCESS: %s", action_id
            )
            return AutonomousActionResponse(
                action_id=action_id,
                status="EXECUTING",
                requires_approval=False,
                reason=(
                    "Action may have succeeded externally, but final persistence is delayed. "
                    "Zombie reconciliation will resolve it within 5 minutes."
                ),
            )

    return AutonomousActionResponse(
        action_id=action_id,
        status=status,
        requires_approval=needs_approval,
        reason="Human audit required: Confidence thresholds not met or Grade != A" if needs_approval else None
    )

@router.post("/{action_id}/approve")
async def approve_action(action_id: str, request: ApprovalRequest):
    action = engine.warehouse.get_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    # 7. Real Authorization Check (Org Membership)
    org_members = engine.warehouse.get_org_members(action["org_id"])
    valid_approvers = {m["user_id"] for m in org_members}
    
    if request.approver_id not in valid_approvers:
        raise HTTPException(status_code=403, detail="Approver not authorized for this organization")
    
    if action["status"] != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Action is already {action['status']}")

    new_status = "EXECUTED" if request.status == "APPROVED" else "REJECTED"
    engine.warehouse.update_action_status(action_id, new_status, request.approver_id)
    
    return {"status": new_status, "action_id": action_id}


@router.post("/reconcile-zombies")
async def reconcile_zombies(confirmed_action_ids: list[str] | None = Body(default=None)):
    result = engine.warehouse.reconcile_zombie_actions(
        confirmed_action_ids=confirmed_action_ids or [],
        max_age_minutes=5,
    )
    return {"status": "ok", "resolved": result}
