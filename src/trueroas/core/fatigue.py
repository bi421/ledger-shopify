import math
import polars as pl

def creative_fatigue(ctr0: float, frequency: float, k: float = 0.15) -> float:
    """
    Calculates the expected CTR after fatigue effects using an exponential decay model.
    Formula: ctr0 * exp(-k * frequency)
    """
    return ctr0 * math.exp(-k * frequency)

def flag_fatigue(df: pl.DataFrame) -> pl.DataFrame:
    """
    Flags rows where creative fatigue risk is high.
    Conditions: frequency > 5 and ctr < 0.005
    """
    return df.with_columns(
        fatigue_risk = (pl.col("frequency") > 5) & (pl.col("ctr") < 0.005)
    )