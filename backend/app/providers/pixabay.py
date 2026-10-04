"""Pixabay API integration for vertical stock photography (Doc 3 §9.3)."""

from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.core.http_client import LoggedHttpClient


class PixabayClient:
    def __init__(self, http_client: Optional[LoggedHttpClient] = None):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient(timeout=30.0)

    async def search_photos(
        self,
        query: str,
        job_id: str = "_system",
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search vertical photos on Pixabay."""
        if not self.settings.is_secret_set(self.settings.PIXABAY_API_KEY):
            return []

        url = "https://pixabay.com/api/"
        key = self.settings.PIXABAY_API_KEY.get_secret_value()
        params = {
            "key": key,
            "q": query,
            "image_type": "photo",
            "orientation": "vertical",
            "min_width": 720,
            "min_height": 1280,
            "safesearch": "true",
            "order": "popular",
            "per_page": per_page,
        }

        try:
            resp = await self.http_client.request(
                method="GET",
                url=url,
                kind="stock_search",
                provider="pixabay",
                label=f"search_{query[:20]}",
                job_id=job_id,
                params=params,
            )
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                results = []
                for h in hits:
                    download_url = h.get("largeImageURL") or h.get("webformatURL")
                    if download_url:
                        results.append(
                            {
                                "provider": "pixabay",
                                "id": str(h.get("id")),
                                "url": download_url,
                                "page_url": h.get("pageURL", ""),
                                "photographer": h.get("user", "Pixabay Creator"),
                                "width": h.get("imageWidth", 1080),
                                "height": h.get("imageHeight", 1920),
                                "tags": h.get("tags", query),
                            }
                        )
                return results
            return []
        except Exception:
            return []
