"""Build the execution report from the final graph state."""

from __future__ import annotations

from typing import cast

from ai_dev_agent.config import Settings
from ai_dev_agent.graph.state import AgentState
from ai_dev_agent.models import AIUsage, ExecutionReport, ReportStatus


def build_execution_report(state: AgentState, settings: Settings | None = None) -> ExecutionReport:
    change = state.get("change")
    ai = None
    if change is not None:
        input_tokens = state.get("ai_input_tokens") or change.input_tokens
        output_tokens = state.get("ai_output_tokens") or change.output_tokens
        ai = AIUsage(
            model=change.model,
            changed_files=change.changed_files,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_estimate_cost(input_tokens, output_tokens, settings),
        )
    errors: list[dict[str, object]] = []
    note = state.get("note")
    error = state.get("error")
    if error is not None:
        if error.get("code") == "insufficient_change":
            note = note or str(error.get("message"))
        else:
            errors.append(error)
    return ExecutionReport(
        trace_id=state["trace_id"],
        task_id=state["task"].task_id,
        status=cast(ReportStatus, state.get("status", "failed")),
        timeline=state.get("timeline", []),
        analysis=state.get("analysis"),
        ai=ai,
        test=state.get("test_result"),
        pr=state.get("pr"),
        note=note,
        errors=errors,
    )


def _estimate_cost(input_tokens: int, output_tokens: int, settings: Settings | None) -> float:
    if settings is None:
        return 0.0
    cost = (
        input_tokens / 1_000_000 * settings.openai_input_cost_per_1m
        + output_tokens / 1_000_000 * settings.openai_output_cost_per_1m
    )
    return round(cost, 6)
