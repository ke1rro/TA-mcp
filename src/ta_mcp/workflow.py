import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from ta_mcp.configuration import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    read_policy,
    read_text_input,
)
from ta_mcp.contracts import InspectArchiveRequest, RunChecksRequest, SaveReviewRequest
from ta_mcp.domain import (
    ArchiveInspection,
    AssignmentDocument,
    CheckExecution,
    Contract,
    CriterionStatus,
    GradingDecisions,
    GradingPolicy,
    ReviewBundle,
    ReviewRun,
    RubricAnalysis,
    RunState,
    TraceEvent,
)
from ta_mcp.mcp_client import ReviewMCPClient
from ta_mcp.observability import ExecutionLog, describe_error
from ta_mcp.reporting import render_analysis_markdown
from ta_mcp.scoring import ScoreCalculator
from ta_mcp.validation import resolve_check_evidence_offsets, validate_analysis


class GradingContext(Contract):
    """Frozen analyst handoff plus actual MCP observations for the grader."""

    assignment: AssignmentDocument
    policy: GradingPolicy
    analysis: RubricAnalysis
    run: ReviewRun
    inspection: ArchiveInspection
    checks: list[CheckExecution]


class ReviewLanguageModel(Protocol):
    """External structured-output boundary for both runtime LLM roles."""

    async def analyze(
        self, assignment: AssignmentDocument, policy: GradingPolicy
    ) -> RubricAnalysis:
        """Extract source-grounded criteria without inspecting student instructions."""
        ...

    async def grade(self, context: GradingContext) -> GradingDecisions:
        """Assess the frozen rubric using only observed evidence."""
        ...


@dataclass(frozen=True)
class WorkflowResult:
    """Finalized CLI result returned after a successful MCP save."""

    run_id: UUID
    json_path: Path
    markdown_path: Path
    state: RunState
    recommended_score: str | None


async def grade_submission(
    submission: Path,
    requirements: Path,
    policy_path: Path,
    output: Path,
    database: Path,
    language_model: ReviewLanguageModel,
    observer: ExecutionLog | None = None,
    llm_timeout_seconds: int = DEFAULT_LLM_TIMEOUT_SECONDS,
    should_repair_output: bool = False,
) -> WorkflowResult:
    """Coordinate two roles, expose their handoff, and persist reviews through MCP.

    The analyst receives the assignment and policy. A validated structured handoff
    freezes the rubric. The grader receives an inspected manifest and actual check
    results; deterministic validators calculate all totals before the only save.

    Args:
        submission: Local ZIP archive authorized for inspection.
        requirements: Markdown or plain-text assignment file.
        policy_path: JSON or YAML grading policy file.
        output: Parent directory for immutable per-run report directories.
        database: Local SQLite audit database.
        language_model: Structured external LLM implementation for the two roles.
        observer: Optional shared live event log and request budget.
        llm_timeout_seconds: Provider wait limit, with five seconds for SDK cleanup.
        should_repair_output: Reserve time for one additional JSON repair call.

    Returns:
        Final report paths, review identity, and recommendation state.
    """
    assignment = AssignmentDocument.from_text(
        read_text_input(requirements), provenance=requirements.name
    )
    policy = read_policy(policy_path)
    run_id = uuid4()
    events: list[TraceEvent] = []
    agent_timeout = (llm_timeout_seconds + 5) * (2 if should_repair_output else 1)
    if observer is not None:
        observer.run_id = str(run_id)
        observer.emit(
            "SYSTEM",
            "workflow_start",
            details={
                "submission": submission.name,
                "requirements": requirements.name,
                "strategy": "MULTI_AGENT",
            },
        )

    def trace(
        role: Literal["analyst", "grader", "orchestrator"],
        event_type: Literal[
            "agent_start",
            "agent_result",
            "mcp_call",
            "mcp_result",
            "handoff",
            "error",
            "decision",
        ],
        detail: str,
    ) -> None:
        """Append bounded local metadata without prompts or credentials."""
        events.append(
            TraceEvent(
                review_run_id=run_id,
                sequence=len(events) + 1,
                agent_role=role,
                event_type=event_type,
                detail=detail,
            )
        )
        if observer is not None and event_type not in {"mcp_call", "mcp_result"}:
            observer.emit(
                "AGENT" if event_type in {"agent_start", "agent_result"} else "SYSTEM",
                "agent_complete" if event_type == "agent_result" else event_type,
                role,
                {"summary": detail},
            )

    trace("analyst", "agent_start", "Requirements Analyst started")
    async with ReviewMCPClient(
        "analyst", submission, requirements, policy_path, output, database, observer
    ) as analyst:
        trace("analyst", "mcp_call", "inspect_archive")
        inspection = await analyst.inspect(
            InspectArchiveRequest(archive_path=str(submission.resolve()))
        )
        trace(
            "analyst",
            "mcp_result",
            f"Inspected {len(inspection.files)} files; "
            f"SHA-256 {inspection.submission.sha256}",
        )
        analysis = await asyncio.wait_for(
            language_model.analyze(assignment, policy), timeout=agent_timeout
        )
        if observer is not None:
            observer.emit("SYSTEM", "rubric_validation_start", "analyst")
        validate_analysis(assignment, analysis)
        handoff_directory = output.parent / "handoffs" / str(run_id)
        handoff_directory.mkdir(parents=True, exist_ok=True)
        analysis_json = handoff_directory / "analyst.json"
        analysis_markdown = handoff_directory / "analyst.md"
        analysis_json.write_text(
            json.dumps(analysis.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        analysis_markdown.write_text(
            render_analysis_markdown(analysis), encoding="utf-8"
        )
        if observer is not None:
            observer.emit(
                "SYSTEM", "rubric_validation_complete", "analyst", {"status": "ok"}
            )
            observer.emit(
                "SYSTEM",
                "analyst_handoff_saved",
                "analyst",
                {
                    "json_path": str(analysis_json),
                    "markdown_path": str(analysis_markdown),
                    "requirements": len(analysis.requirements),
                    "criteria": len(analysis.criteria),
                },
            )
    run = ReviewRun(
        id=run_id,
        submission_id=inspection.submission.id,
        rubric_id=analysis.rubric.id,
        policy_id=policy.id,
        state=RunState.RUNNING,
        started_at=events[0].timestamp,
    )
    trace(
        "analyst",
        "agent_result",
        f"Validated {len(analysis.criteria)} source-linked criteria",
    )
    trace(
        "orchestrator",
        "handoff",
        f"Frozen rubric {analysis.rubric.id} passed to Submission Grader",
    )
    async with ReviewMCPClient(
        "grader", submission, requirements, policy_path, output, database, observer
    ) as grader:
        trace("grader", "agent_start", "Submission Grader started")
        trace("grader", "mcp_call", "inspect_archive")
        current_inspection = await grader.inspect(
            InspectArchiveRequest(archive_path=str(submission.resolve()))
        )
        if inspection.submission != current_inspection.submission:
            raise ValueError("Submission changed between runtime agents")
        inspection = current_inspection
        trace(
            "grader",
            "mcp_result",
            f"Confirmed archive SHA-256 {inspection.submission.sha256}",
        )
        trace("grader", "mcp_call", "run_checks")
        checks = await grader.run_checks(
            RunChecksRequest(
                review_run_id=run.id,
                archive_path=str(submission.resolve()),
                assignment=assignment,
                analysis=analysis,
                policy=policy,
            )
        )
        trace(
            "grader",
            "mcp_result",
            "; ".join(f"{item.tool_name}={item.status}" for item in checks.checks),
        )
        decisions = await asyncio.wait_for(
            language_model.grade(
                GradingContext(
                    assignment=assignment,
                    policy=policy,
                    analysis=analysis,
                    run=run,
                    inspection=inspection,
                    checks=checks.checks,
                )
            ),
            timeout=agent_timeout,
        )
        trace(
            "grader",
            "agent_result",
            f"Received {len(decisions.assessments)} criterion assessments",
        )
        decisions, corrected_offsets = resolve_check_evidence_offsets(
            decisions, checks.checks
        )
        if observer is not None and corrected_offsets:
            observer.emit(
                "SYSTEM",
                "evidence_offsets_resolved",
                "grader",
                {"corrected": corrected_offsets},
            )
        has_unresolved = analysis.rubric.needs_clarification or any(
            item.status == CriterionStatus.NOT_VERIFIABLE
            for item in decisions.assessments
        )
        run = ReviewRun.model_validate(
            {
                **run.model_dump(),
                "state": (
                    RunState.NEEDS_REVIEW if has_unresolved else RunState.COMPLETED
                ),
                "finished_at": datetime.now(UTC),
            }
        )
        trace(
            "grader",
            "decision",
            f"Proposed review state is {run.state}; final validation pending",
        )
        trace("grader", "mcp_call", "save_review")
        if observer is not None:
            observer.emit("SYSTEM", "review_validation_start", "grader")
        payload = {
            **analysis.model_dump(mode="json"),
            "assignment": assignment.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "submission": inspection.submission.model_dump(mode="json"),
            "files": [item.model_dump(mode="json") for item in inspection.files],
            "run": run.model_dump(mode="json"),
            "checks": [item.model_dump(mode="json") for item in checks.checks],
            **decisions.model_dump(mode="json", exclude={"schema_version"}),
            "trace_events": [item.model_dump(mode="json") for item in events],
        }
        try:
            bundle = ReviewBundle.model_validate(payload)
            summary = ScoreCalculator.calculate(bundle)
            bundle = ReviewBundle.model_validate(
                {**bundle.model_dump(), "summary": summary}
            )
        except ValidationError as error:
            draft_path = output.parent / "checks" / str(run.id) / "invalid-review.json"
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            draft_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if observer is not None:
                observer.emit(
                    "ERROR",
                    "review_validation_failed",
                    "grader",
                    {**describe_error(error), "invalid_review_path": str(draft_path)},
                )
            raise
        if observer is not None:
            observer.emit(
                "SYSTEM",
                "review_created",
                "grader",
                {"state": run.state.value, "assessments": len(bundle.assessments)},
            )
        saved = await grader.save(SaveReviewRequest(bundle=bundle))
        if observer is not None:
            observer.emit(
                "SYSTEM",
                "review_persisted",
                "grader",
                {"json_path": saved.json_path, "markdown_path": saved.markdown_path},
            )
    return WorkflowResult(
        run_id=run.id,
        json_path=Path(saved.json_path),
        markdown_path=Path(saved.markdown_path),
        state=run.state,
        recommended_score=(
            None
            if summary.recommended_score is None
            else str(summary.recommended_score)
        ),
    )
