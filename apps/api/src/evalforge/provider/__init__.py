"""LLM provider seam. FakeProvider for hermetic CI, ClaudeProvider as a stub."""

from evalforge.provider._base import JudgeProvider, JudgeVerdict
from evalforge.provider.claude_stub import ClaudeProvider
from evalforge.provider.fake import FakeProvider, get_default_provider

__all__ = [
    "JudgeProvider",
    "JudgeVerdict",
    "FakeProvider",
    "ClaudeProvider",
    "get_default_provider",
]
