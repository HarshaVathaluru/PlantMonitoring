"""PlantGuard centralised configuration.

Every shared policy threshold, provider setting, database URL, and safety limit
has ONE authoritative definition here. All agents, routers, tools, validators,
and guardrails import from this module.
"""
from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"


class Settings(BaseSettings):
    """Single source of truth for all PlantGuard configuration."""

    # ── Project paths ──
    PROJECT_ROOT: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    DATA_DIR: Optional[Path] = None

    # ── LLM provider ──
    LLM_PROVIDER: LLMProvider = LLMProvider.GEMINI
    LLM_MODEL: str = "gemini-flash-lite-latest"
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: str = Field(default="", description="API key loaded strictly from environment or .env - zero hardcoded default")
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT_SECONDS: int = 60

    # ── Secondary / fallback LLM provider ──
    FALLBACK_LLM_PROVIDER: Optional[LLMProvider] = None
    FALLBACK_LLM_MODEL: Optional[str] = None
    FALLBACK_LLM_BASE_URL: Optional[str] = None
    FALLBACK_LLM_API_KEY: Optional[str] = None

    # ── Databases ──
    DATABASE_URL: str = "sqlite:///plantguard.db"
    MEMORY_DATABASE_URL: str = "sqlite:///plantguard_memory.db"
    CHECKPOINT_DATABASE_URL: str = "sqlite:///plantguard_checkpoints.db"

    # ── Vector database (Qdrant) ──
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "plantguard_manuals"
    QDRANT_USE_IN_MEMORY: bool = True
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # ── RAG settings ──
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 64
    RAG_TOP_K: int = 10
    RAG_RERANK_TOP_K: int = 5
    RAG_MIN_RELEVANCE_SCORE: float = 0.3

    # ── LangFuse observability ──
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # ── API settings ──
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = False

    # ── Authoritative physical safety limits ──
    SAFETY_VIBRATION_MAX_MM_S: float = 500.0   # Above this is physically impossible/sensor fault
    SAFETY_TEMP_MIN_C: float = -30.0           # Below this is physically impossible in plant
    SAFETY_TEMP_MAX_C: float = 500.0           # Above this is physically impossible/sensor fault
    SAFETY_PRESSURE_MIN_BAR: float = 0.0
    SAFETY_PRESSURE_MAX_BAR: float = 500.0
    SAFETY_CURRENT_MAX_A: float = 1000.0

    # ── Authoritative criticality thresholds (Clause 2.1) ──
    CRITICALITY_A_MIN_COST_INR: int = 30000
    CRITICALITY_B_MIN_COST_INR: int = 10000
    CRITICALITY_B_MAX_COST_INR: int = 29999
    CRITICALITY_A_DEFAULT_RATE_INR: int = 40000
    CRITICALITY_B_DEFAULT_RATE_INR: int = 18000
    CRITICALITY_C_DEFAULT_RATE_INR: int = 5000

    # ── Authoritative procurement approval tiers ──
    PROCUREMENT_AUTO_MAX_INR: int = 200000
    PROCUREMENT_MANAGER_MAX_INR: int = 1000000
    # Values > 1,000,000 INR require plant_head

    # ── Retry / circuit breaker ──
    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY_SECONDS: float = 1.0
    RETRY_MAX_DELAY_SECONDS: float = 30.0
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS: int = 60
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = 3

    # ── Workflow limits ──
    WORKFLOW_MAX_ITERATIONS: int = 25
    WORKFLOW_RECURSION_LIMIT: int = 50

    # ── Fixed reference date ──
    REFERENCE_DATE: str = "2026-08-01"

    # ── Feature flags ──
    USE_MOCK_SERVICES: bool = True
    ENABLE_FALLBACK: bool = False  # Disabled by default; fallback must be explicitly opted into and observable

    model_config = {
        "env_prefix": "PLANTGUARD_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:
        if self.DATA_DIR is None:
            self.DATA_DIR = self.PROJECT_ROOT / "data" / "plantguard"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached singleton Settings instance."""
    return Settings()
