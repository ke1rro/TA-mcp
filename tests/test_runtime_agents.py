import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from agents import OpenAIChatCompletionsModel
from httpx2 import Request
from pydantic import ValidationError

from ta_mcp import runtime_agents
from ta_mcp.domain import AssignmentDocument, GradingDecisions, GradingPolicy
from ta_mcp.observability import ExecutionLog, RequestLimitReached


def test_gemini_uses_explicit_api_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid discovery requests and keep credentials out of agent prompts."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    client = SimpleNamespace(
        close=AsyncMock(),
        models=SimpleNamespace(list=AsyncMock()),
    )
    with (
        patch.object(runtime_agents, "AsyncOpenAI", return_value=client) as constructor,
        patch.object(runtime_agents, "DefaultAsyncHttpx2Client", return_value=Mock()),
    ):
        model = asyncio.run(
            runtime_agents.create_review_model(
                "gemini", "gemini-2.5-flash", llm_timeout_seconds=240
            )
        )
    assert isinstance(model.requirements_analyst.model, OpenAIChatCompletionsModel)
    assert model.requirements_analyst.model.model == "gemini-2.5-flash"
    assert model.submission_grader.model is model.requirements_analyst.model
    assert constructor.call_args.kwargs["max_retries"] == 0
    assert constructor.call_args.kwargs["timeout"] == 240
    assert constructor.call_args.kwargs["api_key"] == "test-secret"
    assert "test-secret" not in str(model.requirements_analyst.instructions)
    client.models.list.assert_not_awaited()
    assert model.requirements_analyst.model_settings.retry is not None
    assert model.requirements_analyst.model_settings.retry.max_retries == 0


def test_gemini_rejects_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject a UI display name before attempting a generation request."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    with patch.object(runtime_agents, "AsyncOpenAI") as constructor:
        with pytest.raises(ValueError, match="API model ID"):
            asyncio.run(runtime_agents.create_review_model("gemini", "Gemini Flash"))
    constructor.assert_not_called()


def test_gemini_json_mode_preserves_pydantic_validation() -> None:
    """Reject invalid provider JSON before it reaches the frozen handoff."""
    model = runtime_agents.OpenAIReviewModel("unused", is_gemini=True)
    assert model.requirements_analyst.model_settings.extra_args == {
        "response_format": {"type": "json_object"}
    }
    assert model.requirements_analyst.model_settings.reasoning is not None
    assert model.requirements_analyst.model_settings.reasoning.effort == "low"
    response = SimpleNamespace(
        final_output_as=Mock(return_value='{"requirements": []}'),
        context_wrapper=SimpleNamespace(
            usage=SimpleNamespace(requests=1, total_tokens=0)
        ),
    )
    assignment = AssignmentDocument.from_text("Перевірити програму на C++")
    with patch.object(
        runtime_agents.Runner, "run", AsyncMock(return_value=response)
    ) as run:
        with pytest.raises(ValueError, match="validation"):
            asyncio.run(model.analyze(assignment, GradingPolicy()))
    assert run.await_args is not None
    assert assignment.original_text in run.await_args.args[1]
    assert "\\u041f" not in run.await_args.args[1]


def install_model_responses(
    monkeypatch: pytest.MonkeyPatch,
    observer: ExecutionLog,
    outputs: list[str],
) -> list[dict]:
    """Replace only external inference and retain the real HTTP budget hook."""
    payloads: list[dict] = []

    async def respond(
        agent: object, payload: str, **options: object
    ) -> SimpleNamespace:
        """Count one inference attempt without opening a network connection."""
        await observer.api_request_started(
            Request("POST", "https://example.invalid/chat/completions")
        )
        payloads.append(json.loads(payload))
        output = outputs[len(payloads) - 1]
        return SimpleNamespace(
            final_output_as=Mock(return_value=output),
            context_wrapper=SimpleNamespace(
                usage=SimpleNamespace(requests=1, total_tokens=0)
            ),
        )

    monkeypatch.setattr(runtime_agents.Runner, "run", respond)
    return payloads


def test_output_repair_is_validated_and_shared_between_roles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repair once, preserve strict validation and prevent a second role repair."""
    trace = tmp_path / "trace.jsonl"
    observer = ExecutionLog(trace_path=trace, max_llm_requests=4)
    model = runtime_agents.OpenAIReviewModel(
        "unused", is_gemini=True, observer=observer, should_repair_output=True
    )
    invalid = '{"assessments": [], "$defs": {"private": "not-for-logs"}}'
    payloads = install_model_responses(
        monkeypatch, observer, [invalid, '{"assessments": []}', invalid]
    )
    try:
        result = asyncio.run(
            model.run_structured_agent(
                model.submission_grader,
                '{"context": "frozen"}',
                "grader",
                GradingDecisions,
            )
        )
        assert result.assessments == []
        assert observer.llm_requests == 2
        assert payloads[1]["original_input"] == {"context": "frozen"}
        assert payloads[1]["invalid_output"] == invalid
        with pytest.raises(ValidationError, match="extra_forbidden"):
            asyncio.run(
                model.run_structured_agent(
                    model.requirements_analyst, "{}", "analyst", GradingDecisions
                )
            )
        assert observer.llm_requests == 3
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        assert sum(item["event"] == "output_repair_start" for item in events) == 1
        assert "not-for-logs" not in trace.read_text()
    finally:
        observer.close()


@pytest.mark.parametrize(
    ("should_repair_output", "limit", "error_type"),
    [(False, 3, ValidationError), (True, 1, RequestLimitReached)],
)
def test_output_repair_requires_opt_in_and_available_request_budget(
    monkeypatch: pytest.MonkeyPatch,
    should_repair_output: bool,
    limit: int,
    error_type: type[Exception],
) -> None:
    """Reject invalid output without spending an unauthorized extra request."""
    observer = ExecutionLog(max_llm_requests=limit)
    model = runtime_agents.OpenAIReviewModel(
        "unused",
        is_gemini=True,
        observer=observer,
        should_repair_output=should_repair_output,
    )
    install_model_responses(monkeypatch, observer, ['{"assessments": [], "$defs": {}}'])
    with pytest.raises(error_type):
        asyncio.run(
            model.run_structured_agent(
                model.submission_grader, "{}", "grader", GradingDecisions
            )
        )
    assert observer.llm_requests == 1


def test_invalid_repair_is_not_accepted_or_repeated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stop after one repair even when the request budget has spare capacity."""
    observer = ExecutionLog(max_llm_requests=5)
    model = runtime_agents.OpenAIReviewModel(
        "unused", is_gemini=True, observer=observer, should_repair_output=True
    )
    install_model_responses(monkeypatch, observer, ['{"assessments": false}'] * 2)
    with pytest.raises(ValidationError):
        asyncio.run(
            model.run_structured_agent(
                model.submission_grader, "{}", "grader", GradingDecisions
            )
        )
    assert observer.llm_requests == 2


def test_demo_injects_one_labeled_error_and_requires_model_repair(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Route a deliberately invalid instance through the real strict repair path."""
    trace = tmp_path / "demo.jsonl"
    observer = ExecutionLog(trace_path=trace, max_llm_requests=3)
    model = runtime_agents.OpenAIReviewModel(
        "unused",
        is_gemini=True,
        observer=observer,
        should_repair_output=True,
        should_inject_json_error=True,
    )
    payloads = install_model_responses(
        monkeypatch, observer, ['{"assessments": []}'] * 3
    )
    try:
        for role, agent in (
            ("analyst", model.requirements_analyst),
            ("grader", model.submission_grader),
        ):
            result = asyncio.run(
                model.run_structured_agent(agent, "{}", role, GradingDecisions)
            )
            assert result.assessments == []
        assert observer.llm_requests == 3
        rejected = json.loads(payloads[1]["invalid_output"])
        assert rejected["assessments"] == []
        assert "demo_extra_field" in rejected
        assert payloads[1]["validation_errors"] == [
            {"field": "demo_extra_field", "type": "extra_forbidden"}
        ]
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        injected = [item for item in events if item["event"] == "demo_fault_injected"]
        assert len(injected) == 1
        assert injected[0]["details"]["injected_by"] == "coordinator"
        assert injected[0]["details"]["original_contract_valid"] is True
        assert sum(item["event"] == "output_repair_complete" for item in events) == 1
    finally:
        observer.close()
