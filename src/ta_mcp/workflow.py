import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from ta_mcp.configuration import read_policy, read_text_input
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
from ta_mcp.scoring import ScoreCalculator
from ta_mcp.validation import validate_analysis


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
) -> WorkflowResult:
    """Coordinate two runtime roles and persist only through scoped MCP.

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

    Returns:
        Final report paths, review identity, and recommendation state.
    """
    assignment = AssignmentDocument.from_text(
        read_text_input(requirements), provenance=requirements.name
    )
    policy = read_policy(policy_path)
    run_id = uuid4()
    events: list[TraceEvent] = []

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

    trace("analyst", "agent_start", "Requirements Analyst started")
    async with ReviewMCPClient(
        "analyst", submission, requirements, policy_path, output, database
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
            language_model.analyze(assignment, policy), timeout=120
        )
        validate_analysis(assignment, analysis)
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
        "grader", submission, requirements, policy_path, output, database
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
            "; ".join(f"{item.kind}={item.status}" for item in checks.checks),
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
            timeout=120,
        )
        trace(
            "grader",
            "agent_result",
            f"Received {len(decisions.assessments)} criterion assessments",
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
            f"Validated review is {run.state}; all numeric totals computed by Python",
        )
        trace("grader", "mcp_call", "save_review")
        bundle = ReviewBundle(
            **analysis.model_dump(),
            assignment=assignment,
            policy=policy,
            submission=inspection.submission,
            files=inspection.files,
            run=run,
            checks=checks.checks,
            **decisions.model_dump(exclude={"schema_version"}),
            trace_events=events,
        )
        summary = ScoreCalculator.calculate(bundle)
        bundle = ReviewBundle.model_validate(
            {**bundle.model_dump(), "summary": summary}
        )
        saved = await grader.save(SaveReviewRequest(bundle=bundle))
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
