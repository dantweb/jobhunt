from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, ClassVar

import httpx

from jobhunt.exceptions import MissingCredentialsError
from jobhunt.models import RawPosting
from jobhunt.sources._http import make_client
from jobhunt.sources.base import JobSource


class AdzunaSource(JobSource):
    name: ClassVar[str] = "adzuna"
    BASE_URL: ClassVar[str] = "https://api.adzuna.com/v1/api/jobs/de/search/1"

    def __init__(
        self,
        *,
        app_id: str,
        app_key: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        missing = [k for k, v in {"app_id": app_id, "app_key": app_key}.items() if not v]
        if missing:
            raise MissingCredentialsError(self.name, missing=missing)
        self._app_id = app_id
        self._app_key = app_key
        self._client = http_client or make_client()

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        response = self._client.get(
            self.BASE_URL,
            params={
                "app_id": self._app_id,
                "app_key": self._app_key,
                "what": "python",
                "results_per_page": 50,
            },
        )
        response.raise_for_status()
        payload = response.json()
        return [self._parse(item) for item in payload.get("results") or []]

    def _parse(self, item: dict[str, Any]) -> RawPosting:
        location = (item.get("location") or {}).get("display_name")
        company = (item.get("company") or {}).get("display_name") or "Unknown"
        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        return RawPosting(
            external_id=str(item["id"]),
            title=str(item.get("title") or "Untitled"),
            company=str(company),
            url=str(item.get("redirect_url") or item.get("url") or ""),
            source=self.name,
            description=item.get("description"),
            location=location,
            salary_min_eur=int(salary_min) if salary_min else None,
            salary_max_eur=int(salary_max) if salary_max else None,
            posted_at=_parse_iso(item.get("created")),
        )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
