# Active learning: reviewer labels feed the quality scorer

Human review is not a dead end. When a reviewer marks a flagged check as a
mistake, that correction loops back into the scorer so the same class of output
stops getting flagged.

## The loop

```
/v1/evaluate ──► quality flags borderline output ──► review queue
      ▲                                                   │
      │                                          reviewer marks false_positive
      │                                                   │
      └──── few-shot demo relaxes the rubric ◄── labeled_examples row
```

1. A reviewer marks a check `false_positive`. The store writes
   `(prompt_version, output_text, correct_label="not_flagged")` into the
   `labeled_examples` table (`Store.review`).
2. On the next `/v1/evaluate` for that `prompt_version`, the API samples up to 3
   recent labeled examples (`Store.sample_labeled_examples`) and hands them to
   the quality scorer as few-shot demonstrations.
3. Each `not_flagged` demonstration relaxes the judge threshold by 0.05, so a
   borderline output that previously sat just under the bar now clears it. The
   provider's `on_rubric` / `off_rubric` label is authoritative for the flag, so
   the relaxation flows straight through to the verdict.

`false_negative` marks write `correct_label="flagged"` for symmetry, but only
`not_flagged` demos move the threshold today.

## What the test proves

`tests/unit/test_active_learning.py` posts 50 borderline outputs (each hits ~29%
of the rubric tokens, below the 0.40 base threshold), confirms all 50 flag on
quality, marks 10 as `false_positive`, then re-evaluates those 10. With three
`not_flagged` demos sampled, the effective threshold drops to 0.25 and the
re-evaluated outputs clear it. The assertion requires at least 5 of the 10 to
flip to `not_flagged`; in practice all 10 do.

## Drift trade-off

This is a feedback loop, so it can be steered in the wrong direction.

- **Over-relaxation.** Every `not_flagged` demo lowers the bar. Enough
  corrections for one prompt version and the quality scorer stops flagging
  almost anything, including genuinely off-rubric output. The 0.05-per-demo step
  and the hard cap of 3 sampled demos bound this: the threshold can fall by at
  most 0.15 from a single batch, never to zero.
- **Reviewer error compounds.** A wrong `false_positive` is a poisoned example.
  Because sampling favors recent rows, a burst of bad labels has outsized
  short-term influence. There is no demotion path for a labeled example once
  written; correcting course means adding counter-examples, not deleting.
- **Per-version isolation.** Labels are scoped to `prompt_version`, so relaxing
  one version never weakens another. New versions start from the base threshold
  with no inherited drift.
- **Sampling is random and recency-weighted, not curated.** The demos shown to
  the judge are not deduplicated or quality-ranked. This keeps the loop cheap and
  hermetic but means the signal is noisy by design.

The honest framing: this is a lightweight nudge, not a trained classifier. It
shifts a single scalar threshold using a tiny, capped sample. It is enough to
make repeated false positives stop recurring without a retraining pipeline, and
the caps keep a bad day of reviewing from collapsing the scorer.
