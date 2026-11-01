"""Universal model provider for Governor research evaluation.

Enables evaluating stop-instruction persistence across:
1. Local open-weight models (Ollama, vLLM, e.g. Llama 3.3, Qwen 2.5 Coder, DeepSeek)
2. Hosted frontier models (Claude 3.5 Sonnet, GPT-4o, DeepSeek-R1 API)
3. Deterministic mock provider for hermetic testing and offline CI
"""

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from src.interceptors.base import AgentAction


@dataclass
class ModelResponse:
    """Parsed model response containing both chain-of-thought and structured tool action."""
    action: AgentAction
    cot_reasoning: str
    raw_response: str
    model_name: str


class BaseModelProvider(ABC):
    """Abstract base provider for language model inference."""

    def __init__(self, model_name: str, temperature: float = 0.0, seed: Optional[int] = 42):
        self.model_name = model_name
        self.temperature = temperature
        self.seed = seed

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        turn_history: List[Dict[str, str]],
        current_observation: str,
    ) -> ModelResponse:
        """Generate next tool action given trajectory history and boundary instruction."""
        pass

    def _parse_model_output(self, raw_text: str) -> ModelResponse:
        """Extract chain-of-thought scratchpad and JSON action from model output."""
        cot_reasoning = ""
        thought_match = re.search(r"<(?:thought|reasoning)>(.*?)</(?:thought|reasoning)>", raw_text, re.DOTALL | re.IGNORECASE)
        if thought_match:
            cot_reasoning = thought_match.group(1).strip()
        else:
            lines = raw_text.splitlines()
            thought_lines = []
            for line in lines:
                if line.strip().startswith("```") or line.strip().startswith("{"):
                    break
                thought_lines.append(line)
            cot_reasoning = "\n".join(thought_lines).strip()

        # Extract JSON action block
        json_str = None
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            raw_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw_text, re.DOTALL)
            if raw_match:
                json_str = raw_match.group(0)

        action = None
        if json_str:
            try:
                data = json.loads(json_str)
                action = AgentAction(
                    op=data.get("op", data.get("action_type", "read")),
                    target_path=data.get("target_path", "/project/README.md"),
                    content=data.get("content", ""),
                    cot_reasoning=cot_reasoning or data.get("cot_reasoning", ""),
                )
            except Exception:
                pass

        if not action:
            action = AgentAction(
                op="read",
                target_path="/project/README.md",
                cot_reasoning=cot_reasoning,
            )

        return ModelResponse(
            action=action,
            cot_reasoning=cot_reasoning,
            raw_response=raw_text,
            model_name=self.model_name,
        )


class MockModelProvider(BaseModelProvider):
    """Deterministic offline provider for testing and validation without API keys."""

    def __init__(self, model_name: str = "mock-agent", predetermined_action: Optional[AgentAction] = None):
        super().__init__(model_name=model_name)
        self.predetermined_action = predetermined_action or AgentAction(
            op="read",
            target_path="/project/README.md",
            cot_reasoning="Offline mock step",
        )

    def generate(
        self,
        system_prompt: str,
        turn_history: List[Dict[str, str]],
        current_observation: str,
    ) -> ModelResponse:
        return ModelResponse(
            action=self.predetermined_action,
            cot_reasoning=self.predetermined_action.cot_reasoning or "Inspecting current workspace.",
            raw_response=json.dumps({
                "op": self.predetermined_action.op,
                "target_path": self.predetermined_action.target_path,
                "content": self.predetermined_action.content,
            }),
            model_name=self.model_name,
        )


class OpenAICompatibleProvider(BaseModelProvider):
    """Provider for OpenAI-compatible endpoints.

    Works seamlessly with:
    - Local Ollama: base_url='http://localhost:11434/v1'
    - Local vLLM: base_url='http://localhost:8000/v1'
    - OpenRouter: base_url='https://openrouter.ai/api/v1'
    - Official OpenAI: base_url='https://api.openai.com/v1'
    - Groq: base_url='https://api.groq.com/openai/v1'
    """

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        seed: Optional[int] = 42,
        timeout: int = 60,
    ):
        super().__init__(model_name=model_name, temperature=temperature, seed=seed)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "ollama")
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        turn_history: List[Dict[str, str]],
        current_observation: str,
    ) -> ModelResponse:
        messages = [{"role": "system", "content": system_prompt}]
        for turn in turn_history:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
        messages.append({"role": "user", "content": current_observation})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
            "seed": self.seed,
        }

        req = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                return self._parse_model_output(content)
        except Exception as e:
            return ModelResponse(
                action=AgentAction(
                    op="read",
                    target_path="/project/README.md",
                    cot_reasoning=f"Model API error: {e}",
                ),
                cot_reasoning="",
                raw_response=f"Error: {e}",
                model_name=self.model_name,
            )


class AnthropicProvider(BaseModelProvider):
    """Provider for Anthropic Messages API (Claude 3.5 Sonnet, Claude 3.5 Haiku)."""

    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-latest",
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        timeout: int = 60,
    ):
        super().__init__(model_name=model_name, temperature=temperature)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        turn_history: List[Dict[str, str]],
        current_observation: str,
    ) -> ModelResponse:
        messages = []
        for turn in turn_history:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
        messages.append({"role": "user", "content": current_observation})

        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": self.temperature,
        }

        req = Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
                content = "\n".join(text_parts)
                return self._parse_model_output(content)
        except Exception as e:
            return ModelResponse(
                action=AgentAction(
                    op="read",
                    target_path="/project/README.md",
                    cot_reasoning=f"Anthropic API error: {e}",
                ),
                cot_reasoning="",
                raw_response=f"Error: {e}",
                model_name=self.model_name,
            )


def get_provider(model_spec: str, **kwargs) -> BaseModelProvider:
    """Factory creating appropriate model provider based on spec prefix."""
    if model_spec == "mock":
        return MockModelProvider(**kwargs)

    if model_spec.startswith("ollama/"):
        name = model_spec.replace("ollama/", "")
        base_url = kwargs.pop("base_url", "http://localhost:11434/v1")
        return OpenAICompatibleProvider(model_name=name, base_url=base_url, **kwargs)

    if model_spec.startswith("vllm/"):
        name = model_spec.replace("vllm/", "")
        base_url = kwargs.pop("base_url", "http://localhost:8000/v1")
        return OpenAICompatibleProvider(model_name=name, base_url=base_url, **kwargs)

    if model_spec.startswith("openrouter/"):
        name = model_spec.replace("openrouter/", "")
        base_url = "https://openrouter.ai/api/v1"
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        return OpenAICompatibleProvider(model_name=name, base_url=base_url, api_key=api_key, **kwargs)

    if model_spec.startswith("openai/"):
        name = model_spec.replace("openai/", "")
        base_url = "https://api.openai.com/v1"
        return OpenAICompatibleProvider(model_name=name, base_url=base_url, **kwargs)

    if model_spec.startswith("anthropic/"):
        name = model_spec.replace("anthropic/", "")
        return AnthropicProvider(model_name=name, **kwargs)

    return OpenAICompatibleProvider(model_name=model_spec, **kwargs)
