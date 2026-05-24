import polars as pl

def correct_overlap(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """
    Stage 5: Overlap Correction.
    For each date + adset_id, compute reach_dedup = reach * 0.85 as placeholder.
    Comment: replace with inclusion-exclusion later.
    """
    df_corrected = df.with_columns(
        (pl.col("reach") * 0.85).alias("reach_dedup")
    )
    metadata = {"overlap_coefficient": 0.85}
    return df_corrected, metadata