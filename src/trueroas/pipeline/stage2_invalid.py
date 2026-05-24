import polars as pl

def flag_invalid(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Stage 2: Flag bots and impossible CTR/LPV ratios."""
    df_flagged = df.with_columns(
        is_invalid = pl.when(
            (pl.col("clicks") > 0) & (pl.col("lpv") / pl.col("clicks") < 0.1)
        ).then(pl.lit(True))
        .when(
            (pl.col("impressions") > 0) & (pl.col("clicks") / pl.col("impressions") > 0.2)
        ).then(pl.lit(True))
        .otherwise(pl.lit(False))
    )
    
    invalid_count = df_flagged.filter(pl.col("is_invalid")).height
    metadata = {"invalid_traffic_count": invalid_count}
    return df_flagged, metadata