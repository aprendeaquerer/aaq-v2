from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class AIProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        """Send messages and get a completion. Stateless - caller manages history.

        Args:
            system_prompt: The system-level instruction for the AI.
            messages: List of {"role": "user"|"assistant", "content": "..."} dicts.
            temperature: Creativity level (0-1).
            max_tokens: Maximum response length.
            reasoning_effort: Optional provider-specific reasoning level override.

        Returns:
            The AI's response text.
        """
        ...
