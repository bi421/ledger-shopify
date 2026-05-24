import requests
import time
import random
import polars as pl
from typing import List
from src.trueroas.schemas import FBInsightRaw

class FBClient:
    def __init__(self, access_token: str, app_id: str, app_secret: str, version: str = "v19.0"):
        self.base_url = f"https://graph.facebook.com/{version}"
        self.params = {"access_token": access_token}

    def get_insights(self, account_id: str, since: str, until: str) -> pl.DataFrame:
        url = f"{self.base_url}/act_{account_id}/insights"
        params = {
            **self.params,
            "level": "ad",
            "time_range": f"{{'since':'{since}','until':'{until}'}}",
            "fields": "campaign_id,adset_id,ad_id,spend,impressions,reach,clicks,actions,action_values,attribution_setting",
            "limit": 500
        }
        
        all_data = []
        max_retries = 5
        
        while url:
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code in [429, 500, 503]:
                if max_retries > 0:
                    # Exponential backoff with jitter
                    sleep_time = (2 ** (6 - max_retries)) + random.uniform(0, 1)
                    time.sleep(sleep_time)
                    max_retries -= 1
                    continue
                response.raise_for_status()
            
            res_json = response.json()
            all_data.extend(res_json.get("data", []))
            url = res_json.get("paging", {}).get("next")
            params = {} # Params are in the 'next' URL
            
        return self._to_polars(all_data)

    def _to_polars(self, data: List[dict]) -> pl.DataFrame:
        # Logic to parse nested 'actions' and 'action_values' into purchases/purchase_value
        # and cast to FBInsightRaw schema
        return pl.from_dicts(data)