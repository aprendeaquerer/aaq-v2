from app.config import settings
from app.services.ai.base import AIProvider
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.anthropic_provider import AnthropicProvider

_provider = None


def get_ai_provider() -> AIProvider:
    global _provider
    if _provider is None:
        if settings.AI_PROVIDER == "anthropic":
            _provider = AnthropicProvider(
                api_key=settings.ANTHROPIC_API_KEY,
                model=settings.ANTHROPIC_MODEL,
            )
        else:
            _provider = OpenAIProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
                reasoning_effort=settings.OPENAI_REASONING_EFFORT,
            )
    return _provider
