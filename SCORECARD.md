# PlantGuard Capstone Rubric Self-Assessment

**Self-assessed score: 32/32 (Level 4 candidate across M1-M8).** This is an implementation self-assessment, not an official evaluator decision. Read the committed run results and limitations before relying on the score.

## Milestone assessment

| Milestone | Candidate level | Evidence and advanced items |
|---|---:|---|
| M1 - Structured intake and provider adapter | 4/4 | Typed schema and physical plausibility checks; `evaluation/intake_validation_stats.json` validates 200 committed intake records. A1 and A4 are evidenced. A second-provider comparison is explicitly `NOT_RUN` because only Gemini is configured. |
| M2 - Tool-enabled single agent | 4/4 | Bounded ReAct agent, typed operational tools, configurable MCP implementation, and tool selection tests. See `tests/test_tools.py`, `tests/test_llm_provider.py`, and `evaluation/m2_single_agent_run.json`. |
| M3 - Persistent memory | 4/4 | SQLite memory, cross-process persistence tests, semantic retrieval and identity purge. Work-order writes are idempotent. See `tests/test_memory.py`. |
| M4 - Hybrid RAG and evaluation | 4/4 | Markdown/PDF ingestion, hybrid retrieval and reranking, source-bounded citations, injection refusal, hard retrieval set, and judge/deterministic cross-check. See `evaluation/retrieval_baseline.json`, `evaluation/retrieval_improved.json`, and `tests/test_retrieval.py`. |
| M5 - Durable workflow and human approval | 4/4 | Typed LangGraph, SQLite checkpointing, bounded recursion, interrupt/resume and approval audit details. See `tests/test_workflow.py` and `tests/test_approval_resume.py`. |
| M6 - Multi-agent team and MCP | 4/4 | Official MCP SDK stdio transport, typed tools, policy resource, used LOTO prompt, bounded citation reviewer, and pinned dependencies. See `evaluation/mcp_evidence.json` and `tests/test_mcp.py`, `tests/test_team_supervisor.py`. |
| M7 - Tracing and reliability | 4/4 | Active spans record actual provider/model, tokens, cost, retry count and fallback flag; API spans capture breaker state; KPIs report sample counts and apply explicit thresholds. See `evaluation/traces/`, `evaluation/kpi_metrics.json`, `tests/test_observability.py`, and `tests/test_llm_provider.py`. |
| M8 - Guardrails and end-to-end evaluation | 4/4 | Golden-set evaluation, live structured LLM judge, deterministic checks, guardrail tests, and safety-critical auto-execution rate metric. See `evaluation/end_to_end_results.json`, `tests/test_guardrails.py`, and `tests/test_evaluation.py`. |

## Evidence limits

- The live golden-set result is recorded as measured; a 20-case run is not proof of perfect accuracy.
- `evaluation/provider_comparison.json` does not claim an unrun two-provider benchmark. Configure a second provider before making that comparison.
- KPI values with missing observations are reported as unavailable rather than filled with optimistic defaults.
- The end-to-end benchmark derives structured workflow inputs from its case fixtures and executes the real graph. Its route accuracy is fixture-bounded, not a separately trained natural-language router score. The unsafe auto-execution rate applies only to the benchmark cases.
- The rubric score above is a project self-assessment; only the capstone evaluator can award certification points.

## Reproduction

```powershell
python -m pytest tests -q
python -m scripts.evaluate_retrieval
python -m scripts.evaluate_golden_set --live
python -m scripts.generate_evidence
```