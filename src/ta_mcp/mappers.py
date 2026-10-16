from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ta_mcp import db
from ta_mcp.domain import (
    AssignmentDocument,
    AssignmentRequirement,
    CheckExecution,
    CriterionAssessment,
    CriterionRequirementRef,
    Evidence,
    GradingPolicy,
    GradingRubric,
    PenaltyApplication,
    PenaltyRule,
    ReviewBundle,
    RubricCriterion,
    SourceSpan,
    SubmissionArchive,
    SubmissionFile,
    TraceEvent,
)
from ta_mcp.scoring import ScoreCalculator


def row_values(record: db.Base) -> dict[str, object]:
    """Read explicit relational columns without ORM state."""
    return {
        column.key: getattr(record, column.key) for column in record.__table__.columns
    }


def insert_entity(
    session: Session,
    model: type[db.Record],
    entity: BaseModel,
    excluded: set[str] | None = None,
    additions: dict[str, object] | None = None,
) -> None:
    """Insert an immutable entity or require an identical existing record."""
    values = entity.model_dump(exclude=excluded or set())
    values.update(additions or {})
    identifier = values["id"]
    existing = session.get(model, identifier)
    if existing is not None:
        if any(getattr(existing, key) != value for key, value in values.items()):
            raise ValueError(f"Conflicting immutable entity {identifier}")
        return
    session.add(model(**values))
    session.flush()


def insert_bundle(session: Session, bundle: ReviewBundle, digest: str) -> None:
    """Write validated entities and normalized association records."""
    validate_frozen_collections(session, bundle)
    insert_entity(session, db.AssignmentRecord, bundle.assignment)
    insert_entity(session, db.SubmissionRecord, bundle.submission)
    insert_entity(session, db.PolicyRecord, bundle.policy)
    for requirement in bundle.requirements:
        insert_entity(
            session,
            db.RequirementRecord,
            requirement,
            {"source"},
            {
                "start_line": requirement.source.start_line,
                "end_line": requirement.source.end_line,
            },
        )
    insert_entity(session, db.RubricRecord, bundle.rubric)
    for criterion in bundle.criteria:
        insert_entity(session, db.CriterionRecord, criterion)
    for link in bundle.criterion_requirements:
        key = (link.criterion_id, link.requirement_id)
        if session.get(db.CriterionRequirementRecord, key) is None:
            session.add(
                db.CriterionRequirementRecord(
                    criterion_id=link.criterion_id, requirement_id=link.requirement_id
                )
            )
    for rule in bundle.penalty_rules:
        insert_entity(session, db.PenaltyRuleRecord, rule, {"requirement_ids"})
        for identifier in rule.requirement_ids:
            key = (rule.id, identifier)
            if session.get(db.PenaltyRequirementRecord, key) is None:
                session.add(
                    db.PenaltyRequirementRecord(
                        penalty_rule_id=rule.id, requirement_id=identifier
                    )
                )
    for source in bundle.files:
        insert_entity(session, db.FileRecord, source)
    insert_entity(
        session,
        db.RunRecord,
        bundle.run,
        additions={"content_digest": digest, "is_finalized": False},
    )
    for check in bundle.checks:
        insert_entity(session, db.CheckRecord, check)
    for evidence in bundle.evidence:
        common = evidence.model_dump(
            include={"id", "schema_version", "review_run_id", "kind", "summary"}
        )
        session.add(db.EvidenceRecord(**common))
        session.flush()
        detail = evidence.model_dump(
            exclude={"id", "schema_version", "review_run_id", "kind", "summary", "span"}
        )
        detail["evidence_id"] = evidence.id
        if evidence.kind == "source":
            detail.update(
                start_line=evidence.span.start_line, end_line=evidence.span.end_line
            )
            session.add(db.SourceEvidenceRecord(**detail))
        elif evidence.kind == "check":
            session.add(db.CheckEvidenceRecord(**detail))
        else:
            session.add(db.ObservationRecord(**detail))
    session.flush()
    for assessment in bundle.assessments:
        insert_entity(session, db.AssessmentRecord, assessment, {"evidence_ids"})
        session.add_all(
            [
                db.AssessmentEvidenceRecord(
                    assessment_id=assessment.id, evidence_id=identifier
                )
                for identifier in assessment.evidence_ids
            ]
        )
    for application in bundle.penalty_applications:
        insert_entity(
            session, db.PenaltyApplicationRecord, application, {"evidence_ids"}
        )
        session.add_all(
            [
                db.PenaltyEvidenceRecord(
                    penalty_application_id=application.id, evidence_id=identifier
                )
                for identifier in application.evidence_ids
            ]
        )
    for trace in bundle.trace_events:
        insert_entity(session, db.TraceRecord, trace)
    session.flush()


def validate_frozen_collections(session: Session, bundle: ReviewBundle) -> None:
    """Reject additions or removals beneath previously saved immutable roots."""
    if session.get(db.AssignmentRecord, bundle.assignment.id) is not None:
        existing = set(
            session.scalars(
                select(db.RequirementRecord.id).where(
                    db.RequirementRecord.assignment_id == bundle.assignment.id
                )
            )
        )
        if existing != {item.id for item in bundle.requirements}:
            raise ValueError("Frozen assignment requirement collection differs")
    if session.get(db.SubmissionRecord, bundle.submission.id) is not None:
        existing = set(
            session.scalars(
                select(db.FileRecord.id).where(
                    db.FileRecord.submission_id == bundle.submission.id
                )
            )
        )
        if existing != {item.id for item in bundle.files}:
            raise ValueError("Frozen submission manifest differs")
    if session.get(db.RubricRecord, bundle.rubric.id) is None:
        return
    criteria = set(
        session.scalars(
            select(db.CriterionRecord.id).where(
                db.CriterionRecord.rubric_id == bundle.rubric.id
            )
        )
    )
    rules = set(
        session.scalars(
            select(db.PenaltyRuleRecord.id).where(
                db.PenaltyRuleRecord.rubric_id == bundle.rubric.id
            )
        )
    )
    if criteria != {item.id for item in bundle.criteria} or rules != {
        item.id for item in bundle.penalty_rules
    }:
        raise ValueError("Frozen rubric child collection differs")
    links = set(
        session.execute(
            select(
                db.CriterionRequirementRecord.criterion_id,
                db.CriterionRequirementRecord.requirement_id,
            ).where(db.CriterionRequirementRecord.criterion_id.in_(criteria))
        ).tuples()
    )
    if links != {
        (item.criterion_id, item.requirement_id)
        for item in bundle.criterion_requirements
    }:
        raise ValueError("Frozen criterion source associations differ")
    penalty_links = set(
        session.execute(
            select(
                db.PenaltyRequirementRecord.penalty_rule_id,
                db.PenaltyRequirementRecord.requirement_id,
            ).where(db.PenaltyRequirementRecord.penalty_rule_id.in_(rules))
        ).tuples()
    )
    expected_penalty_links = {
        (item.id, identifier)
        for item in bundle.penalty_rules
        for identifier in item.requirement_ids
    }
    if penalty_links != expected_penalty_links:
        raise ValueError("Frozen penalty source associations differ")


def require_record[T: db.Base](session: Session, model: type[T], identifier: UUID) -> T:
    """Load a required relational entity."""
    record = session.get(model, identifier)
    if record is None:
        raise ValueError(f"Missing {model.__tablename__}: {identifier}")
    return record


def load_bundle(session: Session, run_id: UUID) -> ReviewBundle:
    """Reconstruct a canonical review exclusively from normalized rows."""
    run_row = require_record(session, db.RunRecord, run_id)
    run_values = row_values(run_row)
    run_values.pop("content_digest")
    run_values.pop("is_finalized")
    rubric_row = require_record(session, db.RubricRecord, run_row.rubric_id)
    requirements = []
    for row in session.scalars(
        select(db.RequirementRecord)
        .where(db.RequirementRecord.assignment_id == rubric_row.assignment_id)
        .order_by(db.RequirementRecord.code)
    ):
        values = row_values(row)
        values.pop("start_line")
        values.pop("end_line")
        values["source"] = SourceSpan(start_line=row.start_line, end_line=row.end_line)
        requirements.append(AssignmentRequirement.model_validate(values))
    criteria_rows = list(
        session.scalars(
            select(db.CriterionRecord)
            .where(db.CriterionRecord.rubric_id == rubric_row.id)
            .order_by(db.CriterionRecord.ordinal)
        )
    )
    criteria_ids = [row.id for row in criteria_rows]
    links = [
        CriterionRequirementRef(
            criterion_id=row.criterion_id, requirement_id=row.requirement_id
        )
        for row in session.scalars(
            select(db.CriterionRequirementRecord).where(
                db.CriterionRequirementRecord.criterion_id.in_(criteria_ids)
            )
        )
    ]
    rules = []
    for row in session.scalars(
        select(db.PenaltyRuleRecord).where(
            db.PenaltyRuleRecord.rubric_id == rubric_row.id
        )
    ):
        values = row_values(row)
        values["requirement_ids"] = list(
            session.scalars(
                select(db.PenaltyRequirementRecord.requirement_id).where(
                    db.PenaltyRequirementRecord.penalty_rule_id == row.id
                )
            )
        )
        rules.append(PenaltyRule.model_validate(values))
    evidence: list[Evidence] = []
    from pydantic import TypeAdapter

    adapter = TypeAdapter(Evidence)
    for row in session.scalars(
        select(db.EvidenceRecord).where(db.EvidenceRecord.review_run_id == run_id)
    ):
        values = row_values(row)
        detail_type = {
            "source": db.SourceEvidenceRecord,
            "check": db.CheckEvidenceRecord,
            "observation": db.ObservationRecord,
        }[row.kind]
        detail = row_values(require_record(session, detail_type, row.id))
        detail.pop("evidence_id")
        if row.kind == "source":
            detail["span"] = {
                "start_line": detail.pop("start_line"),
                "end_line": detail.pop("end_line"),
            }
        values.update(detail)
        evidence.append(adapter.validate_python(values))
    assessments = []
    for row in session.scalars(
        select(db.AssessmentRecord).where(db.AssessmentRecord.review_run_id == run_id)
    ):
        values = row_values(row)
        values["evidence_ids"] = list(
            session.scalars(
                select(db.AssessmentEvidenceRecord.evidence_id).where(
                    db.AssessmentEvidenceRecord.assessment_id == row.id
                )
            )
        )
        assessments.append(CriterionAssessment.model_validate(values))
    applications = []
    for row in session.scalars(
        select(db.PenaltyApplicationRecord).where(
            db.PenaltyApplicationRecord.review_run_id == run_id
        )
    ):
        values = row_values(row)
        values["evidence_ids"] = list(
            session.scalars(
                select(db.PenaltyEvidenceRecord.evidence_id).where(
                    db.PenaltyEvidenceRecord.penalty_application_id == row.id
                )
            )
        )
        applications.append(PenaltyApplication.model_validate(values))
    bundle = ReviewBundle(
        assignment=AssignmentDocument.model_validate(
            row_values(
                require_record(session, db.AssignmentRecord, rubric_row.assignment_id)
            )
        ),
        policy=GradingPolicy.model_validate(
            row_values(require_record(session, db.PolicyRecord, run_row.policy_id))
        ),
        submission=SubmissionArchive.model_validate(
            row_values(
                require_record(session, db.SubmissionRecord, run_row.submission_id)
            )
        ),
        rubric=GradingRubric.model_validate(row_values(rubric_row)),
        requirements=requirements,
        criteria=[
            RubricCriterion.model_validate(row_values(row)) for row in criteria_rows
        ],
        criterion_requirements=links,
        penalty_rules=rules,
        files=[
            SubmissionFile.model_validate(row_values(row))
            for row in session.scalars(
                select(db.FileRecord).where(
                    db.FileRecord.submission_id == run_row.submission_id
                )
            )
        ],
        run=run_values,
        checks=[
            CheckExecution.model_validate(row_values(row))
            for row in session.scalars(
                select(db.CheckRecord).where(db.CheckRecord.review_run_id == run_id)
            )
        ],
        evidence=evidence,
        assessments=assessments,
        penalty_applications=applications,
        trace_events=[
            TraceEvent.model_validate(row_values(row))
            for row in session.scalars(
                select(db.TraceRecord)
                .where(db.TraceRecord.review_run_id == run_id)
                .order_by(db.TraceRecord.sequence)
            )
        ],
    )
    return ReviewBundle.model_validate(
        {**bundle.model_dump(), "summary": ScoreCalculator.calculate(bundle)}
    )
