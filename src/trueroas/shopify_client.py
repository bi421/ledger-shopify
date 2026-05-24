import requests
from datetime import datetime
import logging

logger = logging.getLogger("ShopifyClient")

class ShopifyClient:
    """
    Client for interacting with the Shopify Admin API to fetch financial truth.
    Used for the weekly financial reconciliation circuit breaker.
    """
    def __init__(self, access_token: str, store_url: str):
        # Normalize store_url by removing protocols and trailing slashes
        self.store_url = store_url.replace("https://", "").replace("http://", "").rstrip("/")
        self.access_token = access_token
        self.base_url = f"https://{self.store_url}/admin/api/2024-04"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

    def get_settled_revenue(self, start_date: datetime, end_date: datetime) -> float:
        """
        Fetches the total price sum of all orders within the given time range.
        """
        url = f"{self.base_url}/orders.json"
        params = {
            "created_at_min": start_date.isoformat(),
            "created_at_max": end_date.isoformat(),
            "status": "any",
            "fields": "total_price"
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            orders = response.json().get("orders", [])
            total_revenue = sum(float(order["total_price"]) for order in orders)
            return total_revenue
        except Exception as e:
            logger.error(f"Failed to fetch Shopify revenue for range {start_date} - {end_date}: {e}")
            raise