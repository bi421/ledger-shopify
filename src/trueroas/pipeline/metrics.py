import polars as pl

def true_roas(spend: float, revenue: float, refund_rate: float = 0, if_factor: float = 1) -> float:
    """
    Formula: (Revenue * (1 - Refund Rate) * IF) / Spend
    """
    return (revenue * (1 - refund_rate) * if_factor) / max(spend, 1e-9)

def true_cac(spend: float, new_customers: int, if_factor: float = 1) -> float:
    """
    Formula: Spend / (New Customers * IF)
    """
    return spend / max(new_customers * if_factor, 1)

def marginal_roas(df: pl.DataFrame) -> float:
    """
    Formula: ΔRevenue / ΔSpend (calculated as mean of differences)
    """
    return df.sort("clean_date").with_columns(
        d_rev = pl.col("true_revenue").diff(),
        d_spend = pl.col("normalized_spend").diff()
    ).filter(pl.col("d_spend") > 0).select(
        (pl.col("d_rev") / pl.col("d_spend")).mean()
    ).item()