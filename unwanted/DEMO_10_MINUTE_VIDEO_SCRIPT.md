# PlantGuard — 10-Minute Demo Video Script

**Target length:** 10:00
**Audience:** capstone evaluator, technical reviewer, or operations stakeholder
**Demo environment:** local PlantGuard service with synthetic project data
**Recording format:** 1920×1080, browser zoom 90–100%, microphone on

## Before recording

1. Start the API from the `plantguard` project folder in PowerShell:

   ```powershell
   $env:PYTHONPATH = (Get-Location).Path
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. Wait for startup to finish, then open `http://127.0.0.1:8000/dashboard`.
3. Close `.env`, terminals containing credentials, unrelated tabs, and notifications. Never show or read an API key on camera.
4. Keep the dashboard, project folder, and scorecard available. Use only the supplied synthetic sample values; do not approve real maintenance work from this demo.
5. The workflow and document search use the configured LLM provider. If a request is slow, narrate the safety or grounding step while it runs. If the provider is unavailable, use the saved evaluation results for the evidence segment and label them as the recorded run.

## Timed run of show

| Time | Segment | What to show |
|---|---|---|
| 0:00–0:40 | Opening | Dashboard landing view |
| 0:40–1:40 | Problem and design | Dashboard and project architecture |
| 1:40–2:40 | Live system status | Status cards and recent activity |
| 2:40–3:50 | Grounded knowledge search | Manuals & SOPs panel and citations |
| 3:50–4:50 | Impossible sensor readings | Assessment form, sensor fault block |
| 4:50–6:20 | Safety-gated assessment | Restored sample values, workflow pause |
| 6:20–7:20 | Human approval | Approval controls and completed result |
| 7:20–8:00 | Observability | Recent activity and request traces |
| 8:00–9:10 | Evaluation evidence | Golden-set JSON and scorecard |
| 9:10–10:00 | Wrap-up | Dashboard or scorecard summary |

## Script and on-screen cues

### 0:00–0:40 — Opening

**On screen:** Start on the dashboard at the top of the page. Pause briefly so the title, DEMO | SAMPLE DATA badge, and service status are readable.

**Say:**

> Hello, this is a ten-minute walkthrough of PlantGuard, a maintenance operations copilot for turning equipment alerts into documented, safety-reviewed maintenance workflows. I’ll show the live service status, search an approved procedure with citations, test a physically impossible sensor alert, and then run a high-risk case through its human approval checkpoint. The data used here is synthetic, and this local demo does not connect to a plant control system.

### 0:40–1:40 — Problem and design

**On screen:** Point to Overview, Maintenance assessment, and Manuals & SOPs. Briefly point out the How it works strip, then return to the assessment and search panels.

**Say:**

> Maintenance teams need more than an answer from a model. They need a response tied to equipment readings, approved instructions, and an auditable decision about whether work can proceed. PlantGuard combines typed alert intake, deterministic checks, hybrid manual retrieval, a stateful workflow, and a human approval gate. The dashboard labels the page as demo/sample data and explains the three steps: check an alert, review evidence, and record a decision. It keeps service health, assessment, and procedure search together. I’ll walk through each of those using the running application.

### 1:40–2:40 — Live system status

**On screen:** Show the API service, AI provider, provider protection, and recent request cards. Click the refresh icon. Point to the recent system activity panel if there are existing requests.

**Say:**

> The first row is populated from the service’s health and observability endpoints, rather than from fixed demonstration numbers. It shows whether the API is reachable, which model provider is configured, whether provider protection is active, and the number of recent requests. The activity list gives a quick view of saved API request records. This matters during an incident: an operator can see whether the application is available before using its recommendations. I can refresh the status without leaving the page.

### 2:40–3:50 — Grounded knowledge search

**On screen:** In “Search manuals and safety standards,” enter: `What must be verified before maintenance on a hydraulic press?` Select `HYD-PRESS`, then search. Wait for the answer and point out the citations and supported/unverified label.

**Say:**

> Next I’ll ask a question about the hydraulic press. I’ve selected the asset class so retrieval can focus on the relevant equipment and safety material. The response includes source identifiers from the PlantGuard corpus. The supported label and citation chips make it easier to inspect what the response relied on. If the requested procedure is not documented, the application is designed to say that it cannot verify it rather than invent a torque or maintenance step. The citation is a path back to the underlying approved document, not a substitute for following the complete procedure on site.

### 3:50–4:50 — Impossible sensor readings

**On screen:** In the assessment form, set vibration to `912` and temperature to `-40`, then run the assessment. Show the plausibility failure and the note that no workflow was started. Restore vibration to `7.8` and temperature to `82.5` afterward.

**Say:**

> Before a maintenance workflow can start, the form sends the readings through the intake plausibility check. Here I’m using an intentionally impossible combination: 912 millimeters per second vibration and minus 40 degrees Celsius. PlantGuard flags this as a likely sensor problem and holds the alert; it does not turn an invalid sensor reading into a repair diagnosis. Notice that the maintenance workflow was not started. I’ll restore the supplied sample readings for the next part of the demo.

### 4:50–6:20 — Safety-gated assessment

**On screen:** Confirm the restored values are vibration `7.8`, temperature `82.5`, severity `Critical`, LOTO checked, and Permit checked. Leave estimated parts cost at `0` unless you need to demonstrate a purchase threshold. Add a short operator note such as `Synthetic demo alert for hydraulic press`. Click **Run assessment**. Show the returned assessment, reason for review, procedure guidance/citations, and `WAITING FOR APPROVAL` state.

**Say:**

> This time the readings pass intake plausibility. The workflow runs through alert validation, equipment history, a root-cause assessment, document retrieval, and safety review. I’ve left the energy-isolation and permit flags on, and this sample is marked critical. Those conditions should pause the graph for human review. The result shows the workflow thread, the recommendation, and its approval reason. This pause is intentional: safety-critical work is not treated as approved simply because an automated recommendation exists. I’ll review the recorded details before taking the next step.

### 6:20–7:20 — Human approval and resume

**On screen:** In the approval section, choose the appropriate demo approver role. Enter: `Synthetic demonstration only; isolation and permit checks reviewed.` Click **Approve & resume**. Show the completed status and work order identifier if returned.

**Say:**

> The approval control records a human decision, role, and comment against this workflow thread. For this synthetic demonstration, I’m submitting a clearly labeled demo approval. The graph resumes from its checkpoint and reports the result. In a real deployment, the approving person would first verify the actual isolation, permit, asset condition, and site procedure. A dashboard click is not a replacement for those physical safety checks. A rejection is also available and stops execution without creating the work order.

### 7:20–8:00 — Observability

**On screen:** Show the recent activity list and refresh. If helpful, open `/api/v1/observability/traces` in a second tab briefly, then return to the dashboard.

**Say:**

> The request is recorded in the observability layer. PlantGuard captures workflow spans and operational metadata so reviewers can inspect what happened. The dashboard uses the trace endpoint for the recent activity view and the KPI endpoint for measured summaries. Values with no observations are reported as unavailable rather than filled with assumed performance numbers. This supports debugging and review after the operation.

### 8:00–9:10 — Evaluation evidence

**On screen:** Open `evaluation/end_to_end_results.json`. Show the summary section only. Then show `SCORECARD.md` briefly, including its self-assessment caveat.

**Say:**

> The saved live golden-set run is dated November 23, 2026. It records 20 of 20 cases passing, all 20 receiving live LLM judgments, five of five adversarial cases passing, and zero safety-critical automatic executions in that benchmark. These are results from a finite test set, not a guarantee of production performance. The scorecard is a project self-assessment; only the capstone evaluator assigns the official rubric score. The evidence files and tests are organized by the project milestones so the implementation can be reviewed rather than judged from this video alone.

### 9:10–10:00 — Wrap-up

**On screen:** Return to the dashboard overview. Hold on the health status and core panels, then end on the PlantGuard name.

**Say:**

> To recap, PlantGuard checks alert plausibility before starting work, grounds maintenance guidance in approved documents, pauses safety-critical workflows for human review, and records operational traces and evaluation evidence. The demo used synthetic data and a local service. The key design principle is that an AI recommendation can support maintenance review, but it cannot replace approved procedures or the responsible person’s safety decision. Thank you for watching.

## Recording checklist

- Keep API keys, `.env`, and personal notifications off screen.
- Use the sample values in this script; do not enter real site or personnel data.
- Show citations and the approval pause clearly; these are the central differentiators.
- Do not call the 32/32 score official. The scorecard labels it as a self-assessment.
- If live provider calls stall, keep the recording moving with the explanation, then show the saved benchmark artifact. Do not imply a cached result came from the current live request.
