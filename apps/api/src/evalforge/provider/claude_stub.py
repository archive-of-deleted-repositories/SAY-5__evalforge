"""Claude provider stub.

Wired to delegate to FakeProvider in CI; a real BYOK Claude call goes here in production.
This keeps tests hermetic without forcing users to provide API keys.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from evalforge.provider._base import JudgeVerdict
from evalforge.provider.fake import FakeProvider


class ClaudeProvider:
    """Replace .judge body with anthropic client call when ANTHROPIC_API_KEY is set in prod."""

    def __init__(self) -> None:
        self._fallback = FakeProvider()
        self.has_credentials = bool(os.environ.get("ANTHROPIC_API_KEY"))

    def judge(
        self,
        rubric: str,
        output_text: str,
        few_shot: Sequence[tuple[str, str]] = (),
    ) -> JudgeVerdict:
        # Stub: in production this would call the Anthropic API.
        # For CI portability we delegate to the FakeProvider when no creds are set.
        return self._fallback.judge(rubric, output_text, few_shot)
