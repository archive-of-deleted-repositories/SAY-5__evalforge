# EvalForge

Inline GenAI evaluation and moderation service. A Python FastAPI backend that scores model outputs on three axes (quality, safety, moderation), exposes a low-latency REST endpoint other services call before returning to users, persists every check to Postgres for review, and ships a React dashboard for reviewing flagged outputs across prompt versions.

## What it does

Other services call `POST /v1/evaluate` with a model output. EvalForge scores it on three axes and returns a verdict in under 200ms (p99, FakeProvider in CI). If any axis flags the output, the check lands in a review queue where humans triage it. Reviewer corrections feed back into the scorer.

The three axes:

| Axis | Detects | Method |
|---|---|---|
| Quality | task-correctness against a rubric | LLM-judge (FakeProvider in CI, BYOK stub for Claude) |
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

## Test

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
