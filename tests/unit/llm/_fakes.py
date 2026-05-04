"""Fake SDK clients for unit-testing the two LLM providers.

Each fake duck-types just enough of the real SDK to let the provider
exercise its happy path without any HTTP. Tests configure the canned
response text per call.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeAnthropicMessages:
    def __init__(self, parent: FakeAnthropicClient) -> None:
        self._parent = parent

    def create(self, **kwargs: Any) -> Any:
        self._parent.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._parent.response_text)]
        )


class FakeAnthropicClient:
    def __init__(self, response_text: str = "") -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []
        self.messages = FakeAnthropicMessages(self)


class FakeOpenAICompletions:
    def __init__(self, parent: FakeOpenAIClient) -> None:
        self._parent = parent

    def create(self, **kwargs: Any) -> Any:
        self._parent.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._parent.response_text))]
        )


class FakeOpenAIChat:
    def __init__(self, parent: FakeOpenAIClient) -> None:
        self.completions = FakeOpenAICompletions(parent)


class FakeOpenAIClient:
    def __init__(self, response_text: str = "") -> None:
        self.response_text = response_text
        self.calls: list[dict[str, Any]] = []
        self.chat = FakeOpenAIChat(self)
