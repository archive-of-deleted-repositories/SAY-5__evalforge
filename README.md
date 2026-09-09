# EvalForge

Inline GenAI evaluation and moderation service. A Python FastAPI backend that scores model outputs on three axes (quality, safety, moderation), exposes a low-latency REST endpoint other services call before returning to users, persists every check to Postgres for review, and ships a React dashboard for reviewing flagged outputs across prompt versions.

## What it does

Other services call `POST /v1/evaluate` with a model output. EvalForge scores it on three axes and returns a verdict in under 200ms (p99, FakeProvider in CI). If any axis flags the output, the check lands in a review queue where humans triage it. Reviewer corrections feed back into the scorer.

The three axes:

| Axis | Detects | Method |
|---|---|---|
| Quality | task-correctness against a rubric | Deterministic FakeProvider by default; optional Claude Messages judge |
| Safety | pii, prompt_injection, harmful_advice, confidential_data | classifier against a fixed taxonomy |
| Moderation | profanity, toxicity, harassment | regex + wordlist baseline |

Each axis returns `{score: 0..1, label, flagged, reasons[]}`. A check is flagged if any axis flags it.

## How this differs

| Repo | What it does | When you use it |
|---|---|---|
| genai-eval | offline multilingual eval batch suites, 5 tasks x 3 langs | once per model release, off the hot path |
| eval-observability | daily Welch t-test cron on stored runs | overnight regression detection |
| promptforge | per-prompt version regression with cost/latency | when you edit a prompt |
| agentic-runner | agent loop with goal decomposition | building agents, not scoring outputs |
| **EvalForge** | inline three-axis scoring + review dashboard | every request, before output reaches user |

EvalForge is distinct on three axes:

1. **Inline REST API** other services call in the hot path before returning output to a user. This is a production safety gate, not an offline batch tool.
2. **Three-axis scoring** (quality + safety + moderation), not just task correctness. Moderation pass is its own load-bearing layer.
3. **React dashboard** for reviewing flagged outputs across prompt versions, with a queue for human reviewers to mark false positives. Corrections feed back into the scorer.

## Stack

Python 3.12, FastAPI, SQLAlchemy, Postgres, Pydantic v2. React 18, TypeScript, Vite, TanStack Query, Tailwind. structlog, Prometheus. pytest, hypothesis, testcontainers. Playwright e2e. Multi-stage Docker.

## Run it

```
docker compose up
```

API on `:8000`, web on `:5173`, Postgres on `:5432`.

### Use Claude for quality scoring

The default `EVALFORGE_PROVIDER=fake` runs without credentials or network calls.
To select the cloud judge, configure these environment variables before starting
the API or Compose stack:

| Variable | Value |
|---|---|
| `EVALFORGE_PROVIDER` | `claude` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key, supplied through a secret manager or local environment |
| `EVALFORGE_CLAUDE_MODEL` | An explicit model ID available to your account that supports structured JSON output |
| `EVALFORGE_API_KEY` | A separate, randomly generated service credential of at least 32 ASCII characters |
| `EVALFORGE_CLAUDE_MAX_CONCURRENCY` | Maximum concurrent evaluations per API process, from 1 to 16; defaults to 2 |

Claude selection fails at startup if its provider key, model, or service credential
is missing or invalid. Unknown provider names also fail explicitly. All `/v1`
HTTP routes require `Authorization: Bearer <EVALFORGE_API_KEY>` in Claude mode,
including review routes that influence future judgments. The live WebSocket also
requires that header; credentials in URL query strings are not accepted.
Health and metrics stay public. Fake mode keeps the credential-free local demo.

Use HTTPS and a trusted, authenticated server-side proxy for the dashboard in
Claude mode: the bundled browser client does not send service credentials, and
browser WebSocket clients cannot set this header. Keep both service and Anthropic
keys out of browser code, build variables, and URLs. The service credential grants
access to every review and evaluation, so restrict it to trusted services or
operators. Configure global rate and spending limits at your ingress and provider
account; concurrency limits apply separately to each worker process or replica.

The judge sends the rubric, evaluated text, and up to three reviewer examples to
Anthropic. Review data-sharing and provider terms for your inputs before enabling
this option. A supplied `context.rubric` must be nonblank text of at most 16,384
characters; invalid rubrics are rejected before any paid call.

Requests use the Messages API with a 512-token output limit, ten-second HTTPX
network-inactivity timeouts and a ten-second total network deadline, a 512 KiB
serialized request cap, and a 64 KiB response cap. There are no automatic retries
or redirects. Requests above the concurrency limit receive HTTP 503 with
`Retry-After: 1`; canceled callers retain their slot until provider work ends.
Invalid, incomplete, refused,
inconsistent, or nonfinite verdicts fail closed with HTTP 503 and create no
successful check. Upstream error bodies are not returned to callers.
The total deadline cancels active HTTP I/O; operating-system DNS resolution may
take longer to shut down, so it is not an absolute bound on worker lifetime.

Cloud evaluation runs in a worker thread so it does not block health requests or
other API work. Each evaluation uses its own prompt-specific reviewer examples.
The under-200ms benchmark above applies to FakeProvider; it is not a Claude
latency or judgment-accuracy guarantee. The Claude tests use synthetic credentials
and HTTPX MockTransport; deployment requires a separate live smoke test with the
operator's chosen model and account.

## Test

Frontend tools require Node.js 20.19+ on the 20.x release line, 22.12+ on 22.x,
or 24+. Install frontend dependencies from the committed lockfile with `npm ci`.

```
make test         # all unit + integration
make bench        # latency bench
make e2e          # Playwright
```

## Repo layout

```
apps/api/  Python FastAPI backend + scorers + store + queue + ws
apps/web/  React + TS + Vite dashboard
docs/      scoring axes, review workflow, inline latency, comparison
```

## License

MIT.
