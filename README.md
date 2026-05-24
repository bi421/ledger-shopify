# TrueROAS v0.3: Autonomous Governance Module README

## Overview
This document describes the Autonomous Governance layer of TrueROAS — the safety-critical system that governs all budget-changing operations. It implements a Three-Phase Execution State Machine with per-account circuit breakers, cached eligibility, and immutable audit trails.

⚠️ **CRITICAL**: The `autonomous.py` implementation in your current codebase (`src/trueroas/api/routes/autonomous.py`) contains known bugs that contradict this documentation. Apply the clean replacement files before using this module in production.

## Core Principles
- **Safety over Speed**: Every autonomous action is gated by multiple independent checks.
- **Immutable Audit**: Every execution attempt is logged before any external API call.
- **Per-Tenant Isolation**: One account's data failure cannot disable autonomy for others.
- **Graceful Degradation**: Stale data triggers async refresh, not synchronous blocking.

## Guardrail Architecture

### 1. Truth Grade A Requirement
Only experiment-backed data (geo-lift, holdout, conversion lift within 30 days) can trigger auto-execution. Grade B/C data always requires human approval.

### 2. Per-Account Circuit Breakers
Financial variance >10% for 2 consecutive weeks disables autonomy for that tenant only. Kill switch is stored in `account_autonomy` table, not global `system_state`.

### 3. Three-Phase Execution
1. **EXECUTING** (Phase 1: Intent recorded)
2. **External API Call** (Phase 2: Meta/Shopify budget update)
3. **EXECUTED / FAILED** (Phase 3: Outcome persisted)

**Zombie State Handling**: If the API succeeds but DB persistence fails, the action remains in `EXECUTING` state. A background reconciliation job resolves these within 5 minutes.

### 4. Cached Eligibility
Instead of running a full synchronous pipeline sync for every `/execute` call, the system:
1. Queries the latest audit record from `audit_logs` table
2. Checks freshness (< 24 hours)
3. If stale, returns `SYNC_REQUIRED` with a `job_id` for async refresh
4. If fresh, uses cached diagnostics for governance evaluation

**Performance Impact**: Reduces `/execute` latency from 5–30s (full sync) to <100ms (cached read).

### 5. Human-in-the-Loop Gate
Any of these conditions forces `PENDING_APPROVAL` status:
- `confidence < 0.90`
- `truth_grade != "A"`
- `warning_flags` non-empty
- `engine_eligible = False` (reasoning engine disagreement)

### 6. Idempotency Enforcement
Duplicate `idempotency_key` values return the existing action record without re-executing. Keys are stored with `UNIQUE` constraint in `actions` table and never expire.

## State Machine Reference

| State | Description | Next States | Guard |
| :--- | :--- | :--- | :--- |
| **PENDING_APPROVAL** | Awaiting human authorization | APPROVED, REJECTED | `needs_approval = true` |
| **APPROVED** | Human authorized, awaiting trigger | EXECUTING | `approver_id` in org roster |
| **EXECUTING** | Intent recorded, API call in progress | EXECUTED, FAILED, EXECUTING* | DB write succeeded |
| **EXECUTED** | API + audit both succeeded | Terminal | Meta API 200 + DB update OK |
| **FAILED** | API or DB failed before completion | Terminal | Exception thrown |
| **EXECUTING*** | Zombie: API succeeded, DB failed | EXECUTED (via reconciliation) | Reconciliation job confirms |

## API Endpoints

### POST `/api/v1/autonomous/execute`
Submit an autonomous action for evaluation and potential execution.

**Request:**
```json
{
  "account_id": "acct_123",
  "org_id": "org_456",
  "action_type": "budget_increase",
  "params": {"campaign_id": "camp_789", "amount": 500},
  "idempotency_key": "acct_123:budget_increase:abc123:20260524"
}
```

**Responses:**
- `200` + status: `"EXECUTED"` — Auto-execution successful
- `200` + status: `"PENDING_APPROVAL"` — Requires human approval
- `202` + status: `"SYNC_REQUIRED"` — Stale audit, async refresh triggered
- `403` — Autonomy halted for this account
- `422` — No historical audit found

### POST `/api/v1/autonomous/{action_id}/approve`
Approve or reject a pending action.

**Request:**
```json
{
  "approver_id": "auth_admin_1",
  "status": "APPROVED"
}
```

**Guard**: `approver_id` must exist in the action's organization roster.

**Note**: v0.3 does not auto-execute upon approval. A separate trigger (background worker or manual API call) moves `APPROVED` → `EXECUTING`.

## Known Implementation Issues
| Bug | Impact | Fix |
| :--- | :--- | :--- |
| `get_system_state()` instead of `get_autonomy_state(account_id)` | Global kill switch — one bad tenant disables all | Use per-account autonomy table |
| Synchronous `run_full_sync()` | 5–30s latency per request, Meta API rate limit exhaustion | Use cached eligibility |
| No idempotency check at entry | Double-spend risk on retries | Check `idempotency_key` first |
| Broken three-phase exception handling | Incorrect status logging, zombie states unhandled | Replace with clean file |
| `auth_` prefix auth check | Security theater — trivially bypassed | Use org roster lookup |

## Next Steps
1. **Apply clean files**: Replace `autonomous.py` and `warehouse.py` with production-ready versions.
2. **Run guardrail tests**: `pytest tests/test_autonomous_guardrails.py -v`
3. **Enable reconciliation job**: Schedule 5-minute cron for zombie recovery.
4. **Configure alerting**: Set up P1/P2/P3 thresholds in your monitoring stack.

Document Version: 0.3.0
Last Updated: 2026-05-24
Owner: TrueROAS Engineering