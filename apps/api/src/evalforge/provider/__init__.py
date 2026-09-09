"""LLM provider seam. FakeProvider for hermetic CI, explicit Claude for cloud judging."""

from evalforge.provider._base import JudgeProvider, JudgeProviderError, JudgeVerdict
from evalforge.provider.claude_stub import ClaudeProvider
from evalforge.provider.fake import FakeProvider, get_default_provider

__all__ = [
    "JudgeProvider",
    "JudgeProviderError",
    "JudgeVerdict",
    "FakeProvider",
    "ClaudeProvider",
    "get_default_provider",
]
