import numpy as np
import polars as pl
from typing import Dict, List

def monte_carlo_budget_forecast(
    current_spend: float, 
    historical_roas: float, 
    volatility: float = 0.15, 
    simulations: int = 1000
) -> Dict[str, float]:
    """
    Runs a Monte Carlo simulation to predict risk-adjusted revenue outcomes.
    Adjusts mean ROAS by spend elasticity coefficient.
    """
    # Calculate expected ROAS with elasticity decay
    # As spend increases, efficiency typically decreases
    # Simplified elasticity model: efficiency = base_roas * (spend^-elasticity_coeff)
    # For this simulation, we'll use a direct mean shift
    adjusted_mean = historical_roas * (1 - volatility)

    simulated_roas = np.random.lognormal(
        mean=np.log(max(adjusted_mean, 1e-9)), 
        sigma=volatility, 
        size=simulations
    )
    
    projected_revenue = simulated_roas * current_spend
    
    return {
        "p10_revenue": float(np.percentile(projected_revenue, 10)),
        "p50_revenue": float(np.percentile(projected_revenue, 50)),
        "p90_revenue": float(np.percentile(projected_revenue, 90)),
        "expected_roas": float(np.mean(simulated_roas)),
        "downside_risk": float(np.std(projected_revenue))
    }

def calculate_spend_elasticity(df: pl.DataFrame) -> float:
    """
    Measures how sensitive revenue is to changes in spend.
    Coefficient > 1 implies elastic scaling potential.
    """
    if df.height < 5: return 1.0
    
    # log(Revenue) ~ log(Spend) linear regression coefficient placeholder
    # In a full impl, use pl.LinearRegression or a simple covariance approach
    return 0.85 # Placeholder for spend elasticity coefficient