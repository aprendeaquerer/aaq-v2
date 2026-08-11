from typing import Dict, List, Optional

from openai import AsyncOpenAI

from app.services.ai.base import AIProvider


class OpenAIProvider(AIProvider):
    _REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-luna",
        reasoning_effort: str = "low",
    ):
        self._validate_reasoning_effort(reasoning_effort)
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.reasoning_effort = reasoning_effort

    @classmethod
    def _validate_reasoning_effort(cls, value: str) -> None:
        if value not in cls._REASONING_EFFORTS:
            allowed = ", ".join(sorted(cls._REASONING_EFFORTS))
            raise ValueError(f"Unsupported OpenAI reasoning effort {value!r}; use one of: {allowed}")

    def _supports_reasoning(self) -> bool:
        return self.model.startswith(("gpt-5", "o1", "o3", "o4"))

    async def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        effort = reasoning_effort or self.reasoning_effort
        self._validate_reasoning_effort(effort)
        request: Dict[str, object] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": messages,
            "max_output_tokens": max_tokens,
        }
        if self._supports_reasoning():
            request["reasoning"] = {"effort": effort}
            if effort == "none":
                request["temperature"] = temperature
        else:
            request["temperature"] = temperature

        response = await self.client.responses.create(**request)
        return response.output_text or ""
