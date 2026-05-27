# Inline-latency bench

`evalforge.bench` spins up the FastAPI app in-process via `httpx.ASGITransport` and fires N concurrent callers, each making M `/v1/evaluate` calls.

## Run

```
make bench           # full: 1000 callers x 100 calls = 100k requests
make bench-smoke     # CI smoke: 100 callers x 10 calls = 1k requests
make bench-regress   # smoke + 30% drift gate against bench-baseline.json
```

## Honest numbers

A single Python process on a developer laptop hits sustained ~1.2-1.5k req/s, not the 10k aspirational target. The bottleneck is the GIL serializing the per-request CPU work in the scorers and the SQLAlchemy session checkout for the write queue's drain loop.

The hot path (FakeProvider, three scorers, write submit) takes about 60-100ms end-to-end p99 in the smoke run. The persistence write is fire-and-forget so it does not appear in the response latency — instead it shows up as `queue_depth_max` when bursts arrive faster than the drain loop processes them.

To approach 10k req/s in production:
- Run multiple uvicorn workers behind a shared Postgres (the current per-process queue is per-worker).
- Replace SQLAlchemy in the hot path with a raw psycopg `COPY FROM` pipeline.
- Move the moderation regex pass into a compiled Rust extension (it's the heaviest pure-Python scorer at scale).

The bench harness is honest about all of this. The regression gate is the load-bearing piece: it ensures changes do not silently drift latency or throughput by more than 30%.

## Regress gate

The first run (or one with `--save-baseline`) writes `apps/api/bench-baseline.json`. Subsequent runs with `--regress` fail if:
- any of p50, p95, p99, p999 drift up by more than 30%, OR
- req/sec drops by more than 30%.

CI runs the smoke + regress gate on every push.

## Sample output

```
{
  "callers": 100,
  "calls_per_caller": 10,
  "total_calls": 1000,
  "wall_seconds": 0.66,
  "req_per_sec": 1503,
  "latency_ms_p50": 64.5,
  "latency_ms_p95": 79.0,
  "latency_ms_p99": 85.2,
  "latency_ms_p999": 91.6,
  "queue_depth_max": 982,
  "axis_ms_quality_p99": 0.1,
  "axis_ms_safety_p99": 0.1,
  "axis_ms_moderation_p99": 0.1
}
```

Per-axis scorer time is sub-millisecond in the smoke; the end-to-end latency comes from ASGI scheduling overhead under 100 concurrent in-process callers, not the scorers themselves.
