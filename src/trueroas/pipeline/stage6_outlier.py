import polars as pl

def flag_outliers(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """
    Stage 6: Outlier Detection and Seasonality Flagging.
    Uses Interquartile Range (IQR) on spend and purchase_value.
    Adds flags for Mongolian seasonality (Naadam and 11.11).
    """
    # Calculate IQR for spend
    q1_spend = df["spend"].quantile(0.25)
    q3_spend = df["spend"].quantile(0.75)
    iqr_spend = q3_spend - q1_spend
    
    # Calculate IQR for purchase_value
    q1_pv = df["purchase_value"].quantile(0.25)
    q3_pv = df["purchase_value"].quantile(0.75)
    iqr_pv = q3_pv - q1_pv
    
    date_expr = (
        pl.col("clean_date")
        if "clean_date" in df.columns
        else pl.col("date").str.to_datetime(format="%Y-%m-%d %H:%M:%S", strict=False)
    )

    df_flagged = df.with_columns([
        # Outlier flag
        (
            (pl.col("spend") < (q1_spend - 1.5 * iqr_spend)) | 
            (pl.col("spend") > (q3_spend + 1.5 * iqr_spend)) |
            (pl.col("purchase_value") < (q1_pv - 1.5 * iqr_pv)) | 
            (pl.col("purchase_value") > (q3_pv + 1.5 * iqr_pv))
        ).alias("is_outlier"),
        
        # Seasonality flag: Naadam (July 11-15) or 11.11 (Nov 11)
        (
            ((date_expr.dt.month() == 7) & (date_expr.dt.day() >= 11) & (date_expr.dt.day() <= 15)) |
            ((date_expr.dt.month() == 11) & (date_expr.dt.day() == 11))
        ).alias("seasonality_flag")
    ])

    metadata = {
        "outlier_count": df_flagged.filter(pl.col("is_outlier")).height,
        "seasonality_detected": df_flagged.filter(pl.col("seasonality_flag")).height > 0
    }
    
    return df_flagged, metadata
