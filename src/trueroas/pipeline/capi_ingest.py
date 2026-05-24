import polars as pl
from datetime import datetime
from src.trueroas.schemas import EventClean

def ingest_capi_events(file_path: str) -> pl.DataFrame:
    """
    Function ingest_capi_events (PROMPT 007).
    Reads JSON lines, maps to EventClean, and deduplicates.
    """
    # Read JSON lines
    df = pl.read_ndjson(file_path)
    
    # Map and Deduplicate: prioritize capi over pixel if both exist for same event_id
    df = df.sort(["event_id", "source"], descending=[False, True]).unique(subset=["event_id"], keep="first")
    
    # Cast to schema
    df = df.with_columns([
        pl.col("event_time").str.to_datetime(),
        pl.col("value").cast(pl.Float64)
    ])
    
    date_str = datetime.now().strftime("%Y%m%d")
    df.write_parquet(f"data/raw/capi_{date_str}.parquet")
    return df