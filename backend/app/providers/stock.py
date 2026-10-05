"""Unified stock search, ranking, and downloading across Pexels videos/photos and Pixabay."""

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple
from app.config import get_settings
from app.core.http_client import LoggedHttpClient
from app.media.imaging import ImageEvaluationResult, evaluate_and_process_image
from app.providers.pexels import PexelsClient
from app.providers.pixabay import PixabayClient


ABSTRACT_BLACKLIST = {
    "reality", "staggering", "mind", "mystery", "scale", "impossible",
    "concept", "theory", "collision", "journey", "feeling", "sense",
    "truth", "secret", "secrets", "deeply", "unbelievable"
}

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "of", "and", "or", "for",
    "with", "to", "by", "from", "is", "are", "it", "its", "that", "this"
}


def sanitize_stock_query(query: str) -> str:
    """Strip abstract adjectives and filler words to leave purely physical search terms."""
    tokens = re.findall(r"\w+", query.lower())
    clean_tokens = [t for t in tokens if t not in STOP_WORDS and t not in ABSTRACT_BLACKLIST]
    return " ".join(clean_tokens) if clean_tokens else query


def is_candidate_relevant(query: str, cand: Dict[str, Any]) -> bool:
    """Check lexical overlap between concrete query words and candidate metadata."""
    query_tokens = set(re.findall(r"\w+", query.lower())) - STOP_WORDS - ABSTRACT_BLACKLIST
    if not query_tokens:
        return True

    cand_text = f"{cand.get('alt', '')} {cand.get('tags', '')}".lower()
    cand_tokens = set(re.findall(r"\w+", cand_text))

    # Reject unrelated human portraits/selfies if query is not about people
    person_words = {"portrait", "model", "woman", "man", "girl", "boy", "person", "selfie", "fashion"}
    if person_words.intersection(cand_tokens) and not any(w in query.lower() for w in ("person", "human", "diver", "scientist", "people")):
        return False

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
        """Search stock providers across ordered queries: Pexels Video -> Pexels Photo -> Pixabay Photo."""
        # Sanitize queries to ensure physical keyword focus
        sanitized_queries = [sanitize_stock_query(q) for q in queries]

        for query in sanitized_queries:
            # 1. First Priority: Pexels Portrait Video thumbnails/frames
            try:
                videos = await self.pexels.search_videos(query, job_id=job_id, per_page=3)
                for vid in videos:
                    vid_key = f"pexels_video_{vid['id']}"
                    if vid_key in seen_stock_ids:
                        continue
                    thumb_url = vid.get("thumb_url")
                    if thumb_url:
                        resp = await self.http_client.request(
                            method="GET",
                            url=thumb_url,
                            kind="stock_download",
                            provider="pexels",
                            label=f"{beat_key}_v_{vid['id']}",
                            job_id=job_id,
                        )
                        if resp.status_code == 200 and len(resp.content) > 5000:
                            eval_res = evaluate_and_process_image(
                                raw_bytes=resp.content,
                                source="pexels_video",
                                existing_phashes=existing_phashes,
                            )
                            if eval_res.accepted and eval_res.image is not None:
                                seen_stock_ids.add(vid_key)
                                return resp.content, vid, eval_res
            except Exception:
                pass

            # 2. Second Priority: Pexels Portrait Photos
            candidates: List[Dict[str, Any]] = []
            try:
                photos = await self.pexels.search_photos(query, job_id=job_id, per_page=6)
                candidates.extend(photos)
            except Exception:
                pass

            # 3. Third Priority: Pixabay Photos
            try:
                if len(candidates) < 4:
                    pix_photos = await self.pixabay.search_photos(query, job_id=job_id, per_page=6)
                    candidates.extend(pix_photos)
            except Exception:
                pass

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
