from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, ClassVar

import httpx

from jobhunt.models import RawPosting
from jobhunt.sources._http import make_client
from jobhunt.sources.base import JobSource

_EU_REGIONS = (
    "europe",
    "eu",
    "emea",
    "germany",
    "berlin",
    "uk",
    "remote",
    "worldwide",
)


class RemotiveSource(JobSource):
    name: ClassVar[str] = "remotive"
    BASE_URL: ClassVar[str] = "https://remotive.com/api/remote-jobs"

    def __init__(self, *, http_client: httpx.Client | None = None) -> None:
        self._client = http_client or make_client()

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        response = self._client.get(
            self.BASE_URL,
            params={"category": "software-dev", "search": "python"},
        )
        response.raise_for_status()
        payload = response.json()
        return [
            self._parse(item)
            for item in payload.get("jobs") or []
            if _is_eu_or_remote(item.get("candidate_required_location") or "")
        ]

    def _parse(self, item: dict[str, Any]) -> RawPosting:
        return RawPosting(
            external_id=str(item["id"]),
            title=str(item.get("title") or "Untitled"),
            company=str(item.get("company_name") or "Unknown"),
            url=str(item.get("url") or ""),
            source=self.name,
            description=item.get("description"),
            location=item.get("candidate_required_location"),
            language="en",
            posted_at=_parse_iso(item.get("publication_date")),
        )


def _is_eu_or_remote(location: str) -> bool:
    lc = location.lower()
    return any(token in lc for token in _EU_REGIONS)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
