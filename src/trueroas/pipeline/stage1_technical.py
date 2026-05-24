import polars as pl

def clean_technical(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Stage 1: Technical normalization and null handling (PROMPT 008)."""
    input_rows = df.height
    df_cleaned = df.with_columns(
        pl.col("date")
        .str.to_datetime(format="%Y-%m-%d %H:%M:%S", strict=False)
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone("Asia/Ulaanbaatar")
        .alias("clean_date")
    ).drop_nulls(
        subset=["date", "campaign_id", "spend"]
    ).with_columns([
        pl.col("spend").cast(pl.Float64).round(4),
        pl.col("purchase_value").cast(pl.Float64).round(4)
    ])

    metadata = {"input_rows": input_rows, "dropped_nulls": input_rows - df_cleaned.height}
    return df_cleaned, metadata