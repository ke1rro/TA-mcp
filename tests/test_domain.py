from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ta_mcp.domain import (
    AssignmentDocument,
    AssignmentRequirement,
    CriterionAssessment,
    CriterionRequirementRef,
    GradingPolicy,
    GradingRubric,
    ObservationEvidence,
    PenaltyApplication,
    PenaltyRule,
    ReviewBundle,
    ReviewRun,
    RubricCriterion,
    SourceFileEvidence,
    SourceSpan,
    SubmissionArchive,
    SubmissionFile,
)
from ta_mcp.scoring import ScoreCalculator


def make_bundle() -> ReviewBundle:
    """Build a small source-backed, unresolved review."""
    assignment = AssignmentDocument.from_text("Implement add: 10 points.")
    requirement = AssignmentRequirement(
        assignment_id=assignment.id,
        code="R1",
        text="Implement add",
        source_quote=assignment.original_text,
        source=SourceSpan(start_line=1, end_line=1),
        points=Decimal("10"),
    )
    rubric = GradingRubric(
        assignment_id=assignment.id,
        scoring_mode="POINTS",
        maximum_base_points=Decimal("10"),
    )
    criterion = RubricCriterion(
        rubric_id=rubric.id,
        code="C1",
        ordinal=1,
        title="Addition",
        description="Implement add",
        category="correctness",
        verification_method="source and tests",
        max_points=Decimal("10"),
    )
    submission = SubmissionArchive(
        archive_name="submission.zip", sha256="0" * 64, byte_size=0
    )
    policy = GradingPolicy()
    run = ReviewRun(
        submission_id=submission.id,
        rubric_id=rubric.id,
        policy_id=policy.id,
        state="NEEDS_REVIEW",
    )
    assessment = CriterionAssessment(
        review_run_id=run.id,
        criterion_id=criterion.id,
        status="NOT_VERIFIABLE",
        explanation="No execution backend",
        not_verifiable_reason="No execution backend",
    )
    return ReviewBundle(
        assignment=assignment,
        requirements=[requirement],
        rubric=rubric,
        criteria=[criterion],
        criterion_requirements=[
            CriterionRequirementRef(
                criterion_id=criterion.id, requirement_id=requirement.id
            )
        ],
        policy=policy,
        submission=submission,
        run=run,
        assessments=[assessment],
    )


def test_decimal_scoring_preserves_unresolved_bounds() -> None:
    """Catch invented final scores for unavailable scored criteria."""
    bundle = make_bundle()
    result = ScoreCalculator.calculate(bundle)
    assert result.known_points == Decimal("0")
    assert result.minimum_possible_score == Decimal("0")
    assert result.maximum_possible_score == Decimal("10")
    assert result.recommended_score is None
    assert result.unresolved_criterion_ids == [bundle.criteria[0].id]
    assert ReviewBundle.model_validate_json(bundle.model_dump_json()) == bundle
    with pytest.raises(ValidationError):
        GradingPolicy(max_score=0.1)
    with pytest.raises(ValidationError):
        GradingPolicy(max_score="NaN")
    assignment = AssignmentDocument.from_text(
        "Implement add: 10 points.\nOptional docstring: 2 points.\n"
        "Deduct 1 point for absent README.md.\nGrade cap: 11 points."
    )
    requirements = [
        AssignmentRequirement(
            assignment_id=assignment.id,
            code=code,
            text=quote,
            source_quote=quote,
            source=SourceSpan(start_line=line, end_line=line),
            necessity="optional" if line == 2 else "mandatory",
            kind="scoring" if line > 2 else "functional",
            points=points,
        )
        for line, code, quote, points in (
            (1, "R1", "Implement add: 10 points.", Decimal(10)),
            (2, "R2", "Optional docstring: 2 points.", Decimal(2)),
            (3, "P1", "Deduct 1 point for absent README.md.", None),
            (4, "CAP", "Grade cap: 11 points.", Decimal(11)),
        )
    ]
    source = SubmissionFile(
        submission_id=bundle.submission.id,
        relative_path="main.py",
        sha256="0" * 64,
        byte_size=4,
        line_count=1,
    )
    evidence = SourceFileEvidence(
        review_run_id=bundle.run.id,
        summary="Source observed",
        submission_file_id=source.id,
        span=SourceSpan(start_line=1, end_line=1),
        verified_excerpt="pass",
    )
    observation = ObservationEvidence(
        review_run_id=bundle.run.id,
        summary="README absent",
        observation="file_absent",
        relative_path="README.md",
    )
    bonus = RubricCriterion(
        rubric_id=bundle.rubric.id,
        code="B1",
        ordinal=2,
        title="Docstring",
        description="Optional documentation",
        category="quality",
        role="BONUS",
        verification_method="source",
        max_points=Decimal(2),
    )
    rule = PenaltyRule(
        rubric_id=bundle.rubric.id,
        code="P1",
        description="Missing README",
        amount=Decimal(1),
        trigger="README.md absent",
        requirement_ids=[requirements[2].id],
    )
    application = PenaltyApplication(
        review_run_id=bundle.run.id,
        penalty_rule_id=rule.id,
        applied_amount=Decimal(1),
        explanation="Required README is absent",
        evidence_ids=[observation.id],
    )
    payload = bundle.model_dump()
    payload.update(
        assignment=assignment,
        requirements=requirements,
        files=[source],
        evidence=[evidence, observation],
        criteria=[bundle.criteria[0], bonus],
        penalty_rules=[rule],
        penalty_applications=[application],
    )
    payload["rubric"].update(
        assignment_id=assignment.id,
        bonus_policy="ADD",
        grade_cap=Decimal(11),
        grade_cap_requirement_id=requirements[3].id,
    )
    payload["criterion_requirements"] = [
        CriterionRequirementRef(
            criterion_id=criterion.id, requirement_id=requirement.id
        )
        for criterion, requirement in zip(
            payload["criteria"], requirements[:2], strict=True
        )
    ]
    for status, award, expected in (
        ("PASS", "10", "11"),
        ("PARTIAL", "3.125", "4.125"),
        ("FAIL", "0", "1"),
    ):
        payload["assessments"] = [
            CriterionAssessment(
                review_run_id=bundle.run.id,
                criterion_id=criterion.id,
                status=status if criterion.role == "CORE" else "PASS",
                explanation="Award justified by source review",
                awarded_points=(
                    Decimal(award) if criterion.role == "CORE" else Decimal(2)
                ),
                evidence_ids=[evidence.id],
            )
            for criterion in payload["criteria"]
        ]
        scored = ReviewBundle.model_validate(payload)
        assert ScoreCalculator.calculate(scored).recommended_score == Decimal(expected)
    payload["penalty_applications"] = [application, application]
    with pytest.raises(ValidationError):
        ReviewBundle.model_validate(payload)


def test_bundle_rejects_fabricated_sources_and_relationships() -> None:
    """Catch invalid citations, missing criteria, and unsupported failures."""
    bundle = make_bundle()
    changes = [
        ("requirements", 0, "source_quote", "invented quote"),
        ("requirements", 0, "assignment_id", str(uuid4())),
        ("assessments", 0, "criterion_id", str(uuid4())),
        ("assessments", 0, "status", "FAIL"),
    ]
    for collection, index, field, value in changes:
        payload = bundle.model_dump(mode="json")
        payload[collection][index][field] = value
        with pytest.raises(ValidationError):
            ReviewBundle.model_validate(payload)
    payload = bundle.model_dump(mode="json")
    payload["assessments"] = []
    with pytest.raises(ValidationError):
        ReviewBundle.model_validate(payload)
    payload = bundle.model_dump(mode="json")
    payload["assessments"].append(payload["assessments"][0])
    with pytest.raises(ValidationError):
        ReviewBundle.model_validate(payload)
