"""Open apply URLs.

Default behaviour falls back to **printing** the URL when no browser is
available (headless host, Docker container, SSH session, …) so the
caller can copy/click it manually instead of failing the apply step.
Tests inject their own opener to keep the strict contract.
"""

from __future__ import annotations

import sys
import webbrowser
from collections.abc import Callable

from jobhunt.exceptions import BrowserOpenError


def _default_opener(url: str) -> bool:
    try:
        if webbrowser.open(url):
            return True
    except webbrowser.Error:
        pass
    # Headless: print prominently so the user can click in the terminal.
    print(f"\n→ Open this URL to apply: {url}\n", file=sys.stdout, flush=True)
    return True


class Browser:
    def __init__(self, opener: Callable[[str], bool] | None = None) -> None:
        self._opener = opener or _default_opener

    def open(self, url: str) -> None:
        if not url:
            raise BrowserOpenError("empty url")
        if not self._opener(url):
            raise BrowserOpenError(f"opener returned False for {url}")
