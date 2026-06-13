from ai_dev_agent.ai.code_agent import CodeChangeResult
from ai_dev_agent.config import Settings
from ai_dev_agent.graph.state import AgentState
from ai_dev_agent.models import Task
from ai_dev_agent.observability.report import build_execution_report


def _state(input_tokens: int, output_tokens: int) -> AgentState:
    state: AgentState = {
        "trace_id": "t1",
        "task": Task(task_id="TASK-1", title="x", description="y"),
        "status": "success",
        "change": CodeChangeResult(
            changed_files=["a.py"],
            model="gpt-5.2",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        "timeline": [],
    }
    return state


def test_cost_usd_computed_from_token_prices() -> None:
    settings = Settings(
        _env_file=None, openai_input_cost_per_1m=1.75, openai_output_cost_per_1m=14.0
    )
    report = build_execution_report(_state(1_000_000, 1_000_000), settings)
    assert report.ai is not None
    assert report.ai.cost_usd == 15.75


def test_cost_usd_is_zero_without_settings() -> None:
    report = build_execution_report(_state(1000, 1000))
    assert report.ai is not None
    assert report.ai.cost_usd == 0.0
