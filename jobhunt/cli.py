"""Typer CLI. Thin glue — every command delegates to a service."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console

from jobhunt.config import AppConfig, load_toml, write_toml
from jobhunt.cv import CvReader, ProfileSeeder
from jobhunt.diagnostics import Status, env_status
from jobhunt.exceptions import SmtpSendError
from jobhunt.llm import AnthropicProvider, LLMProvider, OpenAIProvider
from jobhunt.models import Application, Decision, Filters, ProfileDraft
from jobhunt.sender import Sender
from jobhunt.wiring import Container, build_container

app = typer.Typer(no_args_is_help=False, add_completion=False)
console = Console()


@app.command()
def init(reseed: bool = typer.Option(False, "--reseed", help="Re-seed only [filters].")) -> None:
    """One-time setup. Reads CV, seeds [filters], writes config.toml + .env."""
    app_config = AppConfig()
    cv_path = Path(_prompt("CV path", default=app_config.CV_PATH))
    llm = _build_llm_with_user_choice(app_config)
    seeder = ProfileSeeder(llm=llm, reader=CvReader())
    console.print("[bold]Reading CV…[/bold]")
    draft = seeder.seed(cv_path)
    console.print("[bold]Seeded profile:[/bold]")
    final = _confirm_filters(draft)

    config_path = app_config.config_toml_path()
    default_sources = [
        "bundesagentur",
        "arbeitnow",
        "adzuna",
        "jooble",
        "remotive",
        "weworkremotely",
    ]
    if reseed and config_path.exists():
        existing = load_toml(config_path)
        write_toml(config_path, filters=final, sources_enabled=existing.sources_enabled)
        console.print(f"[green]✅ filters re-seeded → {config_path}[/green]")
        return
    write_toml(config_path, filters=final, sources_enabled=default_sources)
    console.print(f"[green]✅ wrote {config_path}[/green]")
    _print_env_status(app_config)


@app.command()
def fetch() -> None:
    container = _container()
    report = container.fetch_service.run()
    console.print(
        f"[green]fetched={sum(report.fetched_per_source.values())} "
        f"saved={report.saved} scored={report.scored} "
        f"shortlisted={report.shortlisted}[/green]"
    )
    if report.failures:
        console.print(f"[yellow]source failures: {report.failures}[/yellow]")


@app.command()
def review() -> None:
    container = _container()
    for item in container.review_service.next():
        console.print(
            f"\n[bold]{item.job.title}[/bold] @ {item.job.company} "
            f"({item.job.location or '?'})  score={item.job.score}"
        )
        console.print(f"{item.job.url}")
        choice = typer.prompt("a)pprove r)eject s)kip v)iew l)etter q)uit", default="s")
        if choice == "q":
            break
        if choice == "a":
            container.review_service.record(job_id=item.job.id, decision=Decision.APPROVED)
        elif choice == "r":
            container.review_service.record(job_id=item.job.id, decision=Decision.REJECTED)
        elif choice == "v":
            console.print(item.job.description or "(no description)")
        elif choice == "l":
            console.print("[dim]letter generated only on approval to save tokens.[/dim]")


@app.command()
def send() -> None:
    container = _container()
    report = container.apply_service.run()
    console.print(
        f"[green]sent={report.sent_email} browser={report.opened_browser} "
        f"skipped_daily_cap={report.skipped_daily_cap}[/green]"
    )
    if report.failures:
        console.print(f"[red]failures: {report.failures}[/red]")


@app.command(name="send-test")
def send_test(
    to: str = typer.Option(
        "test@local.example",
        "--to",
        help="Recipient. Anything works for mailpit; matters only for real SMTP.",
    ),
) -> None:
    """Send a synthetic email through the configured SMTP server.

    Useful to verify mailpit / SMTP wiring end-to-end without waiting for
    a posting that happens to expose a contact email.
    """
    app_config = AppConfig()
    sender = Sender(config=app_config.smtp(), owner_name=app_config.OWNER_NAME or "jobhunt")
    body = (
        f"This is a synthetic test email from `jobhunt send-test` at "
        f"{datetime.now(tz=UTC).isoformat()}.\n\n"
        f"If you can read this in mailpit (or your inbox), SMTP wiring is correct."
    )
    application = Application(job_id="send-test", decision=Decision.APPROVED, cover_letter=body)
    cv_path = app_config.cv_path()
    if not cv_path.exists():
        console.print(
            f"[red]CV not found at {cv_path} — `send-test` attaches your CV like a real send.[/red]"
        )
        raise typer.Exit(code=1)
    try:
        sender.send(
            application,
            to_address=to,
            subject="jobhunt SMTP test",
            cv_path=cv_path,
        )
    except SmtpSendError as exc:
        console.print(
            f"[red]SMTP send failed against {app_config.SMTP_HOST}:{app_config.SMTP_PORT} — "
            f"{exc}[/red]"
        )
        if "refused" in str(exc).lower() and app_config.SMTP_HOST == "mailpit":
            console.print(
                "[yellow]Mailpit looks unreachable. Start it with:\n"
                "  docker compose up -d mailpit\n"
                "then re-run this command.[/yellow]"
            )
        raise typer.Exit(code=1) from exc
    target = (
        "mailpit (open http://localhost:8125)"
        if app_config.SMTP_HOST == "mailpit"
        else f"{app_config.SMTP_HOST}:{app_config.SMTP_PORT}"
    )
    console.print(f"[green]✅ test email sent to {to} via {target}[/green]")


@app.command()
def status() -> None:
    container = _container()
    pending = len(container.applications_repo.pending())
    approved = len(container.applications_repo.approved())
    all_apps = container.applications_repo.all()
    sent = sum(1 for a in all_apps if a.sent_at is not None)
    console.print(f"pending={pending} approved={approved} sent={sent}")


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    """Bare `jobhunt` runs fetch → review → send."""
    if ctx.invoked_subcommand is not None:
        return
    fetch()
    review()
    send()


def _container() -> Container:
    app_config = AppConfig()
    toml = load_toml(app_config.config_toml_path())
    cv_text = CvReader().read(app_config.cv_path())
    return build_container(app=app_config, toml=toml, cv_text=cv_text)


def _build_llm_with_user_choice(cfg: AppConfig) -> LLMProvider:
    if cfg.LLM_PROVIDER == "anthropic":
        return AnthropicProvider(
            api_key=cfg.ANTHROPIC_API_KEY,
            model_rank=cfg.ANTHROPIC_MODEL_RANK,
            model_tailor=cfg.ANTHROPIC_MODEL_TAILOR,
            model_profile=cfg.ANTHROPIC_MODEL_PROFILE,
        )
    return OpenAIProvider(
        api_key=cfg.OPENAI_API_KEY,
        model_rank=cfg.OPENAI_MODEL_RANK,
        model_tailor=cfg.OPENAI_MODEL_TAILOR,
        model_profile=cfg.OPENAI_MODEL_PROFILE,
    )


def _prompt(text: str, *, default: str = "") -> str:
    return str(typer.prompt(text, default=default))


_STATUS_GLYPH = {
    Status.OK: "[green]✓[/green]",
    Status.WARN: "[yellow]![/yellow]",
    Status.ERROR: "[red]✗[/red]",
}


def _print_env_status(cfg: AppConfig) -> None:
    console.print()
    console.print("[bold]Environment status:[/bold]")
    has_error = False
    has_warn = False
    for entry in env_status(cfg):
        glyph = _STATUS_GLYPH[entry.status]
        console.print(f"  {glyph} [bold]{entry.label}[/bold] — {entry.detail}")
        if entry.status == Status.ERROR:
            has_error = True
        elif entry.status == Status.WARN:
            has_warn = True
    console.print()
    if has_error:
        console.print("[red]Fix the ✗ items in `.env` before running `jobhunt fetch`.[/red]")
    elif has_warn:
        console.print(
            "[yellow]The ! items are optional — `jobhunt fetch` will work without them.[/yellow]"
        )
    else:
        console.print("[green]All set — run `jobhunt fetch` to start.[/green]")


def _confirm_filters(draft: ProfileDraft) -> Filters:
    console.print(f"  min_salary_eur     = {draft.min_salary_eur}")
    console.print(f"  allowed_locations  = {draft.allowed_locations}")
    console.print(f"  language_preference= {draft.language_preference}")
    console.print(f"  language_fallback  = {draft.language_fallback}")
    console.print(f"  seniority          = {draft.seniority}")
    console.print(f"  stack_must_haves   = {draft.stack_must_haves}")
    if not typer.confirm("Accept these defaults?", default=True):
        console.print("[yellow]Edit config.toml manually after init completes.[/yellow]")
    return draft.to_filters()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
