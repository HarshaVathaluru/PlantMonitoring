"""Tests for Milestone 4: Hybrid RAG Engine, RRF, Citations, and Refusal."""
import pytest
from app.rag.engine import HybridRAGEngine, DocumentChunk
from app.adapters.llm_adapter import LLMAdapter, LLMResponse


class MockRAGAdapter(LLMAdapter):
    """Deterministic offline adapter for RAG testing."""
    def generate(self, messages, temperature=None, max_tokens=None, **kwargs) -> LLMResponse:
        user_msg = messages[-1]["content"] if messages else ""
        if "ammonia" in user_msg.lower() or "nuclear" in user_msg.lower():
            return LLMResponse(
                content="I cannot verify this specification from the provided documents.",
                model="mock-rag",
                provider="mock",
                total_tokens=120,
            )
        return LLMResponse(
            content="According to [manual-air-comp-sec01], the maximum operating pressure is 8.5 bar.",
            model="mock-rag",
            provider="mock",
            total_tokens=180,
        )


@pytest.fixture
def rag_engine():
    adapter = MockRAGAdapter()
    return HybridRAGEngine(llm_adapter=adapter)


def test_rag_corpus_loaded(rag_engine):
    """Test that all 13 documents were chunked and indexed."""
    assert len(rag_engine.chunks) > 20
    slugs = {chunk.doc_slug for chunk in rag_engine.chunks}
    assert "lockout-tagout" in slugs
    assert "permit-to-work" in slugs
    assert "spares-procurement" in slugs
    assert "manual-air-comp" in slugs
    assert "manual-hyd-press" in slugs


def test_hybrid_search_rrf_scoring(rag_engine):
    """Test that hybrid search returns results with RRF scores in descending order."""
    results = rag_engine.search("bearing replacement procedure torque", top_k=5)
    assert len(results) > 0
    assert len(results) <= 5
    for i in range(len(results) - 1):
        assert results[i].fused_score >= results[i + 1].fused_score
    assert all(r.chunk.chunk_id for r in results)


def test_asset_code_relevance_boost(rag_engine):
    """Test that providing an asset code boosts that asset's manual chunks."""
    results = rag_engine.search("operating temperature limit", asset_code="AIR-COMP", top_k=3)
    assert len(results) > 0
    top_chunk = results[0].chunk
    assert "air-comp" in top_chunk.doc_slug.lower()


def test_unsupported_question_refusal_probe_p4(rag_engine):
    """Probe P4: Verify that questions about unsupported/undocumented systems are strictly refused."""
    ans = rag_engine.answer_question("What is the purge cycle time for the ammonia refrigeration system?")
    assert ans.is_supported is False
    assert ans.confidence == "refusal"
    assert "cannot verify" in ans.answer.lower() or "not documented" in ans.answer.lower()


def test_grounded_answer_with_citations(rag_engine):
    """Test that grounded answers contain citation tags."""
    ans = rag_engine.answer_question("What is the operating pressure limit for the air compressor?")
    assert ans.is_supported is True
    assert len(ans.citations) > 0
    assert any("manual-air-comp" in c for c in ans.citations)
