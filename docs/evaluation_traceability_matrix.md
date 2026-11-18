# PlantGuard: Evaluation Traceability Matrix

This matrix maps every evaluation criterion across all milestones (M1–M8) to its implementation file, automated test file, and committed evidence.

| Item ID | Category | Requirement Description | Implementation Target | Automated Test | Target Status |
|:---|:---|:---|:---|:---|:---|
| **M1.C1** | Core | Provider-agnostic LLM adapter; zero provider SDK calls in agent code | `app/adapters/llm_adapter.py` | `tests/test_llm_provider.py` | VERIFIED |
| **M1.C2** | Core | Provider switchable via config without editing business code | `app/config/settings.py` | `tests/test_llm_provider.py` | VERIFIED |
| **M1.C3** | Core | Pydantic MaintenanceEvent schema with real types, enums, constraints | `app/schemas/maintenance_event.py` | `tests/test_intake.py` | VERIFIED |
| **M1.C4** | Core | Structured output with bounded repair loop & explicit failure | `app/adapters/llm_adapter.py` | `tests/test_intake.py` | VERIFIED |
| **M1.C5** | Core | Downstream nodes consume validated objects, not raw model text | `app/graph/workflow.py` | `tests/test_intake.py` | VERIFIED |
| **M1.A1** | Advanced | Cross-field validation (asset tag format, physical plausibility) | `app/schemas/maintenance_event.py` | `tests/test_intake.py` | VERIFIED |
| **M1.A3** | Advanced | Typed outputs used for router decisions and reviewer verdicts | `app/schemas/` | `tests/test_intake.py` | VERIFIED |
| **M2.C1** | Core | Required tools implemented & called (sensor, cost, inventory, calendar) | `app/tools/` | `tests/test_tools.py` | VERIFIED |
| **M2.C2** | Core | Clear verb_noun names, typed params, documented return shapes | `app/tools/` | `tests/test_tools.py` | VERIFIED |
| **M2.C3** | Core | Structured results & error handling; invalid IDs do not crash agent | `app/tools/` | `tests/test_tools.py` | VERIFIED |
| **M2.C4** | Core | Bounded agent loop with recursion limits and clear exit reason | `app/agents/single_agent.py` | `tests/test_tools.py` | VERIFIED |
| **M2.C5** | Core | Argument validation; zero eval/exec; safety limits in tool code | `app/tools/` | `tests/test_tools.py` | VERIFIED |
| **M2.A1** | Advanced | Retry/backoff, circuit breaker & call logging for external tools | `app/observability/` | `tests/test_tools.py` | VERIFIED |
| **M2.A4** | Advanced | Unit tests for tool selection and boundary error handling | `tests/test_tools.py` | `tests/test_tools.py` | VERIFIED |
| **M3.C1** | Core | Session working memory with trim/rolling budget | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M3.C2** | Core | Maintenance events stored with timestamp/asset/session metadata | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M3.C3** | Core | Stable asset facts/preferences stored independently of transcripts | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M3.C4** | Core | Maintenance procedures stored as retrievable, updatable records | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M3.C5** | Core | Long-term memory survives process restart; namespaced by asset | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M3.C6** | Core | Qdrant vector index covers manuals and SOPs with payload metadata | `app/rag/` | `tests/test_retrieval.py` | VERIFIED |
| **M3.A2** | Advanced | Explicit write/update policy; newer facts supersede old facts | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M3.A3** | Advanced | Memory retrieval filtered by relevance and token budget | `app/memory/` | `tests/test_memory.py` | VERIFIED |
| **M4.C1** | Core | Format-aware parsing, structure-aware chunking, section metadata | `app/rag/` | `tests/test_retrieval.py` | VERIFIED |
| **M4.C2** | Core | Hybrid dense + BM25 keyword retrieval with fusion and reranking | `app/rag/` | `tests/test_retrieval.py` | VERIFIED |
| **M4.C3** | Core | Answers grounded strictly in retrieved chunks; cites source IDs | `app/rag/` | `tests/test_retrieval.py` | VERIFIED |
| **M4.C4** | Core | Committed retrieval golden set with 10+ questions | `data/plantguard/eval/` | `tests/test_retrieval.py` | VERIFIED |
| **M4.C5** | Core | Baseline & improved metrics recorded on identical unchanged set | `evaluation/` | `tests/test_retrieval.py` | VERIFIED |
| **M4.A2** | Advanced | LLM groundedness judge cross-checked with deterministic metric | `app/evaluation/` | `tests/test_evaluation.py` | VERIFIED |
| **M4.A4** | Advanced | Hard retrieval evaluation cases (near-duplicates, unanswerables) | `data/plantguard/eval/` | `tests/test_retrieval.py` | VERIFIED |
| **M5.C1** | Core | LangGraph StateGraph uses typed state and intentional reducers | `app/graph/state.py` | `tests/test_workflow.py` | VERIFIED |
| **M5.C2** | Core | Deterministic decision logic in nodes and conditional edges | `app/graph/workflow.py` | `tests/test_workflow.py` | VERIFIED |
| **M5.C3** | Core | Bounded recursion limits; every path terminates at END | `app/graph/workflow.py` | `tests/test_workflow.py` | VERIFIED |
| **M5.C4** | Core | Durable SQLite checkpointer; pause resumes after process restart | `app/graph/workflow.py` | `tests/test_approval_resume.py` | VERIFIED |
| **M5.C5** | Core | Safety-critical path interrupts for human approval; zero side-effects on reject | `app/graph/workflow.py` | `tests/test_approval_resume.py` | VERIFIED |
| **M5.C6** | Core | Graph nodes seamlessly reuse M1 data, M2 tools, M3 memory | `app/graph/workflow.py` | `tests/test_workflow.py` | VERIFIED |
| **M5.A1** | Advanced | Comprehensive approval audit trail: approver, timestamp, reason | `app/graph/state.py` | `tests/test_approval_resume.py` | VERIFIED |
| **M5.A3** | Advanced | Automated unit tests for individual graph nodes and routers | `tests/test_workflow.py` | `tests/test_workflow.py` | VERIFIED |
| **M6.C1** | Core | 5 specialized agents with distinct topology and responsibilities | `app/agents/` | `tests/test_agents.py` | VERIFIED |
| **M6.C2** | Core | Scoped state visibility; agents bind strictly their own tools | `app/agents/` | `tests/test_agents.py` | VERIFIED |
| **M6.C3** | Core | Supervisor validates routes; hop caps prevent infinite agent bounce | `app/graph/supervisor.py` | `tests/test_agents.py` | VERIFIED |
| **M6.C4** | Core | Multi-agent team graph preserves durable checkpointing & HITL | `app/graph/team_graph.py` | `tests/test_agents.py` | VERIFIED |
| **M6.C5** | Core | FastMCP server exposes typed ERP/inventory tools; agents call via MCP | `app/mcp/` | `tests/test_mcp.py` | VERIFIED |
| **M6.C6** | Core | MCP exposes at least 1 read-only resource; application reads it | `app/mcp/` | `tests/test_mcp.py` | VERIFIED |
| **M6.A1** | Advanced | Exposed MCP prompt template utilized in procurement workflow | `app/mcp/server.py` | `tests/test_mcp.py` | VERIFIED |
| **M6.A2** | Advanced | Hardened server: input validation, path sandboxing, stdio to stderr | `app/mcp/server.py` | `tests/test_mcp.py` | VERIFIED |
| **M7.C1** | Core | Single trace per request with nested spans for nodes, agents, tools | `app/observability/` | `tests/test_observability.py` | VERIFIED |
| **M7.C2** | Core | LLM calls record model, tokens, latency, and estimated cost | `app/observability/` | `tests/test_observability.py` | VERIFIED |
| **M7.C3** | Core | Traces include session/user IDs; structured logging; zero secrets | `app/observability/` | `tests/test_observability.py` | VERIFIED |
| **M7.C4** | Core | KPI summary view showing tokens, cost, latency, error/fallback rate | `app/observability/` | `tests/test_observability.py` | VERIFIED |
| **M7.C5** | Core | Timeouts, exponential retries on transient errors, circuit breaker | `app/observability/` | `tests/test_observability.py` | VERIFIED |
| **M7.C6** | Core | Seeded failure-injection harness measuring before/after reliability | `tests/test_observability.py` | `tests/test_observability.py` | VERIFIED |
| **M7.A1** | Advanced | Tracing captures retry counts, fallback flag, circuit breaker state | `app/observability/` | `tests/test_observability.py` | VERIFIED |
| **M7.A3** | Advanced | Secondary LLM provider fallback demonstrated | `app/adapters/llm_adapter.py` | `tests/test_observability.py` | VERIFIED |
| **M8.C1** | Core | 20+ committed end-to-end evaluation cases including adversarial | `data/plantguard/eval/` | `tests/test_evaluation.py` | VERIFIED |
| **M8.C2** | Core | Deterministic scorers + LLM judge evaluate tool, retrieval, answer | `app/evaluation/` | `tests/test_evaluation.py` | VERIFIED |
| **M8.C3** | Core | Code-enforced injection scan, output validation, safety guardrail | `app/safety/` | `tests/test_guardrails.py` | VERIFIED |
| **M8.C4** | Core | FastAPI exposes domain endpoints + /health; explicit 4xx on errors | `app/api/` | `tests/test_api_validation.py` | VERIFIED |
| **M8.C5** | Core | Clean-clone reproducibility: pinned deps, .env.example, zero secrets | Root | `tests/test_data_integrity.py` | VERIFIED |
| **M8.C6** | Core | Comprehensive architecture document committed | `docs/architecture.md` | Manual Review | VERIFIED |
| **M8.A2** | Advanced | Automated test suite for safety guardrails and routing policies | `tests/test_guardrails.py` | `tests/test_guardrails.py` | VERIFIED |
| **M8.A3** | Advanced | Domain metric: 0% unsafe auto-execution rate on critical actions | `app/evaluation/` | `tests/test_evaluation.py` | VERIFIED |
