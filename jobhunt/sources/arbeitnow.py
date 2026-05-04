from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx

from jobhunt.models import RawPosting
from jobhunt.sources._http import make_client
from jobhunt.sources.base import JobSource


class ArbeitnowSource(JobSource):
    name: ClassVar[str] = "arbeitnow"
    BASE_URL: ClassVar[str] = "https://www.arbeitnow.com/api/job-board-api"
    MAX_PAGES: ClassVar[int] = 4

    def __init__(self, *, http_client: httpx.Client | None = None) -> None:
        self._client = http_client or make_client()

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        return list(self._iter_pages())

    def _iter_pages(self) -> Iterator[RawPosting]:
        for page in range(1, self.MAX_PAGES + 1):
            response = self._client.get(self.BASE_URL, params={"page": page})
            response.raise_for_status()
            payload = response.json()
            items = payload.get("data") or []
            if not items:
                return
            for item in items:
                yield self._parse(item)
            next_page = (payload.get("links") or {}).get("next")
            if not next_page:
                return

    def _parse(self, item: dict[str, Any]) -> RawPosting:
        timestamp = item.get("created_at")
        posted_at = datetime.fromtimestamp(int(timestamp), tz=UTC) if timestamp else None
        tags = [str(t).lower() for t in (item.get("tags") or [])]
        language = "en" if "english" in tags else None
        return RawPosting(
            external_id=str(item.get("slug") or item["id"]),
            title=str(item["title"]),
            company=str(item["company_name"]),
            url=str(item.get("url") or f"https://www.arbeitnow.com/jobs/{item.get('slug')}"),
            source=self.name,
            description=item.get("description"),
            location=item.get("location"),
            language=language,
            posted_at=posted_at,
        )
