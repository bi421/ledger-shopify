# TrueROAS — Internal Structure (structure.md)

Version: 0.1 | Date: 2026-05-24

## 1\. Mission

TrueROAS is a Marketing Truth Engine that transforms dirty Meta Ads API data into mathematically verified business metrics. Not a dashboard — an audit layer.

Core output: True ROAS, True CAC, MER, POAS, Incremental Lift.

## 2\. System Architecture

```
\[Meta Marketing API, CAPI, CSV] 
        ↓
  Ingestion Service (Python)
        ↓
  Raw Lake (/data/raw/\*.parquet)
        ↓
  7-Stage Cleaning Pipeline
        ↓
  Analytics Warehouse (DuckDB)
        ↓
  Math Engine
        ↓
  API + Reporting (FastAPI + Streamlit)
```

## 3\. Tech Stack

* Python 3.11, Polars, DuckDB, Pydantic v2
* FastAPI, Uvicorn
* Prefect (orchestration)
* Docker, GitHub Actions
* Streamlit (internal UI)

## 4\. Repository Structure

```
/trueroas/
├── src/
│   ├── trueroas/
│   │   ├── \_\_init\_\_.py
│   │   ├── config.py
│   │   ├── ingestion/
│   │   │   ├── fb\_client.py          # Marketing API wrapper with backoff
│   │   │   ├── capi\_ingest.py        # Server events
│   │   │   └── schemas.py            # Pydantic models
│   │   ├── pipeline/
│   │   │   ├── stage1\_technical.py    # nulls, timezone Asia/Ulaanbaatar
│   │   │   ├── stage2\_invalid.py      # bots, CTR>0.2, dwell<1s
│   │   │   ├── stage3\_dedup.py        # event\_id, CAPI priority
│   │   │   ├── stage4\_attribution.py  # normalize 7d/1d
│   │   │   ├── stage5\_overlap.py      # reach de-dup
│   │   │   ├── stage6\_outlier.py      # IQR, Z-score
│   │   │   └── stage7\_incrementality.py # geo holdout IF
│   │   ├── core/
│   │   │   ├── metrics.py             # true\_roas, true\_cac, mer, poas
│   │   │   ├── cohort.py              # LTV D7/D30/D90
│   │   │   ├── mmm\_lite.py            # Bayesian saturation
│   │   │   └── fatigue.py             # CTR decay model
│   │   ├── audit/
│   │   │   ├── rules.yaml             # 30 checks
│   │   │   └── scorer.py              # 0-100 score
│   │   ├── warehouse/
│   │   │   └── duck.py                # DuckDB connection
│   │   └── api/
│   │       ├── main.py                # FastAPI
│   │       └── routes/
│   ├── tests/
│   │   ├── test\_metrics.py
│   │   └── test\_pipeline.py
├── data/
│   ├── raw/
│   ├── clean/
│   └── warehouse.duckdb
├── config/
│   ├── settings.yaml
│   └── business\_rules.yaml
├── docker/
│   └── Dockerfile
├── pyproject.toml
└── README.md
```

## 5\. Data Schemas

### 5.1 fb\_insights\_raw

* date, account\_id, campaign\_id, adset\_id, ad\_id
* spend, impressions, reach, clicks, lpv
* purchases, purchase\_value, attribution\_setting

### 5.2 events\_clean

* event\_id PK, event\_time, fbp, fbc, source, event\_name, value
* is\_duplicate BOOL, is\_invalid BOOL, if\_factor FLOAT

## 6\. Core Math (src/trueroas/core/metrics.py)

```python
def true\_roas(spend: float, revenue: float, refund\_rate: float, if\_factor: float) -> float:
    return (revenue \* (1 - refund\_rate) \* if\_factor) / max(spend, 1e-9)

def true\_cac(spend: float, new\_customers: int, if\_factor: float) -> float:
    return spend / max(new\_customers \* if\_factor, 1)

def mer(total\_revenue: float, total\_spend: float) -> float:
    return total\_revenue / max(total\_spend, 1e-9)

def marginal\_roas(df) -> float:
    # Polars implementation
    return df.sort("date").with\_columns(
        d\_rev = pl.col("revenue").diff(),
        d\_spend = pl.col("spend").diff()
    ).filter(pl.col("d\_spend") > 0).select((pl.col("d\_rev")/pl.col("d\_spend")).mean()).item()
```

## 7\. 7-Stage Pipeline Details

1. Technical: timezone to UTC+8, currency MNT→USD
2. Invalid: ASN datacenter list, CTR>20%, bounce rate
3. De-dup: 48h window, keep CAPI
4. Attribution: force baseline, store delta
5. Overlap: inclusion-exclusion for reach
6. Outlier: IQR, flag Naadam/11.11
7. Incrementality: IF = (test\_cr - control\_cr)/test\_cr

## 8\. Audit Engine (rules.yaml excerpt)

* R01: spend>0 AND purchases==0 for 3d → weight 10
* R07: frequency>5 AND ctr<0.005 → weight 8
* R12: view\_through\_share>0.6 → weight 7
* R18: capi\_coverage<0.7 → weight 9
Score = 100 - Σ(weight \* failed)

## 9\. API (FastAPI)

* POST /v1/ingest/run
* GET /v1/audit/{account\_id}?from=2026-04-01\&to=2026-05-24
* GET /v1/metrics/true-roas?campaign\_id=...
* Response model: TrueROASReport

## 10\. Orchestration

Prefect flow `daily\_trueroas` runs 06:00 ULAT:
ingest → clean → compute → score → export

## 11\. Testing Strategy

* Unit: metrics with pytest
* Integration: pipeline on sample parquet
* Golden dataset: known dirty input → expected true output

## 12\. Roadmap

v0.1: stages 1-3 + true\_roas
v0.2: full 7 stages + audit score
v0.3: MMM lite + Streamlit UI
v1.0: multi-platform (TikTok)

