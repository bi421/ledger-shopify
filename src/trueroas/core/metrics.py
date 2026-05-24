import polars as pl
import numpy as np

def true_roas(spend: float, revenue: float, refund_rate: float = 0, if_factor: float = 1) -> float:
    """
    Calculates the True Return on Ad Spend.
    Formula: (Revenue * (1 - Refund Rate) * IF) / Spend
    """
    return (revenue * (1 - refund_rate) * if_factor) / max(spend, 1e-9)

def true_cac(spend: float, new_customers: int, if_factor: float = 1) -> float:
    """
    Calculates the True Customer Acquisition Cost.
    Formula: Spend / (New Customers * IF)
    """
    return spend / max(new_customers * if_factor, 1)

def mer(total_revenue: float, total_spend: float) -> float:
    """
    Calculates the Marketing Efficiency Ratio (Blended ROAS).
    Formula: Total Revenue / Total Spend
    """
    return total_revenue / max(total_spend, 1e-9)

def poas(revenue: float, cogs: float, spend: float) -> float:
    """
    Calculates Profit on Ad Spend.
    Formula: (Revenue - COGS) / Spend
    """
    return (revenue - cogs) / max(spend, 1e-9)

def contribution_margin(spend: float, revenue: float, cogs: float, refund_rate: float = 0, if_factor: float = 1) -> float:
    """
    Calculates the absolute dollar Contribution Margin.
    This represents the actual 'Financial Truth' of dollars added to the bank.
    Formula: (Revenue * (1 - Refund Rate) * IF) - COGS - Spend
    """
    net_revenue = revenue * (1 - refund_rate) * if_factor
    # Note: COGS should also be adjusted by the IF factor if they are variable costs tied to the incremental sale
    return net_revenue - (cogs * if_factor) - spend

def marginal_roas(df: pl.DataFrame) -> float:
    """
    Calculates the Marginal ROAS using the difference between consecutive periods.
    Formula: mean(ΔRevenue / ΔSpend)
    
    Args:
        df: Polars DataFrame containing 'clean_date', 'true_revenue', and 'normalized_spend'.
    
    Returns:
        The average marginal return on incremental spend.
    """
    if df.height < 2:
        return 0.0

    # Calculate differences in revenue and spend across the time series
    m_df = df.sort("clean_date").with_columns([
        pl.col("true_revenue").diff().alias("d_rev"),
        pl.col("normalized_spend").diff().alias("d_spend")
    ])

    # Filter for rows where spend actually changed to avoid division by zero
    result = m_df.filter(pl.col("d_spend") > 0).select(
        (pl.col("d_rev") / pl.col("d_spend")).mean().alias("m_roas")
    )

    return result.item() if not result.is_empty() and result.item() is not None else 0.0

def calculate_efficiency_decay(current_frequency: float, baseline_roas: float) -> float:
    """
    Milestone 4.4: Spend Elasticity Modeling.
    Predicts ROAS decay based on increasing ad frequency.
    """
    # Simple saturation curve: ROAS = Baseline * (1 / log(frequency + e))
    if current_frequency <= 1.0:
        return baseline_roas
    
    decay_factor = 1.0 / np.log(current_frequency + 1.718)
    return baseline_roas * decay_factor