# PlantGuard: Architectural & Technical Decision Records (ADRs)

## ADR-001: Centralized Configuration via Pydantic BaseSettings
- **Context**: The project spans multiple modules (agents, tools, routers, guardrails, API). Hardcoding URLs, thresholds, or API keys anywhere leads to inconsistencies, security vulnerabilities, and breaks evaluation criteria H2/H4.
- **Decision**: All settings reside in `app/config/settings.py` inheriting from `pydantic_settings.BaseSettings` with environment prefix `PLANTGUARD_`. Shared safety thresholds (e.g., max vibration, temp bounds, PO tiers) have exactly one authoritative definition.
- **Consequences**: Zero duplicate configuration; fully configurable via environment variables and `.env`.

## ADR-002: Provider-Agnostic LLM Adapter with Bounded Repair Loop
- **Context**: M1 requires switching LLM providers without altering application code. Raw model outputs frequently suffer from malformed JSON or schema deviations.
- **Decision**: An abstract `BaseLLMProvider` interface wraps Google Gemini, OpenAI-compatible APIs, and Ollama. The `LLMAdapter` layer enforces a bounded repair loop (up to 3 attempts with validation error feedback). If repair fails, an explicit typed exception is raised rather than crashing silently.
- **Consequences**: Business logic never imports `google.generativeai` or `openai` directly. Switching providers requires changing only `PLANTGUARD_LLM_PROVIDER`.

## ADR-003: Deterministic Code-Level Safety vs. LLM-Prompted Safety
- **Context**: In safety-critical manufacturing, prompt instructions like "do not execute without approval" can be bypassed via adversarial injection (probes P1, P2) or hallucination.
- **Decision**: Safety policies are implemented as pure Python deterministic logic in `app/safety/policy_engine.py` and LangGraph conditional edge routers. An LLM's opinion cannot override physical plausibility rules, permit requirements, or financial sign-off thresholds.
- **Consequences**: Critical actions are structurally quarantined. If `safety_critical == True`, the LangGraph execution unconditionally interrupts for human review.

## ADR-004: Durable SQLite-Backed Checkpointing for LangGraph
- **Context**: M5 and M6 mandate that paused workflows must survive complete application termination and resume seamlessly using the identical `thread_id`. `InMemorySaver` fails this requirement completely.
- **Decision**: Use `SqliteSaver` pointing to a local database (`plantguard_checkpoints.db`). Checkpoints capture full workflow state before human approval pauses.
- **Consequences**: Evaluator pause-kill-restart-resume tests pass cleanly. Side effects execute exactly once after resume.

## ADR-005: Model Context Protocol (MCP) for Supply Chain & Inventory State
- **Context**: M6 requires agents to interface with external mock ERP/inventory systems through real MCP client-server calls, not local Python module imports.
- **Decision**: Implement a FastMCP server running over stdio/SSE exposing typed inventory query tools, order simulation tools, and policy resources (`plantguard://policies/*`). The Procurement Agent interacts exclusively through the MCP client interface. All diagnostic and operational logs from the stdio MCP server are routed strictly to `stderr` to prevent JSON-RPC protocol corruption.
- **Consequences**: Clean decoupled architecture matching production enterprise systems. Full compliance with M6.C5 and M6.C6.

## ADR-006: Hybrid RAG with Reciprocal Rank Fusion & Cross-Encoder Reranking
- **Context**: Manufacturing equipment manuals contain exact part numbers, torque specifications, and alarm setpoints. Pure semantic vector search frequently misses exact part codes or confuses near-duplicate asset classes.
- **Decision**: Combine Qdrant dense vector embeddings (using SentenceTransformers or compatible embeddings) with BM25 keyword matching via Reciprocal Rank Fusion (RRF). Top candidates are re-ordered using a Cross-Encoder reranker prior to context injection.
- **Consequences**: High precision on exact part IDs (`VPW-P-00123`), strong resistance to near-duplicate manual confusion, and provable groundedness.
