"""Build the execution report from the final graph state."""

from __future__ import annotations

from typing import cast

from ai_dev_agent.graph.state import AgentState
from ai_dev_agent.models import AIUsage, ExecutionReport, ReportStatus


def build_execution_report(state: AgentState) -> ExecutionReport:
    change = state.get("change")
    ai = (
        AIUsage(
            model=change.model,
            changed_files=change.changed_files,
            input_tokens=change.input_tokens,
            output_tokens=change.output_tokens,
        )
        if change is not None
        else None
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
