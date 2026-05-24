# TrueROAS — Gemini Code Assist Prompt Pack
Source: TrueROAS_structure.md | Build Order: Sequential | Tool: VS Code + Gemini Code Assist

> Instructions: Execute prompts in order. For each prompt: 1) Create the file, 2) Paste the PROMPT block into Gemini, 3) Review code, 4) Commit. Do not skip.

---

## PROMPT 001 — Project Bootstrap
**Target:** `setup.sh` (run once)
**PROMPT:**
```
You are a principal Python engineer. Generate a bash script that creates the full TrueROAS project skeleton per spec:

Directories:
trueroas/
├── src/trueroas/ingestion/
├── src/trueroas/pipeline/
├── src/trueroas/core/
├── src/trueroas/audit/
├── src/trueroas/warehouse/
├── src/trueroas/api/routes/
├── tests/
├── data/raw/
├── data/clean/
├── config/
├── docker/

Also create empty __init__.py in every Python package directory. Use Python 3.11 conventions. Output only the bash script.
```
**Acceptance:** All dirs exist, `tree trueroas` matches structure.md.

---

## PROMPT 002 — Dependencies
**Target:** `pyproject.toml`
**PROMPT:**
```
Create pyproject.toml for project "trueroas" v0.1.0. Use hatchling build-backend. Dependencies:
polars>=1.0, duckdb>=1.0, fastapi, uvicorn[standard], pydantic>=2.7, pydantic-settings, prefect>=2.14, python-dotenv, requests, pyyaml, pytest.
Dev: ruff, black, mypy. Require python>=3.11.
```

---

## PROMPT 003 — Global Settings File
**Target:** `config/settings.yaml`
**PROMPT:**
```
Generate settings.yaml:
timezone: "Asia/Ulaanbaatar"
currency_base: "USD"
attribution_default: "7d_click_1d_view"
meta_api_version: "v19.0"
paths:
  raw: "data/raw"
  clean: "data/clean"
  warehouse: "data/warehouse.duckdb"
```

---

## PROMPT 004 — Config Loader
**Target:** `src/trueroas/config.py`
**PROMPT:**
```
Write config.py using Pydantic BaseSettings. Load config/settings.yaml and .env variables: FB_ACCESS_TOKEN, FB_APP_ID, FB_APP_SECRET. Provide get_settings() cached function. Validate timezone with zoneinfo. Export Settings class.
```

---

## PROMPT 005 — Data Schemas
**Target:** `src/trueroas/ingestion/schemas.py`
**PROMPT:**
```
Create Pydantic v2 models:
1. FBInsightRaw: date:date, account_id:str, campaign_id:str, adset_id:str, ad_id:str, spend:float, impressions:int, reach:int, clicks:int, lpv:int, purchases:int, purchase_value:float, attribution_setting:str
2. EventClean: event_id:str, event_time:datetime, fbp:str|None, fbc:str|None, source:Literal['pixel','capi'], event_name:str, value:float, is_duplicate:bool=False, is_invalid:bool=False, if_factor:float=1.0
Add ConfigDict(from_attributes=True).
```

---

## PROMPT 006 — Meta API Client
**Target:** `src/trueroas/ingestion/fb_client.py`
**PROMPT:**
```
Implement FBClient. Init with access_token, app_id, app_secret, version from config. Method get_insights(account_id:str, since:str, until:str) -> pl.DataFrame. 
Requirements: 
- Use requests with exponential backoff on 429/500/4xx.
- Handle pagination via 'paging.next'.
- Fields: campaign_id, adset_id, ad_id, spend, impressions, reach, clicks, actions, action_values.
- Convert to Polars, cast to FBInsightRaw schema.
- Add retry=5, sleep base=60s.
```

---

## PROMPT 007 — CAPI Ingest
**Target:** `src/trueroas/ingestion/capi_ingest.py`
**PROMPT:**
```
Function ingest_capi_events(file_path:str) -> pl.DataFrame. Read JSON lines, map to EventClean. Deduplicate by event_id keeping first. Prioritize source='capi' if conflict with pixel. Write parquet to data/raw/capi_{date}.parquet. Return df.
```

---

## PROMPT 008 — Pipeline Stage 1 Technical
**Target:** `src/trueroas/pipeline/stage1_technical.py`
**PROMPT:**
```
Function clean_technical(df:pl.DataFrame) -> pl.DataFrame using Polars. 
Steps: drop nulls on [date, campaign_id, spend]; cast date to Asia/Ulaanbaatar; ensure spend, purchase_value are Float64; round to 4 decimals. Return df.
```

---

## PROMPT 009 — Pipeline Stage 2 Invalid Traffic
**Target:** `src/trueroas/pipeline/stage2_invalid.py`
**PROMPT:**
```
Function flag_invalid(df:pl.DataFrame) -> pl.DataFrame. Add is_invalid bool column. True if: (clicks>0 and lpv/clicks < 0.1) OR (impressions>0 and clicks/impressions > 0.2). Use when expressions. Do not drop rows.
```

---

## PROMPT 010 — Pipeline Stage 3 Deduplication
**Target:** `src/trueroas/pipeline/stage3_dedup.py`
**PROMPT:**
```
Function dedup_events(df:pl.DataFrame) -> pl.DataFrame. Key: event_id. Sort by source (capi>pixel) then event_time. Keep first within 48h window. Add is_duplicate flag for removed ones. Use group_by_dynamic.
```

---

## PROMPT 011 — Pipeline Stage 4 Attribution
**Target:** `src/trueroas/pipeline/stage4_attribution.py`
**PROMPT:**
```
Function normalize_attribution(df:pl.DataFrame, target:str="7d_click_1d_view") -> pl.DataFrame. Copy attribution_setting to orig_attribution. Set normalized_attribution = target. Placeholder for future model.
```

---

## PROMPT 012 — Pipeline Stage 5 Overlap
**Target:** `src/trueroas/pipeline/stage5_overlap.py`
**PROMPT:**
```
Function correct_overlap(df:pl.DataFrame) -> pl.DataFrame. For each date+adset_id, compute reach_dedup = reach * 0.85 as placeholder. Add column. Comment: replace with inclusion-exclusion later.
```

---

## PROMPT 013 — Pipeline Stage 6 Outlier
**Target:** `src/trueroas/pipeline/stage6_outlier.py`
**PROMPT:**
```
Function flag_outliers(df:pl.DataFrame) -> pl.DataFrame. Use IQR on spend and purchase_value. Add is_outlier bool. Add seasonality_flag bool True if date in (Naadam: July 11-15, 11.11: Nov 11). Use Polars date functions.
```

---

## PROMPT 014 — Pipeline Stage 7 Incrementality
**Target:** `src/trueroas/pipeline/stage7_incrementality.py`
**PROMPT:**
```
Functions: 
1. calculate_if(test_cr:float, control_cr:float)->float: return max(0, min(1, (test_cr-control_cr)/test_cr)) if test_cr>0 else 0.
2. apply_if(df:pl.DataFrame, if_factor:float)->pl.DataFrame: add if_factor column.
```

---

## PROMPT 015 — Core Metrics
**Target:** `src/trueroas/core/metrics.py`
**PROMPT:**
```
Implement:
def true_roas(spend:float, revenue:float, refund_rate:float=0, if_factor:float=1)->float:
    return (revenue*(1-refund_rate)*if_factor)/max(spend,1e-9)
def true_cac(spend:float, new_customers:int, if_factor:float=1)->float
def mer(total_revenue:float, total_spend:float)->float
def poas(revenue:float, cogs:float, spend:float)->float
def marginal_roas(df:pl.DataFrame)->float using diff.
Add docstrings with formulas.
```

---

## PROMPT 016 — Cohort LTV
**Target:** `src/trueroas/core/cohort.py`
**PROMPT:**
```
Function calculate_ltv(events:pl.DataFrame)->pl.DataFrame. Assume events has customer_id, event_time, value. Derive first_purchase_date per customer. Compute cumulative revenue at D7, D30, D90. Return cohort df with columns cohort_date, d7_ltv, d30_ltv, d90_ltv.
```

---

## PROMPT 017 — Creative Fatigue
**Target:** `src/trueroas/core/fatigue.py`
**PROMPT:**
```
Function creative_fatigue(ctr0:float, frequency:float, k:float=0.15)->float: return ctr0*math.exp(-k*frequency). 
Function flag_fatigue(df:pl.DataFrame)->pl.DataFrame: add fatigue_risk bool where frequency>5 and ctr<0.005.
```

---

## PROMPT 018 — Audit Rules
**Target:** `src/trueroas/audit/rules.yaml` + `src/trueroas/audit/scorer.py`
**PROMPT:**
```
First create rules.yaml:
- id: R01, name: "Zero Purchase Spend", condition: "spend>0 & purchases==0", window: "3d", weight: 10
- id: R07, name: "High Frequency Fatigue", condition: "frequency>5 & ctr<0.005", weight: 8
- id: R12, name: "View-through Inflation", condition: "view_through_share>0.6", weight: 7
- id: R18, name: "CAPI Coverage Low", condition: "capi_coverage<0.7", weight: 9

Then write scorer.py: load yaml, evaluate each rule against df using Polars, sum failed weights, return score = 100 - total. Function score_account(df:pl.DataFrame)->int.
```

---

## PROMPT 019 — DuckDB Warehouse
**Target:** `src/trueroas/warehouse/duck.py`
**PROMPT:**
```
Class DuckDB: init with db_path from settings. Methods: connect(), write_table(df:pl.DataFrame, table:str), read_table(table:str)->pl.DataFrame, execute(sql:str). Use duckdb.connect, enable polars integration.
```

---

## PROMPT 020 — FastAPI Layer
**Target:** `src/trueroas/api/main.py`
**PROMPT:**
```
Create FastAPI app `app`. Add CORS. Endpoints:
POST /v1/ingest/run -> body: account_id, since, until. Calls FBClient + pipeline stages 1-7, writes to DuckDB. Returns {"status":"ok"}.
GET /v1/metrics/true-roas?account_id=... -> reads warehouse, computes true_roas via core.metrics, returns JSON.
GET /v1/audit/{account_id} -> runs scorer, returns score + failed_rules.
Use Depends(get_settings).
```

---

## PROMPT 021 — Unit Tests
**Target:** `tests/test_metrics.py`
**PROMPT:**
```
Write pytest for true_roas: test case 300 revenue, 100 spend, 0.1 refund, 0.8 IF => 2.16. Test zero spend => 0. Test if_factor 0 => 0. Use pytest.mark.parametrize.
```

---

## PROMPT 022 — Dockerfile
**Target:** `docker/Dockerfile`
**PROMPT:**
```
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install .
COPY src ./src
CMD ["uvicorn","src.trueroas.api.main:app","--host","0.0.0.0","--port","8000"]
```

---

## PROMPT 023 — Prefect Flow
**Target:** `src/trueroas/flows.py`
**PROMPT:**
```
Create Prefect flow daily_trueroas(account_id:str). Tasks: ingest(account_id), run_pipeline(df), compute_metrics(), audit_score(), export(). Schedule: cron="0 6 * * *" timezone="Asia/Ulaanbaatar". Use @flow, @task.
```

---
End of Prompt Pack. Execute sequentially with Gemini Code Assist.
