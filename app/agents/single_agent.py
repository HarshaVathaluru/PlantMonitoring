"""PlantGuard M2 Tool-Enabled Single Agent.

Implements a bounded ReAct / Planner-Executor agent loop that interacts with
real operational tables via typed Python tools.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.adapters.llm_adapter import LLMAdapter
from app.config.settings import get_settings
from app.schemas.maintenance_event import MaintenanceEvent, RiskLevel
from app.tools.maintenance_tools import (
    calculate_downtime_cost,
    check_spare_parts_inventory,
    get_sensor_history,
    schedule_technician,
)

logger = logging.getLogger(__name__)


class ToolCallDecision(BaseModel):
    """Structured decision by agent on which tool to invoke next."""
    thought: str = Field(..., description="Reasoning for the next step")
    action: str = Field(..., description="Tool name: 'get_sensor_history', 'calculate_downtime_cost', 'check_spare_parts_inventory', 'schedule_technician', or 'finish'")
    action_input: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")


class AgentExecutionResult(BaseModel):
    """Complete traceable result of an agent run."""
    initial_event: Optional[MaintenanceEvent] = None
    query: str
    steps_executed: int
    tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    findings: Dict[str, Any] = Field(default_factory=dict)
    final_synthesis: str
    requires_human_approval: bool = False
    stop_reason: str = "completed"


class MaintenanceSingleAgent:
    """
    Bounded Single Agent coordinating diagnostic and operational tools.
    """

    MAX_STEPS = 6

    def __init__(self, llm_adapter: Optional[LLMAdapter] = None):
        self.adapter = llm_adapter or LLMAdapter()
        self.settings = get_settings()

    def _execute_tool(self, action: str, action_input: Dict[str, Any]) -> Any:
        """Execute the chosen tool safely without eval/exec."""
        if action == "get_sensor_history":
            asset_tag = action_input.get("asset_tag", "")
            hours = int(action_input.get("hours", 24))
            return get_sensor_history(asset_tag=asset_tag, hours=hours)

        elif action == "calculate_downtime_cost":
            asset_tag = action_input.get("asset_tag")
            minutes = int(action_input.get("downtime_minutes", 60))
            return calculate_downtime_cost(asset_tag=asset_tag, downtime_minutes=minutes)

        elif action == "check_spare_parts_inventory":
            part_number = action_input.get("part_number", "")
            return check_spare_parts_inventory(part_number=part_number)

        elif action == "schedule_technician":
            required_skill = action_input.get("required_skill", "Mechanical")
            hours = int(action_input.get("estimated_hours", 4))
            date_str = action_input.get("date_str", self.settings.REFERENCE_DATE)
            shift = action_input.get("shift")
            return schedule_technician(
                required_skill=required_skill,
                estimated_hours=hours,
                date_str=date_str,
                shift=shift,
            )

        else:
            return {"error": f"Unknown tool '{action}'"}

    def run(self, query: str, event: Optional[MaintenanceEvent] = None) -> AgentExecutionResult:
        """
        Run the agent loop over a query or maintenance event.
        """
        tools_called = []
        findings: Dict[str, Any] = {}
        requires_approval = False

        if event:
            if event.safety_critical or event.requires_human_approval:
                requires_approval = True
            if event.asset_tag:
                findings["asset_tag"] = event.asset_tag

        # Tool specifications for LLM prompt
        tool_specs = (
            "Available tools:\n"
            "1. get_sensor_history(asset_tag: str, hours: int)\n"
            "2. calculate_downtime_cost(asset_tag: str, downtime_minutes: int)\n"
            "3. check_spare_parts_inventory(part_number: str)\n"
            "4. schedule_technician(required_skill: str, estimated_hours: int, date_str: str, shift: Optional[str])\n"
            "5. finish() - Call when sufficient information is gathered.\n"
        )

        history_text = f"Initial query: {query}\n"
        if event:
            history_text += f"Event Asset: {event.asset_tag}, Severity: {event.severity}, Raw Alert: {event.raw_text}\n"

        stop_reason = "max_iterations"
        for step in range(1, self.MAX_STEPS + 1):
            prompt = (
                f"{tool_specs}\n"
                f"Current investigation history:\n{history_text}\n"
                f"Determine the next action. If you have gathered enough data to provide a recommendation, action must be 'finish'."
            )

            try:
                decision, _ = self.adapter.generate_structured(
                    [
                        {"role": "system", "content": "You are a senior PlantGuard predictive maintenance coordinator."},
                        {"role": "user", "content": prompt},
                    ],
                    ToolCallDecision,
                )
            except Exception as e:
                logger.error(f"Agent decision generation error: {e}")
                # Fallback to deterministic finish
                stop_reason = f"decision_error: {e}"
                break

            if decision.action == "finish" or decision.action not in (
                "get_sensor_history", "calculate_downtime_cost", "check_spare_parts_inventory", "schedule_technician"
            ):
                stop_reason = "completed"
                break

            # Execute tool safely
            tool_result = self._execute_tool(decision.action, decision.action_input)
            result_dict = tool_result.model_dump() if hasattr(tool_result, "model_dump") else tool_result

            tools_called.append({
                "step": step,
                "tool": decision.action,
                "input": decision.action_input,
                "output": result_dict,
            })
            findings[decision.action] = result_dict

            # Check if downtime cost exceeds manager threshold
            if decision.action == "calculate_downtime_cost":
                if result_dict.get("total_cost_inr", 0) >= 30000:
                    requires_approval = True

            history_text += (
                f"\nStep {step}: Thought: {decision.thought}\n"
                f"Action: {decision.action}({json.dumps(decision.action_input)})\n"
                f"Observation: {json.dumps(result_dict)[:400]}\n"
            )

        # Final synthesis
        synthesis_prompt = (
            f"Based on the investigation history:\n{history_text}\n"
            f"Provide a concise, factual maintenance diagnostic summary, downtime cost impact, "
            f"spare parts status, and technician scheduling recommendation."
        )

        try:
            synthesis_resp = self.adapter.generate(
                [
                    {"role": "system", "content": "You are PlantGuard Copilot. Summarize the maintenance investigation cleanly."},
                    {"role": "user", "content": synthesis_prompt},
                ]
            )
            final_synthesis = synthesis_resp.content
        except Exception:
            final_synthesis = f"Investigation completed for {findings.get('asset_tag', 'system')}. Findings recorded across {len(tools_called)} tool calls."

        return AgentExecutionResult(
            initial_event=event,
            query=query,
            steps_executed=len(tools_called),
            tools_called=tools_called,
            findings=findings,
            final_synthesis=final_synthesis,
            requires_human_approval=requires_approval,
            stop_reason=stop_reason,
        )
