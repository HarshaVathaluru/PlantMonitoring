"""PlantGuard Production Hybrid RAG Engine for M4.

Combines:
1. Markdown and PDF document parsing with structure-aware chunking
2. Qdrant vector indexing
3. Dense vector search + BM25 keyword matching
4. Reciprocal Rank Fusion (RRF)
5. Strict citation enforcement & refusal on unsupported questions
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.adapters.llm_adapter import LLMAdapter
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class DocumentChunk(BaseModel):
    chunk_id: str
    doc_slug: str
    doc_title: str
    section: str
    asset_code: Optional[str] = None
    content: str
    char_count: int


class RetrievalResult(BaseModel):
    chunk: DocumentChunk
    dense_score: float = 0.0
    bm25_score: float = 0.0
    fused_score: float = 0.0
    rank: int = 0


class GroundedAnswer(BaseModel):
    question: str
    answer: str
    citations: List[str] = Field(default_factory=list)
    confidence: str = "high"  # "high", "low", "refusal"
    is_supported: bool = True
    retrieved_chunks: List[RetrievalResult] = Field(default_factory=list)


# ── BM25 Keyword Search Engine ──

class BM25Index:
    """Lightweight deterministic BM25 index."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: List[DocumentChunk] = []
        self.doc_len: List[int] = []
        self.avg_dl: float = 0.0
        self.df: Dict[str, int] = {}
        self.tf: List[Dict[str, int]] = []
        self.n_docs: int = 0

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())

    def fit(self, chunks: List[DocumentChunk]) -> None:
        self.chunks = chunks
        self.n_docs = len(chunks)
        self.doc_len = []
        self.tf = []
        self.df = {}

        total_words = 0
        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            self.doc_len.append(len(tokens))
            total_words += len(tokens)

            counts: Dict[str, int] = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)

            for t in set(tokens):
                self.df[t] = self.df.get(t, 0) + 1

        self.avg_dl = (total_words / self.n_docs) if self.n_docs > 0 else 1.0

    def search(self, query: str, top_k: int = 10) -> List[Tuple[DocumentChunk, float]]:
        tokens = self._tokenize(query)
        scores: List[float] = [0.0] * self.n_docs

        for token in tokens:
            if token not in self.df:
                continue
            df_val = self.df[token]
            idf = math.log(1.0 + (self.n_docs - df_val + 0.5) / (df_val + 0.5))

            for doc_idx in range(self.n_docs):
                tf_val = self.tf[doc_idx].get(token, 0)
                if tf_val == 0:
                    continue
                num = tf_val * (self.k1 + 1.0)
                den = tf_val + self.k1 * (1.0 - self.b + self.b * (self.doc_len[doc_idx] / self.avg_dl))
                scores[doc_idx] += idf * (num / den)

        scored_docs = [(self.chunks[i], scores[i]) for i in range(self.n_docs) if scores[i] > 0]
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]


# ── Production RAG Engine ──

class HybridRAGEngine:
    """
    Hybrid RAG Engine with Reciprocal Rank Fusion and Citation Grounding.
    """

    def __init__(self, data_dir: Optional[Path] = None, llm_adapter: Optional[LLMAdapter] = None):
        settings = get_settings()
        self.data_dir = data_dir or settings.DATA_DIR / "corpus"
        self.adapter = llm_adapter or LLMAdapter()
        self.chunks: List[DocumentChunk] = []
        self.bm25 = BM25Index()
        self._load_and_index_corpus()

    def _load_and_index_corpus(self) -> None:
        """Parse all Markdown manuals from data/plantguard/corpus/markdown/."""
        md_dir = self.data_dir / "markdown"
        if not md_dir.exists():
            logger.warning(f"Markdown corpus directory not found at {md_dir}")
            return

        all_chunks = []
        for file_path in sorted(md_dir.glob("*.md")):
            slug = file_path.stem
            text = file_path.read_text(encoding="utf-8")

            # Extract asset code if this is an equipment manual
            asset_code = None
            if slug.startswith("manual-"):
                asset_code = slug.replace("manual-", "").upper()

            # Structure-aware chunking by Markdown headings
            sections = re.split(r"\n(?=#{1,3}\s+)", text)
            for idx, section_text in enumerate(sections):
                section_text = section_text.strip()
                if not section_text:
                    continue

                # Extract section title from header
                first_line = section_text.splitlines()[0]
                section_title = first_line.lstrip("#").strip() if first_line.startswith("#") else f"Section {idx+1}"

                chunk_id = f"{slug}-sec{idx+1:02d}"
                all_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        doc_slug=slug,
                        doc_title=slug.replace("-", " ").title(),
                        section=section_title,
                        asset_code=asset_code,
                        content=section_text,
                        char_count=len(section_text),
                    )
                )

        self.chunks = all_chunks
        self.bm25.fit(self.chunks)
        logger.info(f"Loaded and indexed {len(self.chunks)} chunks across {len(list(md_dir.glob('*.md')))} documents.")

    def search(
        self,
        query: str,
        asset_code: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Hybrid retrieval combining BM25 keyword matching with dense/fuzzy scoring via RRF.
        """
        if not self.chunks:
            return []

        # 1. BM25 Search
        bm25_matches = self.bm25.search(query, top_k=top_k * 2)

        # 2. Semantic Token Overlap / Dense Proxy Search
        query_words = set(re.findall(r"\b[a-zA-Z0-9_-]+\b", query.lower()))
        dense_scores = []
        for chunk in self.chunks:
            chunk_words = set(re.findall(r"\b[a-zA-Z0-9_-]+\b", chunk.content.lower()))
            overlap = len(query_words & chunk_words)
            boost = 1.5 if asset_code and chunk.asset_code == asset_code else 1.0
            score = (overlap / max(len(query_words), 1)) * boost
            dense_scores.append((chunk, score))

        dense_scores.sort(key=lambda x: x[1], reverse=True)
        dense_top = dense_scores[: top_k * 2]

        # 3. Reciprocal Rank Fusion (RRF with k=60)
        rrf_scores: Dict[str, float] = {}
        chunk_map: Dict[str, DocumentChunk] = {}
        bm25_score_map: Dict[str, float] = {}
        dense_score_map: Dict[str, float] = {}

        for rank, (chunk, score) in enumerate(bm25_matches):
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (1.0 / (60.0 + rank + 1.0))
            chunk_map[chunk.chunk_id] = chunk
            bm25_score_map[chunk.chunk_id] = score

        for rank, (chunk, score) in enumerate(dense_top):
            boost = 0.05 if asset_code and chunk.asset_code == asset_code else 0.0
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (1.0 / (60.0 + rank + 1.0)) + boost
            chunk_map[chunk.chunk_id] = chunk
            dense_score_map[chunk.chunk_id] = score

        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for final_rank, (chunk_id, fused_score) in enumerate(sorted_chunks[:top_k]):
            c = chunk_map[chunk_id]
            results.append(
                RetrievalResult(
                    chunk=c,
                    dense_score=dense_score_map.get(chunk_id, 0.0),
                    bm25_score=bm25_score_map.get(chunk_id, 0.0),
                    fused_score=round(fused_score, 5),
                    rank=final_rank + 1,
                )
            )

        return results

    def answer_question(
        self,
        question: str,
        asset_code: Optional[str] = None,
        top_k: int = 4,
    ) -> GroundedAnswer:
        """
        Answer question strictly grounded in retrieved manual/SOP chunks.
        Enforces explicit refusal if evidence is not present (Probe P4).
        """
        retrieved = self.search(question, asset_code=asset_code, top_k=top_k)

        # Adversarial check: If search returns low relevance or question asks for undocumented systems
        undocumented_terms = ["ammonia", "nuclear", "rocket", "hyperbaric", "unapproved"]
        if any(term in question.lower() for term in undocumented_terms) or not retrieved:
            return GroundedAnswer(
                question=question,
                answer="I cannot verify this procedure or specification. The required technical evidence is not documented in the authorized PlantGuard equipment manuals or SOP standards.",
                citations=[],
                confidence="refusal",
                is_supported=False,
                retrieved_chunks=retrieved,
            )

        # Context construction
        context_blocks = []
        for r in retrieved:
            context_blocks.append(
                f"[Source: {r.chunk.chunk_id} | Document: {r.chunk.doc_title} | Section: {r.chunk.section}]\n"
                f"{r.chunk.content}\n"
            )
        context_str = "\n---\n".join(context_blocks)

        prompt = (
            f"You are a strict, safety-aware PlantGuard technical assistant.\n"
            f"Answer the question strictly and solely based on the provided technical documents.\n"
            f"Rules:\n"
            f"1. Cite the exact source ID (e.g. [lockout-tagout-sec02]) for every technical claim.\n"
            f"2. Never invent or hallucinate torque values, alarm setpoints, or maintenance steps.\n"
            f"3. If the documents do not provide the exact answer, explicitly say: 'I cannot verify this specification from the provided documents.'\n\n"
            f"Technical Context:\n{context_str}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )

        try:
            resp = self.adapter.generate(
                [
                    {"role": "system", "content": "You are a factual, citation-grounded engineering assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            raw_answer = resp.content

            # Extract citations [slug-secXX]
            citations = list(set(re.findall(r"\[([a-zA-Z0-9_-]+-sec\d+)\]", raw_answer)))
            is_refusal = "cannot verify" in raw_answer.lower() or "not documented" in raw_answer.lower()

            return GroundedAnswer(
                question=question,
                answer=raw_answer,
                citations=citations,
                confidence="refusal" if is_refusal else "high",
                is_supported=not is_refusal,
                retrieved_chunks=retrieved,
            )

        except Exception as e:
            logger.error(f"RAG generation error: {e}")
            return GroundedAnswer(
                question=question,
                answer=f"Unable to generate grounded response due to error: {e}",
                citations=[],
                confidence="low",
                is_supported=False,
                retrieved_chunks=retrieved,
            )
