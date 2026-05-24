import polars as pl
from typing import Dict, Any, List, Optional
from src.trueroas.core.metrics import true_roas

class VerificationTier:
    VERIFIED = "RECONCILED"      # Deterministic, financial-match confirmed
    INFERRED = "STATISTICAL"     # Probabilistic, evidence-backed inference
    HEURISTIC = "HEURISTIC"      # Directional, based on historical priors
    DEGRADED = "UNSTABLE"        # Data drift detected, low trust

class AutomationPolicy:
    ACTIVE = "FULL_AUTOMATION"
    REVIEW = "ADVISORY_ONLY"
    HALTED = "CIRCUIT_BREAKER_TRIPPED"

class DecisionIntelligence:
    """
    Operational Decision Layer.
    Evaluates data integrity and reconciliation metrics to enforce budget automation policies.
    """

    def __init__(self, calibration_factor: float = 1.0, shadow_mode: bool = True):
        self.calibration_factor = calibration_factor
        self.shadow_mode = shadow_mode

    def formulate_decision(
        self,
        reasoning_report: Dict[str, Any],
        pipeline_meta: Dict[str, Any],
        simulation_results: Optional[Dict[str, Any]] = None,
        audit_score: int = 100
    ) -> Dict[str, Any]:
        
        # Initialize evidence chain early to avoid UnboundLocalError
        evidence = []
        deterministic = pipeline_meta.get("deterministic_layer", {})
        probabilistic = pipeline_meta.get("probabilistic_layer", {})
        metrics = reasoning_report.get("metrics", {})
        
        match_rate = deterministic.get("stitching", {}).get("match_rate", 0)
        calibration_error = abs(1.0 - self.calibration_factor)

        # 1. Extract context
        deterministic = pipeline_meta.get("deterministic_layer", {})
        probabilistic = pipeline_meta.get("probabilistic_layer", {})
        metrics = reasoning_report.get("metrics", {})
        
        # 2. Determine Truth Confidence
        match_rate = deterministic.get("stitching", {}).get("match_rate", 0)
        base_confidence = probabilistic.get("confidence", 0.5)
        calibration_error = abs(1.0 - self.calibration_factor)
        
        # Calibration Penalty: Confidence is weighted by historical probability of correctness
        # High calibration_error (drift) results in aggressive confidence reduction
        system_confidence = base_confidence * (audit_score / 100.0) * (1.0 - calibration_error)

        # 3. Determine Verification Tier
        truth_source = probabilistic.get("incrementality", {}).get("truth_source", "unknown")
        if truth_source != "default_prior" and match_rate > 90 and audit_score > 98:
            tier = VerificationTier.VERIFIED
        elif truth_source != "default_prior":
            tier = VerificationTier.INFERRED
        else:
            tier = VerificationTier.HEURISTIC

        # 4. Identify Primary Action and Causal Driver
        causal_driver = reasoning_report.get("primary_driver") or reasoning_report.get("suggested_driver", "Stable State")
        raw_recommendations = reasoning_report.get("recommendations", [])
        primary_action = raw_recommendations[0] if raw_recommendations else "Maintain current spend levels."

        # 5. Evaluate Financial Risk and Automation Safety
        risk_level = "LOW"
        blocked_actions = []
        automation_eligible = True
        policy = AutomationPolicy.ACTIVE

        # DATA QUALITY GATE
        if tier == VerificationTier.HEURISTIC or system_confidence < 0.85:
            automation_eligible = False
            policy = AutomationPolicy.REVIEW
            risk_level = "HIGH"
            blocked_actions.extend(["Autonomous Scaling", "Direct API Write"])

        # RECONCILIATION KILL-SWITCH
        if match_rate < 70 or calibration_error > 0.25:
            automation_eligible = False
            policy = AutomationPolicy.HALTED
            risk_level = "CRITICAL"
            blocked_actions.extend(["All Budget Adjustments", "Targeting Expansion"])

        # Safety Rule: Block scaling if margin is compressing regardless of ROAS
        if metrics.get("margin_compression", 0) < -0.10:
            risk_level = "CRITICAL"
            blocked_actions.append("Increase Budget")
            automation_eligible = False
        
        # ANOMALY DETECTION: Suspicious ROAS Spikes
        if metrics.get("roas", 0) > 8.0 and tier != VerificationTier.VERIFIED:
            risk_level = "CRITICAL"
            policy = AutomationPolicy.HALTED
            blocked_actions.append("All Automated Actions")
            evidence.append(f"ANOMALY: Suspicious ROAS spike ({metrics.get('roas', 0)}) detected without financial verification.")

        # 6. Synthesis of Evidence Chain
        evidence.extend([
            f"Financial Match Rate: {match_rate:.2f}%",
            f"Data Audit Score: {audit_score}/100",
            f"Verification Method: {reasoning_report.get('driver_evidence', {}).get('method', 'Heuristic Anomaly')}",
            f"Tier: {tier}",
            f"Calibration Error: {calibration_error:.4f}"
        ])

        # 7. Expected Impact (Linked to Monte Carlo Simulation)
        expected_impact = "Stability predicted."
        if simulation_results:
            p50_rev = simulation_results.get("p50_revenue", 0)
            expected_impact = f"Projected median revenue: ${p50_rev:,.2f} (Confidence: {system_confidence:.0%})"

        # 8. Construct Executive Decision Summary
        decision_summary = self._generate_summary(causal_driver, primary_action, risk_level)

        return {
            "decision_summary": decision_summary,
            "primary_action": primary_action,
            "expected_impact": expected_impact,
            "policy": {
                "tier": tier,
                "status": policy,
                "confidence": round(system_confidence, 4),
                "risk_level": risk_level,
                "automation_allowed": automation_eligible and not self.shadow_mode,
                "blocked_actions": blocked_actions,
            },
            "diagnostics": {
                "calibration_error": round(calibration_error, 4),
                "evidence_chain": evidence,
                "causal_driver": causal_driver,
                "shadow_mode": self.shadow_mode
            }
        }

    def _generate_summary(self, driver: str, action: str, risk: str) -> str:
        if risk == "CRITICAL":
            return f"CRITICAL: {driver} is destroying margin. Immediate manual intervention required."
        if risk == "HIGH":
            return f"CAUTION: Significant uncertainty detected in {driver}. Recommended action requires human audit."
        return f"System identifies {driver}. Operational path: {action}"