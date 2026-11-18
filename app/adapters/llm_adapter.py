"""Provider-agnostic LLM adapter for PlantGuard.

All LLM interactions throughout the application go through this adapter.
No provider-specific SDK calls exist outside of this module.
Provider switching requires only configuration changes.
"""
from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from app.config.settings import LLMProvider, Settings, get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_JSON_FENCE = re_pattern = None


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_estimate_usd: float = 0.0
    used_fallback: bool = False
    metadata: Dict[str, Any] = {}


class LLMError(Exception):
    """Base exception for LLM operations."""
    def __init__(self, message: str, provider: str = "", retryable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        output_schema: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        """Generate structured output validated against a Pydantic schema."""
        ...


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider via direct REST endpoint."""

    def __init__(
        self,
        settings: Settings,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        super().__init__(settings)
        self._api_key = api_key or settings.LLM_API_KEY
        self._model_name = model or settings.LLM_MODEL

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        temp = temperature if temperature is not None else self.settings.LLM_TEMPERATURE
        max_tok = max_tokens or self.settings.LLM_MAX_TOKENS

        contents = []
        system_instruction = None
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temp,
                "maxOutputTokens": max_tok,
                "topP": self.settings.LLM_TOP_P,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model_name}:generateContent?key={self._api_key}"
        )

        start_time = time.monotonic()
        try:
            resp = requests.post(url, json=payload, timeout=self.settings.LLM_TIMEOUT_SECONDS)
            latency_ms = (time.monotonic() - start_time) * 1000

            if resp.status_code != 200:
                is_retryable = resp.status_code in (429, 500, 502, 503, 504)
                raise LLMError(
                    f"Gemini API returned status {resp.status_code}: {resp.text[:300]}",
                    provider="gemini",
                    retryable=is_retryable,
                )

            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                raise LLMError("No candidates returned from Gemini", provider="gemini")

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts)

            usage = data.get("usageMetadata", {})
            prompt_tokens = usage.get("promptTokenCount", 0)
            completion_tokens = usage.get("candidatesTokenCount", 0)
            total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

            # Approx cost calculation for Gemini Flash
            cost_estimate = (prompt_tokens * 0.000000075) + (completion_tokens * 0.0000003)

            return LLMResponse(
                content=text,
                model=self._model_name,
                provider="gemini",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost_estimate_usd=round(cost_estimate, 7),
            )
        except requests.RequestException as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.error("Gemini request failed", extra={"error": str(e), "latency_ms": latency_ms})
            raise LLMError(f"Gemini connection error: {e}", provider="gemini", retryable=True)

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        output_schema: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        schema_json = output_schema.model_json_schema()
        schema_instruction = (
            f"\n\nYou MUST respond with a strictly valid JSON object matching this schema:\n"
            f"```json\n{json.dumps(schema_json, indent=2)}\n```\n"
            f"Respond ONLY with the JSON object, with no conversational preamble or markdown code blocks."
        )

        enhanced = list(messages)
        if enhanced and enhanced[-1]["role"] == "user":
            enhanced[-1] = {
                "role": "user",
                "content": enhanced[-1]["content"] + schema_instruction,
            }
        else:
            enhanced.append({"role": "user", "content": schema_instruction})

        response = self.generate(enhanced, temperature=temperature, max_tokens=max_tokens, **kwargs)

        content = response.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        parsed = output_schema.model_validate_json(content)
        return parsed, response


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI-compatible provider (works with OpenAI, OpenRouter, and Ollama)."""

    def __init__(
        self,
        settings: Settings,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(settings)
        self._api_key = api_key or settings.LLM_API_KEY
        self._model_name = model or settings.LLM_MODEL
        self._base_url = (base_url or settings.LLM_BASE_URL or "https://api.openai.com/v1").rstrip("/")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        temp = temperature if temperature is not None else self.settings.LLM_TEMPERATURE
        max_tok = max_tokens or self.settings.LLM_MAX_TOKENS

        payload = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tok,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        start_time = time.monotonic()
        try:
            resp = requests.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.settings.LLM_TIMEOUT_SECONDS,
            )
            latency_ms = (time.monotonic() - start_time) * 1000

            if resp.status_code != 200:
                is_retryable = resp.status_code in (429, 500, 502, 503, 504)
                raise LLMError(
                    f"OpenAI-compatible API error {resp.status_code}: {resp.text[:300]}",
                    provider="openai_compatible",
                    retryable=is_retryable,
                )

            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            return LLMResponse(
                content=content,
                model=self._model_name,
                provider="openai_compatible",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost_estimate_usd=round(total_tokens * 0.0000005, 7),
            )
        except requests.RequestException as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            raise LLMError(f"OpenAI-compatible connection error: {e}", provider="openai_compatible", retryable=True)

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        output_schema: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        schema_json = output_schema.model_json_schema()
        schema_instruction = (
            f"\n\nRespond with a valid JSON object matching this schema:\n"
            f"```json\n{json.dumps(schema_json, indent=2)}\n```\n"
            f"Respond ONLY with the JSON object."
        )

        enhanced = list(messages)
        if enhanced and enhanced[-1]["role"] == "user":
            enhanced[-1] = {
                "role": "user",
                "content": enhanced[-1]["content"] + schema_instruction,
            }
        else:
            enhanced.append({"role": "user", "content": schema_instruction})

        response = self.generate(enhanced, temperature=temperature, max_tokens=max_tokens, **kwargs)

        content = response.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        parsed = output_schema.model_validate_json(content)
        return parsed, response


class LLMAdapter:
    """
    Provider-agnostic LLM adapter with bounded repair and fallback support.
    """

    MAX_REPAIR_ATTEMPTS = 3

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._primary = self._create_provider(
            self._settings.LLM_PROVIDER,
            self._settings.LLM_API_KEY,
            self._settings.LLM_MODEL,
            self._settings.LLM_BASE_URL,
        )
        self._fallback: Optional[BaseLLMProvider] = None
        if self._settings.FALLBACK_LLM_PROVIDER and self._settings.FALLBACK_LLM_API_KEY:
            self._fallback = self._create_provider(
                self._settings.FALLBACK_LLM_PROVIDER,
                self._settings.FALLBACK_LLM_API_KEY,
                self._settings.FALLBACK_LLM_MODEL or self._settings.LLM_MODEL,
                self._settings.FALLBACK_LLM_BASE_URL,
            )

    def _create_provider(
        self,
        provider: LLMProvider,
        api_key: str,
        model: str,
        base_url: Optional[str],
    ) -> BaseLLMProvider:
        if provider == LLMProvider.GEMINI:
            return GeminiProvider(self._settings, api_key=api_key, model=model)
        elif provider in (LLMProvider.OPENAI, LLMProvider.OPENROUTER):
            return OpenAICompatibleProvider(
                self._settings, api_key=api_key, model=model, base_url=base_url
            )
        elif provider == LLMProvider.OLLAMA:
            return OpenAICompatibleProvider(
                self._settings,
                api_key="ollama",
                model=model,
                base_url=base_url or "http://localhost:11434/v1",
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        try:
            return self._primary.generate(messages, temperature, max_tokens, **kwargs)
        except LLMError as e:
            if self._fallback and self._settings.ENABLE_FALLBACK and e.retryable:
                logger.warning("Primary LLM call failed, executing fallback", extra={"error": str(e)})
                resp = self._fallback.generate(messages, temperature, max_tokens, **kwargs)
                resp.used_fallback = True
                return resp
            raise

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        output_schema: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> tuple[T, LLMResponse]:
        """
        Generate structured output with bounded repair loop (up to 3 attempts).
        """
        last_error: Optional[Exception] = None
        current_messages = list(messages)

        for attempt in range(1, self.MAX_REPAIR_ATTEMPTS + 1):
            try:
                try:
                    result, response = self._primary.generate_structured(
                        current_messages, output_schema, temperature, max_tokens, **kwargs
                    )
                except LLMError as e:
                    if self._fallback and self._settings.ENABLE_FALLBACK and attempt == 1:
                        logger.warning("Primary structured generation failed, using fallback")
                        result, response = self._fallback.generate_structured(
                            current_messages, output_schema, temperature, max_tokens, **kwargs
                        )
                        response.used_fallback = True
                    else:
                        raise

                response.metadata["parse_attempt"] = attempt
                response.metadata["total_attempts"] = attempt
                return result, response

            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning(
                    f"Structured validation failed on attempt {attempt}: {e}"
                )

                if attempt < self.MAX_REPAIR_ATTEMPTS:
                    repair_prompt = (
                        f"Your previous response was rejected due to validation errors:\n"
                        f"{str(e)}\n"
                        f"Fix the JSON response to strictly match the schema. Return ONLY valid JSON."
                    )
                    current_messages = list(messages)
                    current_messages.append({"role": "user", "content": repair_prompt})

        raise LLMError(
            f"Failed to generate valid structured output after {self.MAX_REPAIR_ATTEMPTS} attempts. "
            f"Validation error: {last_error}",
            provider=self._settings.LLM_PROVIDER.value,
            retryable=False,
        )
