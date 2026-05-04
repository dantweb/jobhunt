from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, ClassVar

import httpx

from jobhunt.exceptions import MissingCredentialsError
from jobhunt.models import RawPosting
from jobhunt.sources._http import make_client
from jobhunt.sources.base import JobSource


class JoobleSource(JobSource):
    name: ClassVar[str] = "jooble"
    BASE_URL: ClassVar[str] = "https://jooble.org/api"

    def __init__(self, *, api_key: str, http_client: httpx.Client | None = None) -> None:
        if not api_key:
            raise MissingCredentialsError(self.name, missing=["api_key"])
        self._api_key = api_key
        self._client = http_client or make_client()

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        response = self._client.post(
            f"{self.BASE_URL}/{self._api_key}",
            json={"keywords": "python", "location": "Germany"},
        )
        response.raise_for_status()
        payload = response.json()
        return [self._parse(item) for item in payload.get("jobs") or []]

    def _parse(self, item: dict[str, Any]) -> RawPosting:
        return RawPosting(
            external_id=str(item.get("id") or item.get("link")),
            title=str(item.get("title") or "Untitled"),
            company=str(item.get("company") or "Unknown"),
            url=str(item.get("link") or ""),
            source=self.name,
            description=item.get("snippet"),
            location=item.get("location"),
            posted_at=_parse_jooble_date(item.get("updated")),
        )


def _parse_jooble_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
