from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.ai.openai_provider import OpenAIProvider


def provider(model: str = "gpt-5.6-luna") -> tuple[OpenAIProvider, AsyncMock]:
    instance = OpenAIProvider(api_key="sk-test", model=model, reasoning_effort="low")
    create = AsyncMock(return_value=SimpleNamespace(output_text="respuesta"))
    instance.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    return instance, create


@pytest.mark.asyncio
async def test_uses_responses_api_with_low_reasoning_by_default():
    instance, create = provider()

    result = await instance.chat(
        system_prompt="instrucciones",
        messages=[{"role": "user", "content": "hola"}],
        temperature=0.7,
        max_tokens=300,
    )

    assert result == "respuesta"
    kwargs = create.await_args.kwargs
    assert kwargs["model"] == "gpt-5.6-luna"
    assert kwargs["instructions"] == "instrucciones"
    assert kwargs["reasoning"] == {"effort": "low"}
    assert kwargs["max_output_tokens"] == 300
    assert "temperature" not in kwargs


@pytest.mark.asyncio
async def test_simulator_can_disable_reasoning_and_keep_temperature():
    instance, create = provider()

    await instance.chat(
        system_prompt="interpreta una persona",
        messages=[{"role": "user", "content": "empieza"}],
        temperature=0.9,
        max_tokens=220,
        reasoning_effort="none",
    )

    kwargs = create.await_args.kwargs
    assert kwargs["reasoning"] == {"effort": "none"}
    assert kwargs["temperature"] == 0.9


@pytest.mark.asyncio
async def test_non_reasoning_model_remains_compatible():
    instance, create = provider(model="gpt-4o-mini")

    await instance.chat(
        system_prompt="instrucciones",
        messages=[{"role": "user", "content": "hola"}],
    )

    kwargs = create.await_args.kwargs
    assert "reasoning" not in kwargs
    assert kwargs["temperature"] == 0.7
