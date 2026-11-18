"""Evaluation script comparing Baseline (BM25 only) vs Improved (Hybrid RRF).

Generates:
- evaluation/retrieval_baseline.json
- evaluation/retrieval_improved.json
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from app.rag.engine import HybridRAGEngine
from app.config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_evaluation():
    settings = get_settings()
    eval_set_path = settings.DATA_DIR / "eval" / "retrieval_golden_set.json"
    if not eval_set_path.exists():
        raise FileNotFoundError(f"Evaluation set not found at {eval_set_path}")

    with open(eval_set_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    rag = HybridRAGEngine()

    baseline_results = []
    improved_results = []

    for case in cases:
        query = case["query"]
        target_doc = case["target_doc"]
        asset_code = case.get("asset_code")

        # 1. Baseline: Pure BM25 without asset boost
        bm25_hits = rag.bm25.search(query, top_k=10)
        bm25_ranks = [i + 1 for i, (chunk, _) in enumerate(bm25_hits) if target_doc in chunk.doc_slug]
        bm25_hit_rank = bm25_ranks[0] if bm25_ranks else None
        bm25_rr = 1.0 / bm25_hit_rank if bm25_hit_rank else 0.0

        baseline_results.append({
            "id": case["id"],
            "query": query,
            "target_doc": target_doc,
            "hit_rank": bm25_hit_rank,
            "reciprocal_rank": bm25_rr,
            "hit_at_1": bm25_hit_rank == 1,
            "hit_at_3": bm25_hit_rank is not None and bm25_hit_rank <= 3,
            "hit_at_5": bm25_hit_rank is not None and bm25_hit_rank <= 5,
        })

        # 2. Improved: Hybrid RRF with asset code boost
        hybrid_hits = rag.search(query, asset_code=asset_code, top_k=10)
        hybrid_ranks = [i + 1 for i, r in enumerate(hybrid_hits) if target_doc in r.chunk.doc_slug]
        hybrid_hit_rank = hybrid_ranks[0] if hybrid_ranks else None
        hybrid_rr = 1.0 / hybrid_hit_rank if hybrid_hit_rank else 0.0

        improved_results.append({
            "id": case["id"],
            "query": query,
            "target_doc": target_doc,
            "hit_rank": hybrid_hit_rank,
            "reciprocal_rank": hybrid_rr,
            "hit_at_1": hybrid_hit_rank == 1,
            "hit_at_3": hybrid_hit_rank is not None and hybrid_hit_rank <= 3,
            "hit_at_5": hybrid_hit_rank is not None and hybrid_hit_rank <= 5,
        })

    def calc_metrics(res_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(res_list)
        mrr = sum(r["reciprocal_rank"] for r in res_list) / n
        h1 = sum(1 for r in res_list if r["hit_at_1"]) / n
        h3 = sum(1 for r in res_list if r["hit_at_3"]) / n
        h5 = sum(1 for r in res_list if r["hit_at_5"]) / n
        return {
            "total_queries": n,
            "mean_reciprocal_rank": round(mrr, 4),
            "hit_rate_at_1": round(h1, 4),
            "hit_rate_at_3": round(h3, 4),
            "hit_rate_at_5": round(h5, 4),
        }

    baseline_metrics = calc_metrics(baseline_results)
    improved_metrics = calc_metrics(improved_results)

    eval_dir = Path("evaluation")
    eval_dir.mkdir(parents=True, exist_ok=True)

    baseline_payload = {
        "engine": "BM25_Baseline",
        "description": "Standard keyword BM25 retrieval without dense hybrid fusion or metadata boosting",
        "metrics": baseline_metrics,
        "details": baseline_results,
    }
    with open(eval_dir / "retrieval_baseline.json", "w", encoding="utf-8") as f:
        json.dump(baseline_payload, f, indent=2)

    improved_payload = {
        "engine": "Hybrid_RRF_Dense_Reranked",
        "description": "Production Hybrid BM25 lexical + Dense multi-gram vector cosine similarity with Reciprocal Rank Fusion (k=60), Cross-Scoring Reranker, and equipment asset code boosting",
        "metrics": improved_metrics,
        "details": improved_results,
    }
    with open(eval_dir / "retrieval_improved.json", "w", encoding="utf-8") as f:
        json.dump(improved_payload, f, indent=2)

    print("\n--- RETRIEVAL EVALUATION RESULTS ---")
    print(f"Baseline (BM25):   MRR={baseline_metrics['mean_reciprocal_rank']} | Hit@1={baseline_metrics['hit_rate_at_1']} | Hit@3={baseline_metrics['hit_rate_at_3']}")
    print(f"Improved (Hybrid): MRR={improved_metrics['mean_reciprocal_rank']} | Hit@1={improved_metrics['hit_rate_at_1']} | Hit@3={improved_metrics['hit_rate_at_3']}")
    print("------------------------------------\n")


if __name__ == "__main__":
    run_evaluation()
