import asyncio
from typing import Any, Dict, List, Optional

import httpx

from src.config import settings
from src.core.exceptions import MetaAPIError
from src.measurement.thresholds import MAX_SAMPLE_REELS


class MetaGraphClient:
    """
    Production-ready Async Meta Graph API Client.
    Handles authentication, pagination, rate limits (retries), and timeouts.
    """

    BASE_URL = settings.GRAPH_API_BASE
    TIMEOUT = 30.0  # seconds

    def __init__(self, access_token: str):
        # Token is injected upon instantiation (decrypted from DB or read from .env)
        self.access_token = access_token
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self.TIMEOUT,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        """Close the client to release sockets."""
        await self.client.aclose()

    async def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Automatic retry logic for rate limits (429) or server errors (5xx).
        Implements exponential backoff.
        """
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                response = await self.client.get(url, params=params)

                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise MetaAPIError(
                            status_code=502,
                            detail="Meta API returned invalid JSON",
                        ) from exc

                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code in (401, 403):
                    raise MetaAPIError(
                        status_code=response.status_code,
                        detail="Invalid or expired PAGE_TOKEN",
                    )

                if 500 <= response.status_code < 600:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                    continue

                raise MetaAPIError(
                    status_code=response.status_code,
                    detail=response.text,
                )

            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt == max_retries - 1:
                    raise MetaAPIError(
                        status_code=408,
                        detail="Meta API request timed out",
                    ) from exc
                await asyncio.sleep(2 ** attempt)

            except httpx.RequestError as exc:
                last_error = exc
                if attempt == max_retries - 1:
                    raise MetaAPIError(
                        status_code=503,
                        detail=f"Meta API request failed: {exc}",
                    ) from exc
                await asyncio.sleep(2 ** attempt)

        if last_error:
            raise MetaAPIError(
                status_code=429,
                detail="Max retries exceeded for Meta API",
            ) from last_error

        raise MetaAPIError(
            status_code=429,
            detail="Max retries exceeded for Meta API",
        )

    async def fetch_page_info(self) -> Dict[str, str]:
        """Fetch Page name and ID."""
        data = await self._request_with_retry("/me", params={"fields": "name,id"})
        if "name" not in data or "id" not in data:
            raise MetaAPIError(
                status_code=500,
                detail="Invalid page info response from Meta",
            )
        return data

    async def fetch_all_reels(self, max_reels: int = MAX_SAMPLE_REELS) -> List[Dict]:
        """
        Fetch all Reels using pagination.

        Meta API limits per-page results, so we follow the 'next' cursor.
        """
        reels: List[Dict[str, Any]] = []
        url: Optional[str] = "/me/videos"
        params: Optional[Dict[str, Any]] = {
            "fields": "id,title,description,created_time,permalink_url,length",
            "limit": 100,  # Max allowed per page
        }

        while url and len(reels) < max_reels:
            data = await self._request_with_retry(url, params=params)
            items = data.get("data", [])

            if isinstance(items, list):
                reels.extend(items)

            next_url = data.get("paging", {}).get("next")
            if next_url:
                # httpx can handle absolute URLs directly
                url = next_url
                params = None
            else:
                url = None

        # Return only the latest N reels (assumed newest -> oldest order)
        return reels[:max_reels]

    async def fetch_video_insights(self, video_id: str) -> Dict[str, Any]:
        """Fetch specific insights metrics for a single video."""
        return await self._request_with_retry(
            f"/{video_id}/video_insights",
            params={"metric": "total_plays,plays_3s,likes,comments,shares,saves"},
        )