# jobhunt

Personal interactive CLI that fetches German + EU-remote backend job
postings, ranks them against the owner's CV via a pluggable LLM
(Anthropic Claude or OpenAI), tailors a cover letter for approved
entries, and either sends an SMTP application or opens the apply URL.

Planning lives at `docs/dev_log/20260429/`. Status is tracked in
`status.md`.

---

## Quickstart

The host needs **only Docker**. There is no `uv`, `pip`, or `python`
step on the host — the container is the only runtime.

```bash
# 1. Build the dev image and run the test gate to confirm a clean install.
docker compose build
./bin/pre-commit-check.sh

# 2. Start the local Mailpit SMTP sink (web UI at http://localhost:8125).
docker compose up -d mailpit

# 3. Configure your environment.
cp .env.example .env
# edit .env — fill in API keys and paths (see "Getting API keys" below).

# 4. Place your CV PDF where the container will see it.
mkdir -p var/cv
cp /path/to/your/cv.pdf var/cv/cv.pdf

# 5. Run the one-time setup (CV → seeded filters → config.toml).
docker compose run --rm jobhunt uv run jobhunt init

# 6. Daily usage.
docker compose run --rm jobhunt uv run jobhunt fetch
docker compose run --rm jobhunt uv run jobhunt review
docker compose run --rm jobhunt uv run jobhunt send
docker compose run --rm jobhunt uv run jobhunt status
```

`bin/pre-commit-check.sh` is the single source of truth for the
lint/type/test gate. The CI workflow at `.github/workflows/ci.yml`
invokes the same script.

---

## Email testing with Mailpit (no real emails leave your machine)

The compose stack ships a [Mailpit](https://github.com/axllent/mailpit)
service — a tiny SMTP server that captures every outgoing message and
displays it in a web UI. The default `.env.example` already points
`SMTP_HOST=mailpit` so the very first `jobhunt send` you run is captured
by Mailpit, not delivered to the internet.

```bash
docker compose up -d mailpit
open http://localhost:8125      # macOS — or paste the URL into a browser
```

Every email your run produces appears in the inbox at the URL above with
its full headers, body, and PDF attachment. Nothing reaches an external
SMTP server while `SMTP_HOST=mailpit` is set in `.env`.

To switch off Mailpit, override the SMTP block in `.env`. Three documented
options (full snippets are in `.env.example`):

- **Mailpit container** (default) — captures locally, web UI at
  http://localhost:8125.
- **SMTP daemon running on your host** (postfix, sendmail, …) — set
  `SMTP_HOST=host.docker.internal` and the port your daemon uses. The
  compose file already maps `host.docker.internal` for Linux too via
  `extra_hosts: host-gateway`, so this works on Mac, Windows, and Linux.
- **Real production SMTP** (e.g. Gmail) — `SMTP_HOST=smtp.gmail.com`,
  `SMTP_PORT=587`, `SMTP_USE_STARTTLS=true`, app password in
  `SMTP_PASSWORD`.

---

## Getting API keys

You only need the LLM key for the provider you pick (`LLM_PROVIDER`).
Adzuna and Jooble are optional — sources without keys are skipped at
runtime with a warning.

### 1. Anthropic Claude (default LLM)

1. Go to https://console.anthropic.com/ and sign up (free tier works for
   small tests; pay-as-you-go after that).
2. Top-left dropdown → **Workspace** → **API Keys** → **Create Key**.
3. Name it `jobhunt-local`, copy the value once (you cannot see it
   again).
4. Paste into `.env`:
   ```
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   ```
5. Add billing under **Settings → Billing** before doing more than a
   couple of calls — free credits run out fast.

### 2. OpenAI (alternative LLM)

1. Go to https://platform.openai.com/ and sign in.
2. Top-right avatar → **View API keys** → **Create new secret key**.
3. Name it `jobhunt-local`, copy the value (you only see it once).
4. Paste into `.env`:
   ```
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   ```
5. Pre-load credit at **Settings → Billing** (no free tier without one).

### 3. Adzuna (optional — DE job aggregator)

1. Go to https://developer.adzuna.com/ and **Sign up** (free).
2. Verify your email; log in to the developer portal.
3. The dashboard shows your **App ID** and **App Key** under
   **Applications**. (If empty, click **Create application** → name it
   `jobhunt`.)
4. Paste into `.env`:
   ```
   ADZUNA_APP_ID=<numeric id>
   ADZUNA_APP_KEY=<32-char hex>
   ```
   Free tier is 250 calls/month — plenty for a daily run.

### 4. Jooble (optional — DE job aggregator)

1. Go to https://uk.jooble.org/api/about (the country sub-domain doesn't
   matter; the API is global).
2. Click **Get API Key** and fill in the form (use case: "personal job
   search aggregator").
3. The key is emailed to you within a few minutes.
4. Paste into `.env`:
   ```
   JOOBLE_API_KEY=<uuid-style key>
   ```

### 5. Bundesagentur, Arbeitnow, Remotive, WeWorkRemotely

**No keys needed.** These four sources are public and unauthenticated.
They run by default with no extra setup.

### 6. SMTP credentials (only for real production sending)

Skip this entirely if you stay on Mailpit (the default).

For Gmail (recommended for personal use):

1. Enable **2-Step Verification** at
   https://myaccount.google.com/security.
2. Go to https://myaccount.google.com/apppasswords and create an
   **App password** for "Mail" / "Other (jobhunt)". Copy the 16-char
   value.
3. Set in `.env`:
   ```
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_STARTTLS=true
   SMTP_USER=you@gmail.com
   SMTP_PASSWORD=<the 16-char app password>
   SMTP_FROM=you@gmail.com
   ```
