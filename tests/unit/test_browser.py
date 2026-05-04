from __future__ import annotations

import webbrowser

import pytest

from jobhunt.browser import Browser, _default_opener
from jobhunt.exceptions import BrowserOpenError


def test_open_calls_opener_once_with_url() -> None:
    calls: list[str] = []

    def fake_opener(url: str) -> bool:
        calls.append(url)
        return True

    Browser(opener=fake_opener).open("https://example.com")
    assert calls == ["https://example.com"]


def test_open_raises_when_opener_returns_false() -> None:
    def failing(url: str) -> bool:
        return False

    with pytest.raises(BrowserOpenError):
        Browser(opener=failing).open("https://example.com")


def test_empty_url_raises() -> None:
    with pytest.raises(BrowserOpenError):
        Browser(opener=lambda _u: True).open("")


def test_default_opener_prints_url_when_webbrowser_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Headless / container hosts have no usable browser. The default opener
    must fall back to printing the URL and reporting success — never raise."""
    monkeypatch.setattr(webbrowser, "open", lambda _url, *args, **kwargs: False)
    Browser().open("https://example.com/apply")
    captured = capsys.readouterr()
    assert "https://example.com/apply" in captured.out


def test_default_opener_prints_url_when_webbrowser_raises(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raising(_url: str, *args: object, **kwargs: object) -> bool:
        raise webbrowser.Error("no browser")

    monkeypatch.setattr(webbrowser, "open", raising)
    Browser().open("https://example.com/apply")
    captured = capsys.readouterr()
    assert "https://example.com/apply" in captured.out


def test_default_opener_prefers_real_browser_when_available(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(webbrowser, "open", lambda _url, *args, **kwargs: True)
    assert _default_opener("https://example.com") is True
    captured = capsys.readouterr()
    assert captured.out == ""
