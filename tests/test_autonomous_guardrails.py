import pytest
import uuid
import json
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from unittest.mock import MagicMock, patch, AsyncMock
from src.trueroas.api.main import app

@pytest.fixture
def mock_engine():
    with patch("src.trueroas.api.routes.autonomous.engine") as mock:
        # Setup default mock behaviors for warehouse
        mock.warehouse = MagicMock()
        mock.warehouse.get_autonomy_state.return_value = {"enabled": True, "halt_reason": None}
        
        # Default valid audit (Grade A, High Confidence)
        mock.warehouse.get_latest_audit.return_value = {
            "timestamp": datetime.now(),
            "diagnostics": {
                "meta": {"audit_id": "audit_123"},
                "probabilistic_layer": {
                    "confidence": 0.95,
                    "incrementality": {"truth_grade": "A", "source": "geo_lift_test"},
                    "warning_flags": []
                },
                "reasoning": {"autonomous_execution_eligible": True}
            }
        }
        yield mock

@pytest.mark.asyncio
async def test_execute_action_idempotency(mock_engine):
    """Verify that duplicate idempotency keys return cached results."""
    mock_engine.warehouse.get_action_by_idempotency.return_value = {
        "action_id": "cached_action_456",
        "status": "EXECUTED"
    }

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/autonomous/execute",
            json={
                "account_id": "act_123",
                "action_type": "SCALE_BUDGET",
                "params": {"increase_percent": 10},
                "idempotency_key": "unique_key_789"
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["action_id"] == "cached_action_456"
    assert data["status"] == "EXECUTED"
    # Ensure the engine didn't re-run any logic
    mock_engine.warehouse.log_action.assert_not_called()

@pytest.mark.asyncio
async def test_execute_action_circuit_breaker(mock_engine):
    """Verify 403 response when account autonomy is disabled."""
    mock_engine.warehouse.get_autonomy_state.return_value = {
        "enabled": False, 
        "halt_reason": "CRITICAL DRIFT > 20%"
    }
    mock_engine.warehouse.get_action_by_idempotency.return_value = None

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/autonomous/execute",
            json={
                "account_id": "act_123",
                "action_type": "SCALE_BUDGET",
                "params": {"increase_percent": 10}
            }
        )

    assert response.status_code == 403
    assert "Autonomy Halted" in response.json()["detail"]

@pytest.mark.asyncio
async def test_execute_action_stale_audit(mock_engine):
    """Verify SYNC_REQUIRED status when audit data is > 24h old."""
    mock_engine.warehouse.get_action_by_idempotency.return_value = None
    mock_engine.warehouse.get_latest_audit.return_value = {
        "timestamp": datetime.now() - timedelta(hours=25),
        "diagnostics": {}
    }

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/autonomous/execute",
            json={
                "account_id": "act_123",
                "action_type": "SCALE_BUDGET",
                "params": {"increase_percent": 10}
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SYNC_REQUIRED"
    assert data["requires_approval"] is True

@pytest.mark.asyncio
async def test_execute_action_governance_gate(mock_engine):
    """Verify PENDING_APPROVAL status for Grade B / Low Confidence data."""
    mock_engine.warehouse.get_action_by_idempotency.return_value = None
    # Set low confidence in mock
    mock_engine.warehouse.get_latest_audit.return_value["diagnostics"]["probabilistic_layer"]["confidence"] = 0.70

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/autonomous/execute",
            json={
                "account_id": "act_123",
                "action_type": "SCALE_BUDGET",
                "params": {"increase_percent": 10}
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING_APPROVAL"
    assert data["requires_approval"] is True
    mock_engine.warehouse.log_action.assert_called_with(
        action_id=pytest.any,
        idempotency_key=None,
        account_id="act_123",
        org_id="default",
        action_type="SCALE_BUDGET",
        params={"increase_percent": 10},
        status="PENDING_APPROVAL",
        summary=pytest.any,
        audit_ref="audit_123",
        grade="A",
        score=0.70
    )

@pytest.mark.asyncio
async def test_execute_action_three_phase_success(mock_engine):
    """Verify state machine: EXECUTING -> EXECUTED on success."""
    mock_engine.warehouse.get_action_by_idempotency.return_value = None
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/autonomous/execute",
            json={
                "account_id": "act_123",
                "action_type": "SCALE_BUDGET",
                "params": {"increase_percent": 10}
            }
        )

    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTED"
    
    # Verify order of calls
    calls = mock_engine.warehouse.update_action_status.call_args_list
    assert calls[0].args[1] == "EXECUTING"
    assert calls[1].args[1] == "EXECUTED"

@pytest.mark.asyncio
async def test_execute_action_three_phase_zombie_on_final_persistence_failure(mock_engine):
    """Verify state machine keeps EXECUTING when final persistence fails after external success."""
    mock_engine.warehouse.get_action_by_idempotency.return_value = None
    
    with patch(
        "src.trueroas.api.routes.autonomous.engine.warehouse.update_action_status",
        side_effect=[None, Exception("API Crash")],
    ) as update_action_status:
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/autonomous/execute",
                json={
                    "account_id": "act_123",
                    "action_type": "SCALE_BUDGET",
                    "params": {"increase_percent": 10}
                }
            )

    update_action_status.assert_any_call(pytest.any, "EXECUTING")
    update_action_status.assert_any_call(pytest.any, "EXECUTED")
    assert response.status_code == 200
    assert response.json()["status"] == "EXECUTING"

@pytest.mark.asyncio
async def test_reconcile_zombies_endpoint(mock_engine):
    mock_engine.warehouse.reconcile_zombie_actions.return_value = {"executed": 1, "failed": 1}

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/autonomous/reconcile-zombies",
            json=["action_confirmed"],
        )

    assert response.status_code == 200
    assert response.json()["resolved"] == {"executed": 1, "failed": 1}
    mock_engine.warehouse.reconcile_zombie_actions.assert_called_once_with(
        confirmed_action_ids=["action_confirmed"],
        max_age_minutes=5,
    )

@pytest.mark.asyncio
async def test_approve_action_authorization(mock_engine):
    """Verify that only authorized org members can approve actions."""
    mock_engine.warehouse.get_action.return_value = {"status": "PENDING_APPROVAL", "org_id": "org_777"}
    mock_engine.warehouse.get_org_members.return_value = [{"user_id": "legit_user", "role": "owner"}]

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Unauthorized attempt
        bad_res = await ac.post("/api/v1/autonomous/action_1/approve", json={"approver_id": "hacker_99", "status": "APPROVED"})
        assert bad_res.status_code == 403

        # Authorized attempt
        good_res = await ac.post("/api/v1/autonomous/action_1/approve", json={"approver_id": "legit_user", "status": "APPROVED"})
        assert good_res.status_code == 200
