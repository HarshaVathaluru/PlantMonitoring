"""PlantGuard RAG Agent for Milestone 6.

Specialized agent responsible for retrieving authoritative maintenance procedures,
extracting exact citations, and refusing unsupported/undocumented queries.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.rag.engine import GroundedAnswer, HybridRAGEngine

logger = logging.getLogger(__name__)


class RAGAgent:
    """Specialized RAG Agent."""

    def __init__(self, rag_engine: Optional[HybridRAGEngine] = None):
        self.rag = rag_engine or HybridRAGEngine()

    def query_procedure(self, question: str, asset_code: Optional[str] = None) -> GroundedAnswer:
        """Query standard operating procedures and technical manuals."""
        logger.info(f"RAGAgent querying: '{question}' for asset {asset_code}")
        return self.rag.answer_question(question, asset_code=asset_code)
