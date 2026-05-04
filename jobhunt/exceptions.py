"""Exceptions raised by the jobhunt package."""

from __future__ import annotations


class JobhuntError(Exception):
    """Base for all jobhunt-specific exceptions."""


class JobNotFoundError(JobhuntError):
    pass


class MissingCredentialsError(JobhuntError):
    """A source or provider was instantiated without its required credentials."""

    def __init__(self, name: str, missing: list[str]) -> None:
        self.name = name
        self.missing = list(missing)
        super().__init__(f"{name} is missing credentials: {', '.join(self.missing)}")


class MissingCvError(JobhuntError):
    pass


class CvReadError(JobhuntError):
    pass


class LLMResponseError(JobhuntError):
    """Raised when an LLM response cannot be parsed into the expected shape."""


class SmtpSendError(JobhuntError):
    pass


class BrowserOpenError(JobhuntError):
    pass


class InvalidStateTransitionError(JobhuntError):
    pass
