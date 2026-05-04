from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import ClassVar
from xml.etree import ElementTree as ET

import httpx

from jobhunt.models import RawPosting
from jobhunt.sources._http import make_client
from jobhunt.sources.base import JobSource


class WeWorkRemotelySource(JobSource):
    name: ClassVar[str] = "weworkremotely"
    FEED_URL: ClassVar[str] = (
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss"
    )

    def __init__(self, *, http_client: httpx.Client | None = None) -> None:
        self._client = http_client or make_client()

    def fetch(self, since: datetime | None = None) -> Iterable[RawPosting]:
        response = self._client.get(self.FEED_URL)
        response.raise_for_status()
        return list(self._parse_feed(response.text))

    def _parse_feed(self, body: str) -> Iterable[RawPosting]:
        root = ET.fromstring(body)
        for item in root.iter("item"):
            link = (item.findtext("link") or "").strip()
            title_raw = (item.findtext("title") or "").strip()
            company, title = _split_title(title_raw)
            description = (item.findtext("description") or "").strip() or None
            pub_date = _parse_rss_date(item.findtext("pubDate"))
            guid = (item.findtext("guid") or link).strip()
            yield RawPosting(
                external_id=guid or link,
                title=title or title_raw or "Untitled",
                company=company or "Unknown",
                url=link or "https://weworkremotely.com",
                source=self.name,
                description=description,
                language="en",
                posted_at=pub_date,
            )


def _split_title(title: str) -> tuple[str | None, str | None]:
    if ":" in title:
        company, role = title.split(":", 1)
        return company.strip() or None, role.strip() or None
    return None, title or None


def _parse_rss_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
