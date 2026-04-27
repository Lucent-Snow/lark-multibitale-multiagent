"""
LLM client for 火山引擎 ARK (方舟).

ARK is OpenAI-compatible. We use the standard openai SDK with:
  - base_url: https://ark.cn-beijing.volces.com/api/v3
  - model:    the endpoint ID (ep-xxx)
"""

from openai import OpenAI


class LLMClient:
    """Thin wrapper around OpenAI client configured for ARK."""

    def __init__(self, api_key: str, endpoint_id: str):
        self._client = OpenAI(
            api_key=api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )
        self.endpoint_id = endpoint_id

    def chat(self, messages: list[dict], temperature: float = 0.7,
             max_tokens: int = 4096) -> str:
        """Send a chat completion request, return the reply text."""
        response = self._client.chat.completions.create(
            model=self.endpoint_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def chat_with_system(self, system_prompt: str, user_message: str,
                         temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Convenience: system prompt + single user message."""
        return self.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ], temperature=temperature, max_tokens=max_tokens)
