import asyncio
from decimal import Decimal
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest

from ta_mcp.contracts import InspectArchiveRequest
from ta_mcp.domain import (
    AssignmentDocument,
    AssignmentRequirement,
    CheckEvidence,
    CriterionAssessment,
    CriterionRequirementRef,
    GradingDecisions,
    GradingPolicy,
    GradingRubric,
    ObservationEvidence,
    RubricAnalysis,
    RubricCriterion,
    SourceFileEvidence,
    SourceSpan,
)
from ta_mcp.mcp_client import ReviewMCPClient
from ta_mcp.repository import ReviewRepository
from ta_mcp.workflow import GradingContext, grade_submission


class ScenarioModel:
    """Deterministic substitute at the external LLM boundary."""

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    async def analyze(
        self, assignment: AssignmentDocument, policy: GradingPolicy
    ) -> RubricAnalysis:
        """Extract the single explicit synthetic requirement."""
        points = None if self.scenario == "unscored" else Decimal("0.3")
        requirement = AssignmentRequirement(
            assignment_id=assignment.id,
            code="R1",
            text=assignment.original_text,
            source_quote=assignment.original_text,
            source=SourceSpan(start_line=1, end_line=1),
            points=points,
        )
        rubric = GradingRubric(
            assignment_id=assignment.id,
            scoring_mode="UNSCORED" if points is None else "POINTS",
            maximum_base_points=points,
        )
        criterion = RubricCriterion(
            rubric_id=rubric.id,
            code="C1",
            ordinal=1,
            title="Required behavior",
            description=assignment.original_text,
            category="correctness",
            verification_method="source, manifest, syntax check",
            max_points=points,
        )
        criteria = [criterion]
        links = [
            CriterionRequirementRef(
                criterion_id=criterion.id, requirement_id=requirement.id
            )
        ]
        if self.scenario == "correct":
            criterion = RubricCriterion.model_validate(
                {**criterion.model_dump(), "id": UUID(int=2)}
            )
            advisory = RubricCriterion.model_validate(
                {
                    **criterion.model_dump(),
                    "id": UUID(int=1),
                    "ordinal": 2,
                    "code": "C2",
                    "role": "ADVISORY",
                    "max_points": None,
                }
            )
            criteria = [criterion, advisory]
            links = [
                CriterionRequirementRef(
                    criterion_id=item.id, requirement_id=requirement.id
                )
                for item in criteria
            ]
        return RubricAnalysis(
            requirements=[requirement],
            rubric=rubric,
            criteria=criteria,
            criterion_requirements=links,
        )

    async def grade(self, context: GradingContext) -> GradingDecisions:
        """Return source-backed decisions or an explicit unresolved state."""
        points = context.analysis.criteria[0].max_points
        evidence = []
        reason = None
        status = "PASS"
        if self.scenario == "runtime":
            status = "NOT_VERIFIABLE"
            points = None
            reason = "Runtime behavior cannot be established without isolated execution"
        elif self.scenario == "missing":
            status = "FAIL"
            points = Decimal(0)
            evidence = [
                ObservationEvidence(
                    review_run_id=context.run.id,
                    summary="Required file absent",
                    observation="file_absent",
                    relative_path="main.py",
                )
            ]
        elif self.scenario == "syntax_error":
            status = "FAIL"
            points = Decimal(0)
            check = next(item for item in context.checks if item.status == "FAILED")
            evidence = [
                CheckEvidence(
                    review_run_id=context.run.id,
                    summary="Python syntax invalid",
                    check_execution_id=check.id,
                    diagnostic_stream="stderr",
                    start_offset=0,
                    end_offset=len(check.bounded_stderr),
                    diagnostic=check.bounded_stderr,
                    exit_code=1,
                )
            ]
        else:
            source = next(
                item
                for item in context.inspection.files
                if item.relative_path == "main.py"
            )
            evidence = [
                SourceFileEvidence(
                    review_run_id=context.run.id,
                    summary="Required Python implementation exists",
                    submission_file_id=source.id,
                    span=SourceSpan(start_line=1, end_line=1),
                    verified_excerpt="def add(a, b): return a + b",
                )
            ]
        assessment = CriterionAssessment(
            review_run_id=context.run.id,
            criterion_id=context.analysis.criteria[0].id,
            status=status,
            explanation=reason
            or "Decision is supported by the referenced tool evidence",
            not_verifiable_reason=reason,
            awarded_points=points,
            evidence_ids=[item.id for item in evidence],
        )
        assessments = [assessment]
        if self.scenario == "correct":
            assessments.append(
                CriterionAssessment(
                    review_run_id=context.run.id,
                    criterion_id=context.analysis.criteria[1].id,
                    status="PASS",
                    explanation="Advisory source review",
                    evidence_ids=[item.id for item in evidence],
                )
            )
        return GradingDecisions(evidence=evidence, assessments=assessments)


@pytest.mark.parametrize(
    ("scenario", "expected_status", "expected_score"),
    [
        ("correct", "PASS", "0.3"),
        ("syntax_error", "FAIL", "0"),
        ("missing", "FAIL", "0"),
        ("runtime", "NOT_VERIFIABLE", None),
        ("unscored", "PASS", None),
    ],
)
def test_mcp_vertical_slice(
    tmp_path: Path, scenario: str, expected_status: str, expected_score: str | None
) -> None:
    """Catch broken MCP transport, lost evidence, and invented numeric grades."""
    submission = tmp_path / "submission.zip"
    requirements = tmp_path / "assignment.md"
    policy = tmp_path / "policy.yaml"
    description = (
        "Verify runtime addition"
        if scenario == "runtime"
        else "Provide main.py with valid Python syntax"
    )
    requirements.write_text(
        description + ("." if scenario == "unscored" else ": 0.3 points.")
    )
    policy.write_text("max_score: 100\nstrictness: strict\n")
    with ZipFile(submission, "w") as archive:
        archive.writestr(
            "readme.txt" if scenario == "missing" else "main.py",
            (
                "def broken(:\n"
                if scenario == "syntax_error"
                else "def add(a, b): return a + b\n"
            ),
        )
    saved = asyncio.run(
        grade_submission(
            submission,
            requirements,
            policy,
            tmp_path / "reports",
            tmp_path / "audit.sqlite",
            language_model=ScenarioModel(scenario),
        )
    )
    bundle = ReviewRepository(tmp_path / "audit.sqlite", tmp_path / "reports").load(
        saved.run_id
    )
    assert bundle.assessments[0].status == expected_status
    assert bundle.summary is not None
    assert bundle.summary.recommended_score == (
        None if expected_score is None else Decimal(expected_score)
    )
    assert saved.json_path.name == "review.json"
    assert saved.markdown_path.name == "review.md"
    assert "mcp_call" in [event.event_type for event in bundle.trace_events]
    assert "handoff" in [event.event_type for event in bundle.trace_events]
    assert (
        next(item for item in bundle.checks if item.kind == "tests").status
        == "UNAVAILABLE"
    )


def test_analyst_mcp_has_no_persistence_permission(tmp_path: Path) -> None:
    """Catch authorization implemented only as an agent prompt or UI filter."""

    async def verify() -> None:
        """Exercise actual analyst server discovery and direct tool dispatch."""
        submission = tmp_path / "submission.zip"
        with ZipFile(submission, "w") as archive:
            archive.writestr("main.py", "pass\n")
        requirements = tmp_path / "assignment.md"
        requirements.write_text("Provide code.")
        policy = tmp_path / "policy.yaml"
        policy.write_text("{}")
        async with ReviewMCPClient(
            "analyst",
            submission,
            requirements,
            policy,
            tmp_path / "reports",
            tmp_path / "audit.sqlite",
        ) as client:
            assert await client.tool_names() == {"inspect_archive"}
            inspection = await client.inspect(
                InspectArchiveRequest(archive_path=str(submission))
            )
            assert len(inspection.files) == 1
            denied = await client.server.call_tool("save_review", {"request": {}})
            assert denied.is_error
        assert not (tmp_path / "audit.sqlite").exists()

    asyncio.run(verify())
