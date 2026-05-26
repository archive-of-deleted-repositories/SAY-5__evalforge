# How EvalForge differs from genai-eval

Both repos evaluate LLM outputs, but they operate on different timescales and against different needs.

| Dimension | genai-eval | EvalForge |
|---|---|---|
| When you call it | once per model release, off the hot path | every request, inline before output reaches user |
| Latency tolerance | minutes per task suite | p99 < 200ms (FakeProvider) |
| Scope | task correctness across 5 task types x 3 languages | three axes: quality + safety + moderation |
| Output | offline reports + dashboards over batch runs | live verdict per call + persisted check |
| Failure mode | drift detected next batch run | gate trips on the current request |
| Audience | model evaluation engineers | service owners + content trust + safety |

If you only need offline evaluation, use genai-eval. If you need a production safety gate that scores every output before it ships to a user, use EvalForge.

The two are complementary: genai-eval runs batch suites to validate a model before rollout, EvalForge sits in the request path after rollout.
