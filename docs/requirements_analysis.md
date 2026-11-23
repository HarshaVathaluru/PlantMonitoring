# PlantGuard: Comprehensive Requirements Analysis & Specification

## 1. Executive Summary & Programme Context
- **System**: PlantGuard — Production-Grade Predictive Maintenance & Supply Chain Operations Copilot.
- **Domain**: Discrete & Continuous Manufacturing, Supply Chain, Industrial Operations.
- **Target Evaluation Score**: 32/32 (Level 4 across all 8 milestones M1–M8, Distinction Band).
- **Core Principle**: Zero hardcoded application behavior, zero unapproved safety-critical execution, zero fabricated engineering parameters (torques, setpoints, procedures).

---

## 2. Source Documents & Precedence Hierarchy
1. `PlantGuard_Project_Blueprint_and_Data_Sourcing_Guide.docx` (Authoritative Blueprint & Milestone Structure)
2. `PlantGuard_Detailed_Data_Sourcing_and_Data_Quality_Guide.docx` (Authoritative Data Schema, Validation Rules & 14 Mock API Tables)
3. `PlantGuard_Capstone_Evaluation_and_Scoring_Guide.docx` (Authoritative Rubric, Evaluation Checklist, Scoring Levels 0–4 & Red Flags)
4. `PlantGuard_Antigravity_Master_Implementation_Prompt.pdf` (Execution Roadmap & Guardrails)

*Conflict Resolution*: In any discrepancy regarding data fields, table schemas, or counts, `PlantGuard_Detailed_Data_Sourcing_and_Data_Quality_Guide.docx` governs. In grading and evaluation criteria, `PlantGuard_Capstone_Evaluation_and_Scoring_Guide.docx` governs.

---

## 3. Four Core Data Assets Specification

### Asset A: Equipment Manuals & SOP Corpus (~13 Documents)
1. **Safety & Operational Standards**:
   - Lockout/Tagout (LOTO) Procedure (OSHA 1910.147 structural alignment)
   - Permit-to-Work (PTW) Standard (Hot Work, Confined Space, Work at Height, High Voltage, Pressure Systems)
   - Maintenance Planning Standard (Clause 2.1 Criticality Matrix A/B/C)
   - Spare-Parts Procurement Standard (Auto re-order <= ₹200k, Manager <= ₹1M, Plant Head > ₹1M)
   - Alarm Response & Escalation Protocol
2. **8 Asset Class Equipment Manuals** (genuinely distinct operating parameters, alarm trip thresholds, torque specs, PM intervals, 6+ named fault conditions):
   - `CNC-MILL` (CNC Milling Machine)
   - `HYD-PRESS` (Hydraulic Press)
   - `CONV-BELT` (Conveyor Belt System)
   - `AIR-COMP` (Industrial Air Compressor)
   - `IND-OVEN` (Industrial Curing Oven)
   - `PUMP-CENT` (Centrifugal Slurry/Water Pump)
   - `ROBOT-WELD` (Robotic Welding Cell)
   - `CHILLER` (Process Water Chiller)

### Asset B: Sensor Alerts & Operator Maintenance Logs
- Grounded in real industrial sensor distributions (AI4I 2020 predictive maintenance dataset + NASA C-MAPSS degradation curves).
- Telemetry degradation simulator with trend progression (healthy/faulty overlap, accelerating faults on ~1/5th assets).
- Prose layer: Dual machine-precise alerts + messy human operator logs ("funny noise near drive end").
- Contradictory cases, ambiguous reports, missing fields (approx 1 in 6 records missing required fields).
- Deliberately impossible readings: e.g., Vibration 912 mm/s RMS and Temp -40°C.
- Standard JSONL intake schema preserving `ground_truth` block for evaluation.

### Asset C: 14 Relational Mock API Tables (31,516 total rows, 120 columns)
Reference Date fixed at: **2026-08-01**.
1. `assets` (28 rows): Machines across Lines 1–4, asset_tag, asset_code, criticality A/B/C, running_hours, last_pm_on.
2. `asset_classes` (8 rows): Trip/warning limits for vibration, temperature, pressure, PM interval hours, energy sources.
3. `criticality_matrix` (3 rows): Class A (>=₹30k/hr, default ₹40k, 7d inspect), B (₹10k–₹29,999/hr, default ₹18k, 30d inspect), C (<₹10k/hr, default ₹5k, 90d inspect).
4. `asset_criticality` (28 rows): Asset-level safety risk, environmental impact, specific `downtime_cost_per_hour_inr`.
5. `telemetry` (20,160 rows): 720 hours (30 days) of vibration, temperature, current, seeded_fault.
6. `telemetry_pressure` (8,640 rows): 720 hours of pressure_bar for pressure-enabled classes.
7. `work_orders` (400 rows): Historical & active WOs (P1–P4, preventive, corrective, predictive, breakdown).
8. `work_order_details` (400 rows): Required skill, hours, permit_type, part_number, downtime_cost_inr.
9. `technicians` (40 rows): VPW-T-001 to VPW-T-040 across Mechanical, Electrical, Instrumentation, Hydraulics, Robotics; L1–L3, certifications.
10. `technician_calendar` (1,120 rows): 28 days x 40 techs; shifts A (06:00-14:00), B (14:00-22:00), C (22:00-06:00); on_shift/rest/leave, available_hours.
11. `inventory` (280 rows): Spare parts VPW-P-*, on_hand, reorder_point, unit_cost_inr, lead_time_days, supplier_tier.
12. `suppliers` (12 rows): VPW-SUP-001 to 012, T1/T2/T3, on-time delivery %, status.
13. `part_suppliers` (280 rows): Quotes, lead times, MOQ per part-supplier pair.
14. `purchase_orders` (117 rows): POs with status, raised_by, approval_tier, total_inr.

### Asset D: Golden Evaluation Dataset
- Minimum 10 retrieval evaluation questions with ground truth citations and expected answers.
- Minimum 20 end-to-end evaluation scenarios covering normal, ambiguous, contradictory, impossible readings, safety-critical actions.
- Standard Adversarial Probes:
  - P1: Direct prompt injection (bypass safety approval, skip sign-off).
  - P2: Indirect prompt injection (malicious payload embedded in logs or manuals).
  - P3: Domain safety & physical impossibility (extreme sensor values, production pressure to skip permits).
  - P4: Hallucination/Fabrication resistance (unsupported torque or undocumented skid procedures -> explicit refusal/verification request).
  - P5: Malformed API input / contract violations (clear 4xx responses, zero unhandled 500s).

---

## 4. Multi-Agent Roster (M6)
1. **Log Intake Agent**: Ingests unstructured alerts/logs, extracts entities, validates schemas via Pydantic, flags anomalies and contradictions.
2. **Manual / SOP RAG Agent**: Performs hybrid retrieval (dense + BM25/keyword) + reranking over manuals and SOPs, cites clauses, enforces refusal on missing data.
3. **Maintenance Recommendation Agent**: Correlates telemetry trends, downtime costs, technician qualifications, and SOP evidence into actionable plans.
4. **Procurement Agent**: Queries inventory via MCP, checks supplier tiers/lead times, drafts purchase orders adhering strictly to financial approval gates.
5. **Safety Reviewer Agent**: Evaluates risk level, validates LOTO/permit compliance, checks technician certifications, gates safety-critical operations behind human approvals.

---

## 5. Non-Negotiable Architectural Rules
- Central configuration using `pydantic-settings` (`Settings` class) consuming `.env` and environment variables.
- Provider-agnostic LLM Adapter: Switchable between Gemini, OpenAI-compatible, Ollama without touching business logic.
- Bounded repair loop: Max 3 attempts for structured output repair; explicit structured failure on termination.
- LangGraph orchestration with durable SQLite checkpointing and human-in-the-loop (HITL) interrupt on safety-critical actions.
- Side-effect idempotency: Irreversible actions (dispatch, PO creation) execute strictly once and only post-approval.
- Model Context Protocol (MCP): Real FastMCP client-server architecture serving inventory/ERP tools and read-only policy resources.
- Observability: Comprehensive tracing with token tracking, cost estimation, retry counts, fallback flags, and circuit breakers.
- FastAPI backend serving complete REST endpoints and status dashboard.
