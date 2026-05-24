import polars as pl

def validate_raw_shopify_contract(df: pl.DataFrame) -> pl.DataFrame:
    """
    Validates the structure of incoming raw Shopify data.
    Fails early if critical contract fields are missing.
    """
    required_fields = ["order_id", "email_hash", "total_price", "created_at"]
    
    missing_fields = [field for field in required_fields if field not in df.columns]
    if missing_fields:
        raise ValueError(f"[Stage 0 Contract Error] Missing required schema fields: {missing_fields}")
    
    # Force strict type compliance
    return df.with_columns([
        pl.col("order_id").cast(pl.Utf8),
        pl.col("email_hash").cast(pl.Utf8),
        pl.col("total_price").cast(pl.Float64),
        pl.col("created_at").cast(pl.Datetime)
    ])