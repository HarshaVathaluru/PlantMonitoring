# PlantGuard: Implementation Roadmap & Execution Sequence

## 1. Sequence Overview
Execution proceeds sequentially across Phases 0 to 7 to guarantee full traceability, reproducible evaluation evidence, and zero regressions.

```
Phase 0: Workspace Audit & Technical Specs (Complete)
  │
Phase 1: Data Engineering Foundation (Assets A, B, C, D & Manifest)
  │
Phase 2: Milestone 1 (LLM Adapter & Intake) & Milestone 2 (Tool-Enabled Single Agent)
  │
Phase 3: Milestone 3 (Persistent Memory) & Milestone 4 (Production RAG & Evaluation Baseline)
  │
Phase 4: Milestone 5 (LangGraph Workflow & Checkpointing) & Milestone 6 (Multi-Agent Team & MCP)
  │
Phase 5: Milestone 7 (Observability & Reliability Hardening)
  │
Phase 6: Milestone 8 (Safety Guardrails, End-to-End Evaluation & FastAPI/Dashboard Deployment)
  │
Phase 7: Full System Verification, Test Suite Execution & Evidence Generation
```

---

## 2. Milestone Deliverables & Acceptance Criteria

### Milestone 1: Provider-Agnostic LLM Adapter & Structured Intake
- Implement `app/config/settings.py` with Pydantic BaseSettings.
- Implement `app/adapters/llm_adapter.py` supporting Gemini and OpenAI-compatible endpoints with bounded repair.
- Implement `app/schemas/maintenance_event.py` with rigorous Pydantic validation, enums, cross-field checks.
- Deliverable tests: `tests/test_intake.py`, `tests/test_llm_provider.py`.
- Level 4 Advanced Criteria targeted: M1.A1 (Cross-field validation), M1.A3 (Typed outputs across router & reviewer).

### Milestone 2: Tool-Enabled Single Agent
- Implement 4 deterministic tools grounded in the 14 mock API tables:
  1. `get_sensor_history(asset_tag, hours)`
  2. `calculate_downtime_cost(asset_tag, downtime_minutes)`
  3. `check_spare_parts_inventory(part_number)`
  4. `schedule_technician(required_skill, estimated_hours, date, shift)`
- Implement single-agent loop with recursion limits, structured parameter validation, and zero `eval()` execution.
- Deliverable tests: `tests/test_tools.py`.
- Level 4 Advanced Criteria targeted: M2.A1 (Retry/circuit breaker logging), M2.A4 (Unit tests for tool selection/errors).

### Milestone 3: Persistent Memory & Semantic Index
- Implement SQLite-backed persistent memory `app/memory/persistent_memory.py` capturing stable asset facts, past work orders, and SOP procedures.
- Namespacing and session isolation to prevent cross-tenant/cross-asset leakage.
- Explicit update/supersession policy with audit trail.
- Survive complete process termination and restart (verifiable via test).
- Deliverable tests: `tests/test_memory.py` executing tests T1 through T9.
- Level 4 Advanced Criteria targeted: M3.A2 (Explicit update/supersession policy), M3.A3 (Relevance & token budget filtering).

### Milestone 4: Production RAG & Evaluation Baseline
- Chunking, metadata tagging, and indexing of ~13 equipment manuals and SOPs into Qdrant.
- Implement hybrid retrieval combining dense vector similarity with BM25 keyword matching and reciprocal rank fusion.
- Implement Cross-Encoder reranking to guarantee high-precision context ordering.
- Commit initial retrieval golden set (10+ questions) with baseline metrics, followed by improved metrics.
- Deliverable tests: `tests/test_retrieval.py`.
- Level 4 Advanced Criteria targeted: M4.A2 (Groundedness scorer with deterministic checks), M4.A4 (Hard cases with near-duplicates and unanswerable questions).

### Milestone 5: LangGraph Workflow & Checkpointing
- Build `StateGraph` with explicit typed state, deterministic node transitions, and conditional routing.
- Integrate SQLite durable checkpointer for pause-restart-resume.
- Implement human-approval interrupt node for safety-critical recommendations.
- Guarantee that irreversible side effects (work order issuance, dispatch, PO placement) occur strictly once post-approval.
- Deliverable tests: `tests/test_workflow.py`, `tests/test_approval_resume.py`.
- Level 4 Advanced Criteria targeted: M5.A1 (Approval audit trail), M5.A3 (Unit tests for graph nodes and routing logic).

### Milestone 6: Multi-Agent Team & Model Context Protocol (MCP)
- Coordinate 5 agents: Log Intake, Manual RAG, Maintenance Recommender, Procurement, and Safety Reviewer.
- Develop FastMCP server in `app/mcp/server.py` exposing inventory tools and read-only policy resources.
- Develop MCP client in `app/mcp/client.py` and bind to Procurement Agent.
- Deliverable tests: `tests/test_agents.py`, `tests/test_mcp.py`.
- Level 4 Advanced Criteria targeted: M6.A1 (MCP prompt template usage), M6.A2 (Server hardening, strict stdio logging to stderr).

### Milestone 7: Observability & Reliability Hardening
- Implement Langfuse / structured span tracing with token counts, latency, and cost calculations.
- Implement Circuit Breaker (`CLOSED`, `OPEN`, `HALF_OPEN`) with configurable failure thresholds.
- Seeded failure-injection test harness measuring reliability before and after hardening.
- Deliverable tests: `tests/test_observability.py`.
- Level 4 Advanced Criteria targeted: M7.A1 (Retry count and breaker state tracing), M7.A3 (Secondary LLM provider fallback).

### Milestone 8: Safety Guardrails, End-to-End Evaluation & FastAPI Deployment
- Build Safety Policy Engine (`app/safety/policy_engine.py`) enforcing hard blocks on unapproved safety-critical actions.
- Execute 20+ end-to-end evaluation scenarios (including probes P1–P5).
- Expose complete FastAPI service with `/health`, `/api/v1/intake`, `/api/v1/workflow`, `/api/v1/approval`, and `/dashboard`.
- Deliverable tests: `tests/test_guardrails.py`, `tests/test_api_validation.py`, `tests/test_evaluation.py`.
- Level 4 Advanced Criteria targeted: M8.A2 (Automated pytest suite for guardrails), M8.A3 (Zero unsafe auto-execution rate verification).
