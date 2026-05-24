import polars as pl

def dedup_events(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Stage 3: Multi-source Event Deduplication (PROMPT 010)."""
    if "event_id" not in df.columns:
        return df, {"duplicates_removed": 0}
        
    initial_count = df.height
    if "source" not in df.columns:
        df = df.with_columns(source=pl.lit("unknown"))

    # 1. Prioritize CAPI over Pixel by sorting
    # 2. Within 48h windows, keep the first occurrence
    df_deduped = df.sort(
        ["event_id", "source", "clean_date"], 
        descending=[False, True, False]
    ).with_columns(
        is_duplicate = pl.col("event_id").is_duplicated() & 
                       (pl.col("clean_date") != pl.col("clean_date").min().over("event_id"))
    ).filter(
        ~pl.col("is_duplicate")
    )

    metadata = {"duplicates_removed": initial_count - df_deduped.height}
    return df_deduped, metadata
