import polars as pl
from typing import Dict, Any, List, Optional

def interpret_metric(name: str, value: Any, confidence: float, tier: str = "HEURISTIC", trend: str = "Stable") -> Dict[str, Any]:
    """
    Standardizes metric display according to v0.3 Interpretation Rules.
    Ensures every metric includes meaning, status, and recommended action.
    """
    interpretations = {
        "Profit ROAS": {
            "meaning": f"For every $1 spent, the business generated ${value:.2f} in verified profit-adjusted revenue.",
            "why": "This is your core efficiency metric, stripped of attribution inflation.",
            "status": "Positive" if value > 1.2 else "Caution" if value > 0.8 else "Critical",
            "risk": "Verified match" if tier == "RECONCILED" else "Statistical model"
        },
        "True CAC": {
            "meaning": f"It costs ${value:.2f} in verified ad spend to acquire one customer.",
            "why": "Ensures acquisition costs stay below customer lifetime value (LTV).",
            "status": "Healthy" if confidence > 0.85 else "Uncertain",
            "risk": "Potential over-reporting from platform pixels" if confidence < 0.8 else "Verified match"
        },
        "Confidence Score": {
            "meaning": f"This analysis has a {value:.0%} statistical reliability score.",
            "why": "Determines if you can trust these numbers for autonomous scaling.",
            "status": "Strong" if value > 0.9 else "Developing",
            "risk": "Based on heuristic priors" if value < 0.75 else "Experiment-backed"
        }
    }

    base = interpretations.get(name, {
        "meaning": "Metric meaning not defined.",
        "why": "Context unavailable.",
        "status": "Neutral",
        "risk": "Unknown"
    })

    return {
        "name": name,
        "value": value,
        "verification_tier": tier,
        "meaning": base["meaning"],
        "why": base["why"],
        "confidence_display": f"{confidence:.0%} confidence based on verified reconciliation data.",
        "trend": trend,
        "status": base["status"],
        "risk_interpretation": base["risk"]
    }

def generate_executive_dashboard(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for the Metric Interpretation Layer.
    Transforms raw sync results into a Decision-First executive interface.
    """
    if result.get("status") == "error":
        return {"error": "Dashboard generation failed due to engine error."}

    det = result.get("deterministic_layer", {})
    prob = result.get("probabilistic_layer", {})
    dec = result.get("decision", {})
    meta = result.get("meta", {})

    policy = dec.get("policy", {})
    tier = policy.get("tier", "HEURISTIC")
    
    conf = meta.get("confidence", 0.0)
    truth_grade = meta.get("truth_grade", "C")

    # 1. Executive Summary (The 10-Second Rule)
    summary = {
        "headline": f"System identifies {dec.get('causal_driver', 'Stable State')}.",
        "trust_model": f"{tier} | {conf:.0%} Conf.",
        "cause": dec.get("decision_summary", "No significant variance detected."),
        "policy_status": policy.get("status", "REVIEW"),
        "next_action": dec.get("primary_action", "Maintain current pace.")
    }

    # 2. Metric Hierarchy Construction
    interpreted_metrics = {
        "performance": [
            interpret_metric("Profit ROAS", prob.get("incrementality", {}).get("point_estimate", 0.0), conf, tier=tier),
            interpret_metric("True CAC", 0.0, conf, tier=tier)
        ],
        "integrity": [
            interpret_metric("Confidence Score", conf, 1.0, tier="RECONCILED"),
            {
                "name": "Truth Grade",
                "value": truth_grade,
                "meaning": f"Verification Tier: {tier}",
                "color": "green" if truth_grade == "A" else "yellow" if truth_grade == "B" else "gray"
            }
        ],
        "risk_stability": {
            "level": dec.get("risk_level", "Medium"),
            "blocked_actions": dec.get("blocked_actions", []),
            "automation_eligible": dec.get("automation_eligible", False)
        }
    }

    # 3. Visual Prioritization Logic
    # Move Critical risk indicators to the top if detected
    if dec.get("risk_level") == "Critical":
        summary["headline"] = f"⚠️ CRITICAL RISK: {summary['headline']}"

    return {
        "executive_summary": summary,
        "metrics": interpreted_metrics,
        "decision_intelligence": {
            "primary_action": dec.get("primary_action"),
            "expected_impact": dec.get("expected_impact"),
            "evidence_chain": dec.get("evidence", [])
        },
        "visual_hints": {
            "primary_color": "blue" if tier == "RECONCILED" else "yellow" if tier == "STATISTICAL" else "gray",
            "risk_border": "red" if dec.get("risk_level") in ["HIGH", "CRITICAL"] else None,
            "show_confidence_bands": True,
            "separation_mode": "Fact vs Inference"
        }
    }

def flatten_truth_sync_result(result: Dict[str, Any]) -> pl.DataFrame:
    """
    Flattens the v0.3 Truth-Aware nested dictionary into a clean, 
    normalized Polars DataFrame suitable for CSV export.
    """
    if result.get("status") == "error":
        return pl.DataFrame()

    det = result.get("deterministic_layer", {})
    prob = result.get("probabilistic_layer", {})
    dec = result.get("decision", {})
    meta = result.get("meta", {})

    # Create a flat record for the CSV
    record = {
        "audit_id": meta.get("audit_id"),
        "account_id": meta.get("account_id"),
        "timestamp": meta.get("execution_timestamp"),
        "spend": det.get("spend", 0.0),
        "verified_revenue": det.get("verified_revenue", 0.0),
        "profit_roas": prob.get("incrementality", {}).get("point_estimate_roas", 0.0),
        "true_cac": prob.get("incrementality", {}).get("point_estimate_cac", 0.0),
        "duplicate_events_removed": det.get("duplicate_events_removed", 0),
        "bot_traffic_filtered": det.get("bot_traffic_filtered", 0),
        "match_rate": det.get("stitching", {}).get("match_rate", 0.0),
        "confidence": meta.get("confidence", 0.0),
        "risk_level": dec.get("risk_level"),
        "truth_grade": meta.get("truth_grade"),
        "primary_driver": dec.get("causal_driver"),
        "recommended_action": dec.get("primary_action"),
        "source": prob.get("incrementality", {}).get("truth_source")
    }

    return pl.DataFrame([record])

def export_to_csv(results: List[Dict[str, Any]], output_path: str):
    """
    Batch exports multiple sync results to a flat CSV.
    """
    dfs = [flatten_truth_sync_result(r) for r in results if r.get("status") != "error"]
    if not dfs:
        return
    
    final_df = pl.concat(dfs)
    final_df.write_csv(output_path)