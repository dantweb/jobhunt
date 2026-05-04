"""Single point of construction. Plain Python — no DI container."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from jobhunt.browser import Browser
from jobhunt.config import AppConfig, TomlConfig
from jobhunt.cv import CvReader, ProfileSeeder
from jobhunt.db import connect
from jobhunt.exceptions import MissingCredentialsError
from jobhunt.llm import AnthropicProvider, LLMProvider, OpenAIProvider
from jobhunt.ranker import Ranker
from jobhunt.repositories import ApplicationRepository, JobRepository
from jobhunt.sender import Sender
from jobhunt.services import ApplyService, FetchService, ReviewService
from jobhunt.sources import REGISTRY
from jobhunt.sources.base import JobSource
from jobhunt.tailor import Tailor

logger = logging.getLogger(__name__)


@dataclass
class Container:
    fetch_service: FetchService
    review_service: ReviewService
    apply_service: ApplyService
    jobs_repo: JobRepository
    applications_repo: ApplicationRepository
    cv_reader: CvReader
    profile_seeder: ProfileSeeder
    llm: LLMProvider


def build_container(*, app: AppConfig, toml: TomlConfig, cv_text: str) -> Container:
    conn = connect(app.db_path())
    jobs_repo = JobRepository(conn)
    applications_repo = ApplicationRepository(conn)

    llm = _build_llm(app)
    cv_reader = CvReader()
    profile_seeder = ProfileSeeder(llm=llm, reader=cv_reader)

    sources = _build_sources(toml.sources_enabled, app)
    ranker = Ranker(llm=llm, filters=toml.filters, cv=cv_text)
    tailor = Tailor(llm=llm, cv=cv_text, owner_preference=toml.filters.language_preference)
    sender = Sender(config=app.smtp(), owner_name=app.OWNER_NAME or "")
    browser = Browser()

    fetch_service = FetchService(
        sources=sources,
        jobs=jobs_repo,
        ranker=ranker,
        shortlist_size=toml.filters.shortlist_size,
    )
    review_service = ReviewService(jobs=jobs_repo, applications=applications_repo, tailor=tailor)
    apply_service = ApplyService(
        applications=applications_repo,
        jobs=jobs_repo,
        sender=sender,
        browser=browser,
        cv_path=app.cv_path(),
    )

    return Container(
        fetch_service=fetch_service,
        review_service=review_service,
        apply_service=apply_service,
        jobs_repo=jobs_repo,
        applications_repo=applications_repo,
        cv_reader=cv_reader,
        profile_seeder=profile_seeder,
        llm=llm,
    )


def _build_llm(app: AppConfig) -> LLMProvider:
    if app.LLM_PROVIDER == "anthropic":
        return AnthropicProvider(
            api_key=app.ANTHROPIC_API_KEY,
            model_rank=app.ANTHROPIC_MODEL_RANK,
            model_tailor=app.ANTHROPIC_MODEL_TAILOR,
            model_profile=app.ANTHROPIC_MODEL_PROFILE,
        )
    return OpenAIProvider(
        api_key=app.OPENAI_API_KEY,
        model_rank=app.OPENAI_MODEL_RANK,
        model_tailor=app.OPENAI_MODEL_TAILOR,
        model_profile=app.OPENAI_MODEL_PROFILE,
    )


def _build_sources(enabled: list[str], app: AppConfig) -> list[JobSource]:
    sources: list[JobSource] = []
    for name in enabled:
        cls = REGISTRY.get(name)
        if cls is None:
            logger.warning("unknown source name skipped: %s", name)
            continue
        try:
            if name == "adzuna":
                sources.append(REGISTRY[name](app_id=app.ADZUNA_APP_ID, app_key=app.ADZUNA_APP_KEY))  # type: ignore[call-arg]
            elif name == "jooble":
                sources.append(REGISTRY[name](api_key=app.JOOBLE_API_KEY))  # type: ignore[call-arg]
            else:
                sources.append(REGISTRY[name]())
        except MissingCredentialsError as exc:
            logger.warning("source %s skipped: %s", name, exc)
    return sources
