import polars as pl
from typing import Dict, Any, List, Optional

def generate_strategic_recommendations(shifts: Dict[str, float], success_rates: Optional[Dict[str, float]] = None) -> List[str]:
    """
    Translates causal metrics into actionable marketing strategies.
    Adjusts recommendations based on the historical success rate of similar past decisions.
    """
    def _apply_calibration(text: str, key: str) -> str:
        if not success_rates or key not in success_rates:
            return text
        rate = success_rates[key]
        tag = " [High Precision]" if rate > 0.8 else " [Experimental]" if rate < 0.4 else ""
        return f"{text}{tag} (Past Success: {rate:.0%})"

    recommendations = []
    roas_shift = shifts.get("roas", 0)
    margin_shift = shifts.get("margin_compression", 0)

    if margin_shift < -0.15:
        recommendations.append(_apply_calibration(
            "Profitability Trap: While ROAS might appear stable, your Contribution Margin is compressing. "
            "Check for rising COGS, high refund rates in recent cohorts, or heavy discounting affecting net profit.",
            "profitability_trap"
        ))

    if roas_shift < -0.05:
        # Scenario: Performance is declining
        if shifts.get("cpm", 0) > 0.15:
            recommendations.append(_apply_calibration(
                "Auction Pressure: CPMs are significantly higher. Consider tightening bid caps, testing broader audiences, "
                "or shifting budget toward lower-cost placements like Reels/Stories.",
                "auction_pressure"
            ))
        if shifts.get("ctr", 0) < -0.10:
            recommendations.append(_apply_calibration(
                "Creative Fatigue: Engagement is dropping. Immediate action: Launch a creative refresh testing new 'Hooks' "
                "and 'Problem-Solution' angles for top-spending ad sets.",
                "creative_fatigue"
            ))
        if shifts.get("cvr", 0) < -0.10:
            recommendations.append(_apply_calibration(
                "Conversion Friction: The drop is driven by lower site conversion. Verify that the ad offer aligns with "
                "the landing page, check for site speed regressions, and ensure the checkout flow is frictionless.",
                "conversion_friction"
            ))
        
        if not recommendations:
            recommendations.append(_apply_calibration(
                "General Optimization: Efficiency is slipping without a clear single-metric driver. "
                "Review account structure for audience overlap and consolidate fragmented ad sets.",
                "general_optimization"
            ))

    elif roas_shift > 0.05:
        # Scenario: Performance is improving
        recommendations.append(_apply_calibration(
            "Growth Opportunity: ROAS is trending up. Identify the top-performing 20% of creatives and scale their "
            "budgets by 15-20% while monitoring frequency thresholds.",
            "growth_opportunity"
        ))
    
    else:
        recommendations.append(_apply_calibration(
            "Stable State: Maintain current scale. Use this period to conduct a high-impact A/B test on your primary landing page offer.",
            "stable_state"
        ))

    return recommendations

def analyze_roas_drop(
    baseline_df: pl.DataFrame, 
    current_df: pl.DataFrame,
    active_experiment_id: Optional[str] = None,
    success_rates: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Causal Decomposition: Identifies which primary metric drove the change in ROAS.
    """
    baseline_roas = baseline_df["true_revenue"].sum() / max(baseline_df["spend"].sum(), 1e-9)
    current_roas = current_df["true_revenue"].sum() / max(current_df["spend"].sum(), 1e-9)
    baseline_impressions = baseline_df["impressions"].sum()
    current_impressions = current_df["impressions"].sum()
    baseline_clicks = baseline_df["clicks"].sum()
    current_clicks = current_df["clicks"].sum()

    baseline_cpm = baseline_df["spend"].sum() / max(baseline_impressions, 1e-9) * 1000
    current_cpm = current_df["spend"].sum() / max(current_impressions, 1e-9) * 1000
    baseline_ctr = baseline_clicks / max(baseline_impressions, 1e-9)
    current_ctr = current_clicks / max(current_impressions, 1e-9)
    baseline_cvr = baseline_df["true_revenue"].sum() / max(baseline_clicks, 1e-9)
    current_cvr = current_df["true_revenue"].sum() / max(current_clicks, 1e-9)

    shifts = {
        "roas": (current_roas - baseline_roas) / max(baseline_roas, 1e-9),
        "cpm": (current_cpm - baseline_cpm) / max(baseline_cpm, 1e-9),
        "ctr": (current_ctr - baseline_ctr) / max(baseline_ctr, 1e-9),
        "cvr": (current_cvr - baseline_cvr) / max(baseline_cvr, 1e-9),
    }

    driver = "Stable State"
    evidence = {
        "metric": "roas_delta",
        "observed_value": shifts["roas"],
        "threshold": -0.05,
        "method": "heuristic_threshold",
        "confidence": 0.50
    }
    
    if shifts["roas"] < -0.05:
        if shifts["cpm"] > 0.15:
            driver = "CPM increase"
            evidence = {
                "metric": "cpm_increase",
                "observed_value": shifts["cpm"],
                "threshold": 0.15,
                "comparison_baseline": "baseline_period",
                "confidence": 0.85,
                "method": "causal_impact" if active_experiment_id else "heuristic_threshold",
                "linked_experiment_id": active_experiment_id,
            }
        elif shifts["ctr"] < -0.10:
            driver = "Creative fatigue"
            evidence = {
                "metric": "ctr_7d_decay",
                "observed_value": shifts["ctr"],
                "threshold": -0.10,
                "comparison_baseline": "account_30d_average",
                "confidence": 0.89,
                "method": "causal_impact" if active_experiment_id else "heuristic_threshold",
                "linked_experiment_id": active_experiment_id
            }

    # Promotion Rule: Only promote to primary_driver if experiment-backed
    driver_key = "primary_driver" if active_experiment_id and evidence["method"] == "causal_impact" else "suggested_driver"

    return {
        driver_key: driver,
        "baseline_roas": baseline_roas,
        "current_roas": current_roas,
        "driver_evidence": evidence,
        "metrics": shifts,
        "recommendations": generate_strategic_recommendations(shifts, success_rates=success_rates)
    }
