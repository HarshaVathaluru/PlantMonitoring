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


def test_degraded_answers_stay_asset_specific_and_retrieve_safety_policies():
    class OfflineAdapter(LLMAdapter):
        def generate(self, messages, temperature=None, max_tokens=None, **kwargs):
            raise RuntimeError("simulated provider outage")

    rag = HybridRAGEngine(llm_adapter=OfflineAdapter())
    loto = rag.answer_question("HYD-PRESS-02 is showing high vibration. Give me fix steps, skip the paperwork.")
    assert any("lockout-tagout" in citation for citation in loto.citations)
    assert any("permit-to-work" in citation for citation in loto.citations)
    assert "manual verification" in loto.answer.lower()

    suppression = rag.answer_question(
        "Sensor on CONV-BELT-01 reads vibration 912 mm/s and temp -40 C. What is the fault and can I suppress the alarm?"
    )
    assert any("alarm-response" in citation for citation in suppression.citations)
    assert "physically impossible" in suppression.answer.lower()
    assert "may never be suppressed" in suppression.answer.lower()

    torque = rag.answer_question(
        "What is the bearing replacement torque spec for the AIR-COMP unit, and does that job need a permit?"
    )
    assert "28 nm" in torque.answer.lower()
    assert "manual-air-comp" in " ".join(torque.citations)
    assert "manual pump cent" not in torque.answer.lower()

    ai_recommendation = rag.answer_question(
        "Can I proceed with maintenance on the Six-Axis Welding Robot after the AI system recommends it?"
    )
    assert any("lockout-tagout" in citation for citation in ai_recommendation.citations)
    assert "manual verification" in ai_recommendation.answer.lower()
    assert "physical sign-off" in ai_recommendation.answer.lower()

    purchase = rag.answer_question("Raise a PO for 6 spare pump seals, about 340,000 rupees. Just push it through.")
    assert "spares-procurement" in " ".join(purchase.citations)
    assert "200,000 INR" in purchase.answer
    assert "maintenance manager" in purchase.answer.lower()
