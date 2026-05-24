import polars as pl

def calculate_ltv(events: pl.DataFrame) -> pl.DataFrame:
    """
    Calculates Cohort LTV (Lifetime Value) at D7, D30, and D90 intervals.
    
    Formula: Cumulative Revenue within N days / Total Unique Customers in Cohort
    
    Args:
        events: Polars DataFrame with columns: customer_id, event_time, value.
        
    Returns:
        Polars DataFrame with: cohort_date, d7_ltv, d30_ltv, d90_ltv.
    """
    # Ensure event_time is treated as a datetime for accurate delta calculations
    df = events.with_columns(pl.col("event_time").cast(pl.Datetime))

    # 1. Derive first_purchase_date per customer to define their cohort
    cohort_map = df.group_by("customer_id").agg([
        pl.col("event_time").min().dt.date().alias("cohort_date"),
        pl.col("event_time").min().alias("first_purchase_time")
    ])

    # 2. Join cohort data back and compute days since first purchase
    df = df.join(cohort_map, on="customer_id")
    df = df.with_columns(
        (pl.col("event_time") - pl.col("first_purchase_time")).dt.total_days().alias("days_since")
    )

    # 3. Aggregate cumulative revenue at D7, D30, and D90 and divide by cohort size
    result = (
        df.group_by("cohort_date")
        .agg([
            pl.col("customer_id").n_unique().alias("cohort_size"),
            (pl.col("value").filter(pl.col("days_since") <= 7).sum() / pl.col("customer_id").n_unique()).alias("d7_ltv"),
            (pl.col("value").filter(pl.col("days_since") <= 30).sum() / pl.col("customer_id").n_unique()).alias("d30_ltv"),
            (pl.col("value").filter(pl.col("days_since") <= 90).sum() / pl.col("customer_id").n_unique()).alias("d90_ltv"),
        ])
        .select(["cohort_date", "d7_ltv", "d30_ltv", "d90_ltv"])
        .sort("cohort_date")
    )

    return result