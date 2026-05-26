# Review workflow

Every flagged check lands in a review queue. Reviewers triage it into one of three terminal labels.

## States

```
unreviewed ──► correct
           ──► false_positive  (scorer wrong; output is fine)
           ──► false_negative  (scorer missed it; output is bad)
```

Transitions are one-way. Once a check is marked, the label is locked. Attempting to change it returns `409 Conflict`. This invariant is enforced at the store layer and covered by a property test in v1.

## Feedback loop

A `false_positive` review writes `(prompt_version, output_text, correct_label="not_flagged")` to the `labeled_examples` table. A `false_negative` writes `correct_label="flagged"`.

The quality scorer reads up to 3 random recent labeled examples for the current prompt version on every `/v1/evaluate` call and includes them as few-shot demonstrations in the rubric prompt. Each `not_flagged` demonstration relaxes the threshold by 0.05.

See `docs/active-learning.md` for the loop in detail and its trade-offs.

## API

```
GET  /v1/queue              # flagged + unreviewed checks
POST /v1/checks/{id}/review { "label": "correct" | "false_positive" | "false_negative" }
GET  /v1/prompt-versions/stats
```

The dashboard's Review Queue page wraps these.
