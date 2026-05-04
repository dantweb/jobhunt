from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any, ClassVar

import httpx

from jobhunt.models import RawPosting
from jobhunt.sources._http import make_client
from jobhunt.sources.base import JobSource


class BundesagenturSource(JobSource):
    name: ClassVar[str] = "bundesagentur"
    BASE_URL: ClassVar[str] = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
    PAGE_SIZE: ClassVar[int] = 50
    MAX_PAGES: ClassVar[int] = 4
    KEYWORDS: ClassVar[str] = "python php symfony"

    def __init__(self, *, http_client: httpx.Client | None = None) -> None:
        self._client = http_client or make_client(
            headers={"X-API-Key": "jobboerse-jobsuche"},
        )

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        return list(self._iter_pages(since))

    def _iter_pages(self, since: datetime | None) -> Iterator[RawPosting]:
        for page in range(1, self.MAX_PAGES + 1):
            response = self._client.get(
                self.BASE_URL,
                params={
                    "page": page,
                    "size": self.PAGE_SIZE,
                    "was": self.KEYWORDS,
                },
            )
            response.raise_for_status()
            data = response.json()
            items = data.get("stellenangebote") or []
            if not items:
                return
            for item in items:
                yield self._parse(item)
            if len(items) < self.PAGE_SIZE:
                return

    def _parse(self, item: dict[str, Any]) -> RawPosting:
        location = (item.get("arbeitsort") or {}).get("ort") if "arbeitsort" in item else None
        posted_at = _parse_date(item.get("aktuelleVeroeffentlichungsdatum"))
        return RawPosting(
            external_id=str(item.get("refnr") or item.get("hashId") or item["id"]),
            title=str(item.get("titel") or item.get("beruf") or "Unbenannt"),
            company=str(item.get("arbeitgeber") or "Unbekannt"),
            url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{item.get('refnr', '')}",
            source=self.name,
            description=item.get("stellenbeschreibung"),
            location=location,
            posted_at=posted_at,
            language="de",
        )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
