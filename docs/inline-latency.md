# Inline latency

EvalForge is designed to be called inline by other services before they return output to a user. The latency budget matters.

## Target

p99 latency under 200ms (FakeProvider) for the round trip: network in, three scorers, response out. Persistence is async via an in-process queue so it does not contribute to client-observed latency.

## Architecture

```
caller ──HTTP──► FastAPI ──► ScoringEngine ──► response
                                │
                                └─► WriteQueue ──► Postgres
                                                      │
                                                      └─► LiveFeed (WebSocket fan-out)
```

`submit_nowait` drops the persistence write if the queue is saturated. The scoring verdict is still returned to the caller; only the audit trail is lost. The bench gate (v2) makes that trade explicit.

## Bench

`make bench` runs 1000 simulated concurrent callers with 100 calls each (default; configurable). The harness reports throughput, P50/P95/P99/P99.9 end-to-end latency, queue depth over time, and per-axis scorer time.

`make bench-regress` re-runs and fails if any P-percentile drifts more than 30% from the pinned baseline.

The CI runs a 100-caller × 10-call smoke so the bench gate has hermetic coverage on every push.

See v2's `docs/bench.md` for the actual numbers from a recent run.
