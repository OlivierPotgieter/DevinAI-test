"""Minimal LLM service layer with provider selection."""
from __future__ import annotations

import os
from typing import List, Dict

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

from openai import OpenAI

if load_dotenv:
    load_dotenv()


class BaseLLMService:
    def chat(self, messages: List[Dict[str, str]], model: str = "gpt-4o") -> str:
        raise NotImplementedError


class OpenAIService(BaseLLMService):
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)

    def chat(self, messages: List[Dict[str, str]], model: str = "gpt-4o") -> str:
        chat = self.client.chat.completions.create(model=model, messages=messages)
        return chat.choices[0].message.content.strip()


_PROVIDERS = {"openai": OpenAIService}


def get_service() -> BaseLLMService:
    provider = os.getenv("MCP_LLM_PROVIDER", "openai").lower()
    cls = _PROVIDERS.get(provider)
    if not cls:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    return cls()
