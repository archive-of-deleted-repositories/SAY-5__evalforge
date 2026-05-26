# Three scoring axes

Every `/v1/evaluate` call runs through three scorers in sequence. A check is `flagged` if any axis flags it.

## Quality

LLM-as-judge against a per-task rubric. The default rubric asks for helpful, factually grounded, non-speculative responses; callers can override via `context.rubric`.

The judge is wired through a `JudgeProvider` seam:
- `FakeProvider` (default in CI): a deterministic keyword-coverage scorer. Same input always produces the same verdict.
- `ClaudeProvider`: stub that delegates to FakeProvider unless `ANTHROPIC_API_KEY` is set. Swap in the real Anthropic call in production.

The threshold defaults to 0.4. Few-shot examples marked `not_flagged` (sourced from reviewer corrections) relax the threshold by 0.05 each, capped to floor zero.

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
