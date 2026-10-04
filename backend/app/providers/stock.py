"""Unified stock search, ranking, and downloading across Pexels and Pixabay."""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from app.config import get_settings
from app.core.http_client import LoggedHttpClient
from app.media.imaging import ImageEvaluationResult, evaluate_and_process_image
from app.providers.pexels import PexelsClient
from app.providers.pixabay import PixabayClient


import re

def is_candidate_relevant(query: str, cand: Dict[str, Any]) -> bool:
    """Check lexical overlap between query words and candidate alt/tags per Doc 3 §12.3."""
    stop_words = {"a", "an", "the", "in", "on", "at", "of", "and", "or", "for", "with", "to", "by", "from", "is", "are"}
    query_tokens = set(re.findall(r"\w+", query.lower())) - stop_words
    if not query_tokens:
        return True

    cand_text = f"{cand.get('alt', '')} {cand.get('tags', '')}".lower()
    cand_tokens = set(re.findall(r"\w+", cand_text))
    # True if at least one meaningful token overlaps or is a substring
    for qt in query_tokens:
        if len(qt) >= 3 and any(qt in ct or ct in qt for ct in cand_tokens):
            return True
    return False


class UnifiedStockService:
    def __init__(self, http_client: Optional[LoggedHttpClient] = None):
        self.settings = get_settings()
        self.http_client = http_client or LoggedHttpClient()
        self.pexels = PexelsClient(self.http_client)
        self.pixabay = PixabayClient(self.http_client)

    async def search_and_download_candidate(
        self,
        queries: List[str],
        job_id: str,
        beat_key: str,
        existing_phashes: List[str],
        seen_stock_ids: set[str],
    ) -> Optional[Tuple[bytes, Dict[str, Any], ImageEvaluationResult]]:
        """Search stock providers across ordered queries and download the best accepted candidate."""
        providers = self.settings.stock_providers

        for query in queries:
            candidates: List[Dict[str, Any]] = []

            for provider in providers:
                if provider == "pexels":
                    photos = await self.pexels.search_photos(query, job_id=job_id)
                    candidates.extend(photos)
                elif provider == "pixabay":
                    photos = await self.pixabay.search_photos(query, job_id=job_id)
                    candidates.extend(photos)

                if len(candidates) >= 5:
                    break

            # Filter out already used IDs and verify query relevance
            fresh_candidates = [
                c for c in candidates
                if f"{c['provider']}_{c['id']}" not in seen_stock_ids and is_candidate_relevant(query, c)
            ]

            for cand in fresh_candidates:
                download_url = cand["url"]
                provider_name = cand["provider"]

                try:
                    resp = await self.http_client.request(
                        method="GET",
                        url=download_url,
                        kind="stock_download",
                        provider=provider_name,
                        label=f"{beat_key}_{cand['id']}",
                        job_id=job_id,
                    )

                    if resp.status_code == 200 and len(resp.content) > 5000:
                        eval_res = evaluate_and_process_image(
                            raw_bytes=resp.content,
                            source=provider_name,
                            existing_phashes=existing_phashes,
                        )

                        if eval_res.accepted and eval_res.image is not None:
                            seen_stock_ids.add(f"{provider_name}_{cand['id']}")
                            return resp.content, cand, eval_res

                except Exception:
                    continue

        return None
