"""Pexels API integration for portrait stock photography (Doc 3 §9.2)."""

from typing import Any, Dict, List, Optional
from app.config import get_settings
from app.core.http_client import LoggedHttpClient


class PexelsClient:
    def __init__(self, http_client: Optional[LoggedHttpClient] = None):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient(timeout=30.0)

    async def search_photos(
        self,
        query: str,
        job_id: str = "_system",
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search portrait photos on Pexels."""
        if not self.settings.is_secret_set(self.settings.PEXELS_API_KEY):
            return []

        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": self.settings.PEXELS_API_KEY.get_secret_value()}
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "large",
            "per_page": per_page,
            "page": 1,
        }

        try:
            resp = await self.http_client.request(
                method="GET",
                url=url,
                kind="stock_search",
                provider="pexels",
                label=f"search_{query[:20]}",
                job_id=job_id,
                headers=headers,
                params=params,
            )
            if resp.status_code == 200:
                data = resp.json()
                photos = data.get("photos", [])
                results = []
                for p in photos:
                    src = p.get("src", {})
                    download_url = src.get("original") or src.get("large2x") or src.get("large")
                    if download_url:
                        results.append(
                            {
                                "provider": "pexels",
                                "id": str(p.get("id")),
                                "url": download_url,
                                "page_url": p.get("url", ""),
                                "photographer": p.get("photographer", "Pexels Creator"),
                                "width": p.get("width", 1080),
                                "height": p.get("height", 1920),
                                "alt": p.get("alt", query),
                            }
                        )
                return results
            return []
        except Exception:
            return []

    async def search_videos(
        self,
        query: str,
        job_id: str = "_system",
        per_page: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search portrait video clips on Pexels."""
        if not self.settings.is_secret_set(self.settings.PEXELS_API_KEY):
            return []

        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.settings.PEXELS_API_KEY.get_secret_value()}
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "medium",
            "per_page": per_page,
            "page": 1,
        }

        try:
            resp = await self.http_client.request(
                method="GET",
                url=url,
                kind="stock_search",
                provider="pexels",
                label=f"video_search_{query[:20]}",
                job_id=job_id,
                headers=headers,
                params=params,
            )
            if resp.status_code == 200:
                data = resp.json()
                videos = data.get("videos", [])
                results = []
                for v in videos:
                    files = v.get("video_files", [])
                    # Pick best vertical HD/SD mp4 link
                    portrait_files = [
                        f for f in files
                        if f.get("height", 0) > f.get("width", 0) and f.get("file_type") == "video/mp4"
                    ]
                    chosen_file = (
                        portrait_files[0] if portrait_files
                        else (files[0] if files else None)
                    )
                    pictures = v.get("video_pictures", [])
                    thumb_url = pictures[0].get("picture") if pictures else ""

                    if chosen_file and chosen_file.get("link"):
                        results.append(
                            {
                                "provider": "pexels_video",
                                "id": str(v.get("id")),
                                "url": chosen_file.get("link"),
                                "thumb_url": thumb_url,
                                "duration": v.get("duration", 5),
                                "width": chosen_file.get("width", 1080),
                                "height": chosen_file.get("height", 1920),
                                "alt": query,
                            }
                        )
                return results
            return []
        except Exception:
            return []
