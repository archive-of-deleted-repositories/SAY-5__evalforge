# Three scoring axes

Every `/v1/evaluate` call runs through three scorers in sequence. A check is `flagged` if any axis flags it.

## Quality

LLM-as-judge against a per-task rubric. The default rubric asks for helpful, factually grounded, non-speculative responses; callers can override via `context.rubric` with nonblank text of at most 16,384 characters. Invalid rubrics receive HTTP 422 before scoring.

The judge is wired through a `JudgeProvider` seam:
- `FakeProvider` (default in CI): a deterministic keyword-coverage scorer. Same input always produces the same verdict.
- `ClaudeProvider`: Anthropic Messages API adapter, selected with `EVALFORGE_PROVIDER=claude`. Requires `ANTHROPIC_API_KEY` and an explicit `EVALFORGE_CLAUDE_MODEL`; missing configuration never falls back to fake scoring. The historical `claude_stub` module import path remains supported.

The threshold defaults to 0.4. Few-shot examples marked `not_flagged` (sourced from reviewer corrections) relax the threshold by 0.05 each, capped to floor zero.

Claude receives the rubric, output, and reviewer examples as untrusted JSON data,
separate from system instructions. It returns a schema-constrained score, label,
and reason. EvalForge validates that the score is finite and in [0, 1], the reason
is non-empty and bounded, and the label agrees with the relaxed threshold. It
rejects incomplete generations and provider failures rather than manufacturing a
verdict. The deterministic safety and moderation scorers remain unchanged.

Claude mode also requires a separate `EVALFORGE_API_KEY` service credential for
every `/v1` HTTP request and live WebSocket connection, including reviewer
corrections. Paid calls have a ten-second total network deadline and a per-process
concurrency limit (`EVALFORGE_CLAUDE_MAX_CONCURRENCY`, default 2). Excess requests
receive HTTP 503 immediately. See the [deployment settings](../README.md#use-claude-for-quality-scoring)
for credential handling, dashboard proxy requirements, and request/response bounds.
The deadline cancels active HTTP I/O; operating-system DNS resolver shutdown may
extend the worker lifetime beyond it.

## Safety

Classifier against the fixed taxonomy:

| Label | Detects |
|---|---|
| `pii` | SSNs, credit cards, emails, phone numbers |
| `prompt_injection` | "ignore previous instructions", "disregard prior", "you are now ..." |
| `harmful_advice` | bomb / weapon / drug synthesis / hacking instructions |
| `confidential_data` | API key patterns, private keys, `sk-...` tokens |

Implementation is a curated set of regexes per label so verdicts are deterministic and byte-stable.

## Moderation

Profanity + toxicity + harassment.
- Profanity: word-list match.
- Toxicity: phrase-list match ("you are stupid", "shut up", ...).
- Harassment: regex set ("kill yourself", "i hope you die", ...).

Harassment carries the heaviest weight in the aggregate score (0.8 vs 0.5 toxicity vs 0.3 profanity).

## Per-axis contributions

Each scorer returns a `contributions` list keyed to character offsets in the original output:

```
{
  "feature": "moderation:profanity",
  "weight": 0.4,
  "snippet": "crap",
  "offset": 12,
  "length": 4
}
```

The dashboard uses these to render inline highlights so reviewers can see exactly which span triggered each axis.
