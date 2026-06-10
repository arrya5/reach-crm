"""Provider-agnostic LLM interface + a Gemini implementation.

The agent loop (``agent.py``) speaks only in the normalized ``Turn`` / ``ToolCall``
/ ``LLMResult`` types defined here, so swapping Gemini for Groq/Cerebras/OpenAI
is a matter of writing one more ``LLMProvider`` — the orchestration never changes.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..config import settings


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict          # JSON Schema for the tool's arguments


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class Turn:
    """One normalized conversation turn."""
    role: str                 # "user" | "model" | "tool"
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str = ""       # for role == "tool"
    tool_result: Any = None   # for role == "tool"


@dataclass
class LLMResult:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self, system: str, history: list[Turn], tools: list[ToolSpec]
    ) -> LLMResult:
        ...


class GeminiProvider(LLMProvider):
    """Google Gemini via the ``google-genai`` SDK (default: gemini-2.5-flash)."""

    def __init__(self) -> None:
        from google import genai  # imported lazily so the app boots without the key

        self._genai = genai
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def _to_contents(self, history: list[Turn]):
        from google.genai import types

        contents = []
        for turn in history:
            if turn.role == "user":
                contents.append(types.Content(
                    role="user", parts=[types.Part(text=turn.text)]
                ))
            elif turn.role == "model":
                parts = []
                if turn.text:
                    parts.append(types.Part(text=turn.text))
                for call in turn.tool_calls:
                    parts.append(types.Part(
                        function_call=types.FunctionCall(name=call.name, args=call.args)
                    ))
                contents.append(types.Content(role="model", parts=parts))
            elif turn.role == "tool":
                contents.append(types.Content(role="tool", parts=[
                    types.Part.from_function_response(
                        name=turn.tool_name, response={"result": turn.tool_result}
                    )
                ]))
        return contents

    def _to_tools(self, tools: list[ToolSpec]):
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(
                name=t.name, description=t.description, parameters=t.parameters
            )
            for t in tools
        ]
        return [types.Tool(function_declarations=declarations)]

    async def generate(
        self, system: str, history: list[Turn], tools: list[ToolSpec]
    ) -> LLMResult:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=self._to_tools(tools),
            temperature=0.4,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = self._to_contents(history)

        # The SDK call is synchronous; run it off the event loop.
        resp = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=contents,
            config=config,
        )

        result = LLMResult()
        candidate = resp.candidates[0]
        for part in candidate.content.parts or []:
            if getattr(part, "function_call", None):
                fc = part.function_call
                result.tool_calls.append(ToolCall(name=fc.name, args=dict(fc.args or {})))
            elif getattr(part, "text", None):
                result.text += part.text
        return result


def get_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiProvider()
    raise ValueError(f"unsupported llm_provider: {settings.llm_provider}")
