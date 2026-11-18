"""Tests for M1: Provider-agnostic LLM adapter."""
from typing import Dict, List, Optional
import pytest
from pydantic import BaseModel, Field

from app.adapters.llm_adapter import LLMAdapter, LLMError, LLMResponse
from app.config.settings import LLMProvider, Settings


class SampleExtraction(BaseModel):
    asset_tag: str = Field(..., description="Asset identifier")
    fault_identified: str = Field(..., description="Short fault description")
    urgency_level: str = Field(..., description="Urgency: P1, P2, P3, P4")


def test_adapter_initialization_from_settings():
    """Verify adapter initializes strictly from Settings with zero hardcoded call sites."""
    settings = Settings(
        LLM_PROVIDER=LLMProvider.GEMINI,
        LLM_MODEL="gemini-3.1-flash-lite",
        LLM_API_KEY="test-mock-key",
    )
    adapter = LLMAdapter(settings)
    assert adapter._primary.settings.LLM_PROVIDER == LLMProvider.GEMINI
    assert adapter._primary.settings.LLM_MODEL == "gemini-3.1-flash-lite"


def test_provider_switching_without_code_edits():
    """Verify switching provider requires only settings change (M1.C2)."""
    # Switch to OpenAI-compatible
    settings_openai = Settings(
        LLM_PROVIDER=LLMProvider.OPENAI,
        LLM_MODEL="gpt-4o-mini",
        LLM_API_KEY="test-openai-key",
        LLM_BASE_URL="https://api.openai.com/v1",
    )
    adapter_openai = LLMAdapter(settings_openai)
    assert adapter_openai._primary.__class__.__name__ == "OpenAICompatibleProvider"

    # Switch to Ollama
    settings_ollama = Settings(
        LLM_PROVIDER=LLMProvider.OLLAMA,
        LLM_MODEL="llama3.1:8b",
        LLM_BASE_URL="http://localhost:11434/v1",
    )
    adapter_ollama = LLMAdapter(settings_ollama)
    assert adapter_ollama._primary.__class__.__name__ == "OpenAICompatibleProvider"


def test_structured_output_repair_simulation():
    """Verify bounded repair loop handles invalid initial output."""
    class MockFlakyProvider:
        settings = Settings()
        attempts = 0

        def generate_structured(self, messages, output_schema, temperature=None, max_tokens=None, **kwargs):
            self.attempts += 1
            if self.attempts < 2:
                # Return bad JSON that triggers validation error
                raise ValueError("Simulated schema mismatch: missing required field 'urgency_level'")
            # Return valid object
            obj = SampleExtraction(
                asset_tag="VPW-CNC-MILL-01",
                fault_identified="Spindle thermal expansion",
                urgency_level="P2",
            )
            resp = LLMResponse(
                content=obj.model_dump_json(),
                model="mock-model",
                provider="mock",
                prompt_tokens=120,
                completion_tokens=45,
                total_tokens=165,
                latency_ms=150.0,
            )
            return obj, resp

    adapter = LLMAdapter()
    adapter._primary = MockFlakyProvider()  # type: ignore

    result, resp = adapter.generate_structured(
        [{"role": "user", "content": "Extract data"}],
        SampleExtraction,
    )
    assert result.asset_tag == "VPW-CNC-MILL-01"
    assert result.urgency_level == "P2"
    assert adapter._primary.attempts == 2
    assert resp.metadata.get("total_attempts") == 2
