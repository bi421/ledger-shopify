import polars as pl

def calculate_true_roas(df: pl.DataFrame, refund_rate_col: str = "refund_rate", incrementality_factor_col: str = "incrementality_factor") -> pl.DataFrame:
    """
    Магик шүүлтүүрээр шүүгдсэн дата дээр тулгуурлан БОДИТ ROAS-ийг тооцоолно.
    Томъёо: True ROAS = (Түүхий Борлуулалт * (1 - Цуцлалтын Хувь) * Үр Өгөөжийн Коэффициент) / Нийт Зардал
    """
    return df.with_columns(
        (
            (pl.col("raw_revenue") * (1 - pl.col(refund_rate_col)) * pl.col(incrementality_factor_col)) 
            / pl.col("spend")
        ).alias("true_roas")
    )

def calculate_marginal_roas(df: pl.DataFrame) -> pl.DataFrame:
    """
    Нэмэлт зарцуулсан 1 төгрөг тутамд ямар хэмжээний өсөлт ирж байгааг тооцоолно (mROAS).
    Үүний тулд цаг хугацааны дараалалтай (time-series) дата шаардлагатай.
    Томъёо: mROAS = dRevenue / dSpend
    """
    # Өмнөх өдрийн зардал болон орлогыг шилжүүлж зөрүүг олох
    sorted_df = df.sort("date")
    
    return sorted_df.with_columns([
        (pl.col("raw_revenue") - pl.col("raw_revenue").shift(1)).alias("delta_revenue"),
        (pl.col("spend") - pl.col("spend").shift(1)).alias("delta_spend")
    ]).with_columns(
        (pl.col("delta_revenue") / pl.col("delta_spend")).alias("marginal_roas")
    ).drop(["delta_revenue", "delta_spend"])

def calculate_true_cac(df: pl.DataFrame, incrementality_factor_col: str = "incrementality_factor") -> pl.DataFrame:
    """
    Бодит Хэрэглэгч Элсүүлсэн Зардал (True CAC) тооцоолох.
    Томъёо: True CAC = Нийт Зардал / (Түүхий Худалдан Авалт * Үр Өгөөжийн Коэффициент)
    """
    return df.with_columns(
        (
            pl.col("spend") / (pl.col("raw_purchases") * pl.col(incrementality_factor_col))
        ).alias("true_cac")
    )