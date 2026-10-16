from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class ExactPoints(TypeDecorator[Decimal]):
    """Exact fixed-point decimals stored as scaled SQLite integers."""

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: object) -> int | None:
        """Encode points as an integer count of ten-thousandths."""
        if value is None:
            return None
        scaled = value * 10000
        if not value.is_finite() or scaled != scaled.to_integral_value():
            raise ValueError("Points require finite precision of at most four places")
        return int(scaled)

    def process_result_value(
        self, value: int | None, dialect: object
    ) -> Decimal | None:
        """Decode exact integer storage without binary floating point."""
        return None if value is None else Decimal(value) / 10000


class UtcTimestamp(TypeDecorator[datetime]):
    """UTC timestamps preserved across SQLite round trips."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        """Store the UTC clock value without SQLite timezone loss."""
        return None if value is None else value.replace(tzinfo=None)

    def process_result_value(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        """Restore the contract's UTC timezone."""
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    """Normalized audit schema metadata."""


class Record(Base):
    """Common identity for independent domain entities."""

    __abstract__ = True
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(8), default="1.0")


class AssignmentRecord(Record):
    """Original assignment document."""

    __tablename__ = "assignment_documents"
    format: Mapped[str]
    original_text: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp)


class RequirementRecord(Record):
    """Atomic source-cited assignment requirement."""

    __tablename__ = "assignment_requirements"
    __table_args__ = (
        UniqueConstraint("assignment_id", "code"),
        CheckConstraint("start_line >= 1 AND end_line >= start_line"),
        CheckConstraint("points IS NULL OR points >= 0"),
        CheckConstraint("necessity IN ('mandatory', 'optional')"),
        CheckConstraint("ambiguity_state IN ('clear', 'ambiguous', 'conflicting')"),
    )
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assignment_documents.id"), index=True
    )
    code: Mapped[str]
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str]
    necessity: Mapped[str]
    ambiguity_state: Mapped[str]
    start_line: Mapped[int]
    end_line: Mapped[int]
    source_quote: Mapped[str] = mapped_column(Text)
    points: Mapped[Decimal | None] = mapped_column(ExactPoints)


class SubmissionRecord(Record):
    """Immutable input ZIP metadata."""

    __tablename__ = "submissions"
    __table_args__ = (CheckConstraint("byte_size >= 0"),)
    archive_name: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UtcTimestamp)


class FileRecord(Record):
    """One unique canonical manifest entry."""

    __tablename__ = "submission_files"
    __table_args__ = (
        UniqueConstraint("submission_id", "relative_path"),
        CheckConstraint("byte_size >= 0"),
        CheckConstraint("line_count IS NULL OR line_count >= 0"),
    )
    submission_id: Mapped[UUID] = mapped_column(
        ForeignKey("submissions.id"), index=True
    )
    relative_path: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int]
    language: Mapped[str | None]
    line_count: Mapped[int | None]


class PolicyRecord(Record):
    """Immutable grading behavior snapshot."""

    __tablename__ = "grading_policies"
    __table_args__ = (
        CheckConstraint("version >= 1"),
        CheckConstraint("max_score IS NULL OR max_score >= 0"),
        CheckConstraint("strictness IN ('lenient', 'balanced', 'strict')"),
        CheckConstraint("code_style IN ('none', 'google', 'llvm', 'custom')"),
        CheckConstraint("feedback_detail IN ('brief', 'detailed', 'educational')"),
    )
    strictness: Mapped[str]
    code_style: Mapped[str]
    custom_style_rules: Mapped[str | None] = mapped_column(Text)
    feedback_detail: Mapped[str]
    check_correctness: Mapped[bool] = mapped_column(Boolean(create_constraint=True))
    check_memory_safety: Mapped[bool] = mapped_column(Boolean(create_constraint=True))
    check_code_quality: Mapped[bool] = mapped_column(Boolean(create_constraint=True))
    check_requirements: Mapped[bool] = mapped_column(Boolean(create_constraint=True))
    run_tests: Mapped[bool] = mapped_column(Boolean(create_constraint=True))
    max_score: Mapped[Decimal | None] = mapped_column(ExactPoints)
    version: Mapped[int]


class RubricRecord(Record):
    """Frozen rubric definition independent of per-run outcomes."""

    __tablename__ = "grading_rubrics"
    __table_args__ = (
        UniqueConstraint("assignment_id", "version"),
        CheckConstraint("version >= 1"),
        CheckConstraint("scoring_mode IN ('UNSCORED', 'POINTS')"),
        CheckConstraint("status = 'FROZEN'"),
        CheckConstraint("maximum_base_points IS NULL OR maximum_base_points > 0"),
        CheckConstraint("grade_cap IS NULL OR grade_cap >= 0"),
        CheckConstraint("bonus_policy IN ('NONE', 'ADD')"),
    )
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("assignment_documents.id"), index=True
    )
    version: Mapped[int]
    scoring_mode: Mapped[str]
    status: Mapped[str]
    maximum_base_points: Mapped[Decimal | None] = mapped_column(ExactPoints)
    bonus_policy: Mapped[str]
    grade_cap: Mapped[Decimal | None] = mapped_column(ExactPoints)
    grade_cap_requirement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assignment_requirements.id")
    )
    needs_clarification: Mapped[bool] = mapped_column(Boolean(create_constraint=True))


class CriterionRecord(Record):
    """Ordered rubric criterion with source-backed weight."""

    __tablename__ = "rubric_criteria"
    __table_args__ = (
        UniqueConstraint("rubric_id", "code"),
        UniqueConstraint("rubric_id", "ordinal"),
        CheckConstraint("ordinal >= 1"),
        CheckConstraint("role IN ('CORE', 'BONUS', 'ADVISORY')"),
        CheckConstraint("max_points IS NULL OR max_points > 0"),
        CheckConstraint("role != 'ADVISORY' OR max_points IS NULL"),
    )
    rubric_id: Mapped[UUID] = mapped_column(
        ForeignKey("grading_rubrics.id"), index=True
    )
    code: Mapped[str]
    ordinal: Mapped[int]
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str]
    role: Mapped[str]
    verification_method: Mapped[str]
    max_points: Mapped[Decimal | None] = mapped_column(ExactPoints)


class CriterionRequirementRecord(Base):
    """Many-to-many rubric source relationship."""

    __tablename__ = "criterion_requirements"
    criterion_id: Mapped[UUID] = mapped_column(
        ForeignKey("rubric_criteria.id"), primary_key=True
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("assignment_requirements.id"), primary_key=True
    )


class PenaltyRuleRecord(Record):
    """Explicit once-per-run deduction definition."""

    __tablename__ = "penalty_rules"
    __table_args__ = (
        UniqueConstraint("rubric_id", "code"),
        CheckConstraint("amount >= 0"),
        CheckConstraint("repeat_policy = 'ONCE'"),
    )
    rubric_id: Mapped[UUID] = mapped_column(
        ForeignKey("grading_rubrics.id"), index=True
    )
    code: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(ExactPoints)
    trigger: Mapped[str]
    repeat_policy: Mapped[str]


class PenaltyRequirementRecord(Base):
    """Penalty rule sources without repeated requirement text."""

    __tablename__ = "penalty_rule_requirements"
    penalty_rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("penalty_rules.id"), primary_key=True
    )
    requirement_id: Mapped[UUID] = mapped_column(
        ForeignKey("assignment_requirements.id"), primary_key=True
    )


class RunRecord(Record):
    """Review identity and recoverable cross-resource finalization metadata."""

    __tablename__ = "review_runs"
    __table_args__ = (
        CheckConstraint("strategy IN ('MULTI_AGENT', 'SINGLE_AGENT_BASELINE')"),
        CheckConstraint(
            "state IN ('CREATED', 'RUNNING', 'COMPLETED', 'NEEDS_REVIEW', 'FAILED')"
        ),
    )
    submission_id: Mapped[UUID] = mapped_column(
        ForeignKey("submissions.id"), index=True
    )
    rubric_id: Mapped[UUID] = mapped_column(
        ForeignKey("grading_rubrics.id"), index=True
    )
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("grading_policies.id"), index=True
    )
    strategy: Mapped[str]
    state: Mapped[str]
    started_at: Mapped[datetime] = mapped_column(UtcTimestamp)
    finished_at: Mapped[datetime | None] = mapped_column(UtcTimestamp)
    content_digest: Mapped[str] = mapped_column(String(64))
    is_finalized: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True), default=False
    )


class CheckRecord(Record):
    """Bounded execution attempt independent of grading decisions."""

    __tablename__ = "check_executions"
    __table_args__ = (
        CheckConstraint("duration_ms >= 0"),
        CheckConstraint(
            "status IN ('PASSED', 'FAILED', 'SKIPPED', "
            "'UNAVAILABLE', 'TIMEOUT', 'ERROR')"
        ),
        CheckConstraint("kind IN ('compile', 'tests', 'static', 'memory')"),
    )
    review_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_runs.id"), index=True
    )
    kind: Mapped[str]
    status: Mapped[str]
    tool_name: Mapped[str]
    exit_code: Mapped[int | None]
    duration_ms: Mapped[int]
    bounded_stdout: Mapped[str] = mapped_column(Text)
    bounded_stderr: Mapped[str] = mapped_column(Text)
    environment_digest: Mapped[str]
    reason: Mapped[str | None]


class EvidenceRecord(Record):
    """Common evidence identity and run membership."""

    __tablename__ = "evidence"
    __table_args__ = (CheckConstraint("kind IN ('source', 'check', 'observation')"),)
    review_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_runs.id"), index=True
    )
    kind: Mapped[str]
    summary: Mapped[str] = mapped_column(Text)


class SourceEvidenceRecord(Base):
    """One source-file evidence detail record."""

    __tablename__ = "source_file_evidence"
    __table_args__ = (CheckConstraint("start_line >= 1 AND end_line >= start_line"),)
    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence.id"), primary_key=True
    )
    submission_file_id: Mapped[UUID] = mapped_column(ForeignKey("submission_files.id"))
    start_line: Mapped[int]
    end_line: Mapped[int]
    verified_excerpt: Mapped[str] = mapped_column(Text)


class CheckEvidenceRecord(Base):
    """One execution-linked diagnostic detail record."""

    __tablename__ = "check_evidence"
    __table_args__ = (
        CheckConstraint("start_offset >= 0 AND end_offset > start_offset"),
        CheckConstraint("diagnostic_stream IN ('stdout', 'stderr')"),
    )
    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence.id"), primary_key=True
    )
    check_execution_id: Mapped[UUID] = mapped_column(ForeignKey("check_executions.id"))
    diagnostic_stream: Mapped[str]
    start_offset: Mapped[int]
    end_offset: Mapped[int]
    diagnostic: Mapped[str] = mapped_column(Text)
    exit_code: Mapped[int]


class ObservationRecord(Base):
    """One manifest-derived observable fact."""

    __tablename__ = "observation_evidence"
    __table_args__ = (
        CheckConstraint("observation IN ('file_absent', 'file_present')"),
    )
    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence.id"), primary_key=True
    )
    observation: Mapped[str]
    relative_path: Mapped[str]
    provenance_description: Mapped[str]


class AssessmentRecord(Record):
    """Exactly one criterion decision per run."""

    __tablename__ = "criterion_assessments"
    __table_args__ = (
        UniqueConstraint("review_run_id", "criterion_id"),
        CheckConstraint("status IN ('PASS', 'PARTIAL', 'FAIL', 'NOT_VERIFIABLE')"),
        CheckConstraint("awarded_points IS NULL OR awarded_points >= 0"),
        CheckConstraint(
            "status != 'NOT_VERIFIABLE' OR "
            "(awarded_points IS NULL AND not_verifiable_reason IS NOT NULL)"
        ),
    )
    review_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_runs.id"), index=True
    )
    criterion_id: Mapped[UUID] = mapped_column(ForeignKey("rubric_criteria.id"))
    status: Mapped[str]
    explanation: Mapped[str] = mapped_column(Text)
    not_verifiable_reason: Mapped[str | None]
    awarded_points: Mapped[Decimal | None] = mapped_column(ExactPoints)
    recommendations: Mapped[str] = mapped_column(Text)


class AssessmentEvidenceRecord(Base):
    """Many-to-many assessment evidence relationship."""

    __tablename__ = "assessment_evidence"
    assessment_id: Mapped[UUID] = mapped_column(
        ForeignKey("criterion_assessments.id"), primary_key=True
    )
    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence.id"), primary_key=True
    )


class PenaltyApplicationRecord(Record):
    """Unique evidence-backed rule application per run."""

    __tablename__ = "penalty_applications"
    __table_args__ = (
        UniqueConstraint("review_run_id", "penalty_rule_id"),
        CheckConstraint("applied_amount >= 0"),
    )
    review_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_runs.id"), index=True
    )
    penalty_rule_id: Mapped[UUID] = mapped_column(ForeignKey("penalty_rules.id"))
    applied_amount: Mapped[Decimal] = mapped_column(ExactPoints)
    explanation: Mapped[str] = mapped_column(Text)


class PenaltyEvidenceRecord(Base):
    """Many-to-many penalty evidence relationship."""

    __tablename__ = "penalty_application_evidence"
    penalty_application_id: Mapped[UUID] = mapped_column(
        ForeignKey("penalty_applications.id"), primary_key=True
    )
    evidence_id: Mapped[UUID] = mapped_column(
        ForeignKey("evidence.id"), primary_key=True
    )


class ArtifactRecord(Record):
    """Finalized report path and content checksum."""

    __tablename__ = "review_artifacts"
    __table_args__ = (
        UniqueConstraint("review_run_id", "format"),
        CheckConstraint("format IN ('json', 'markdown')"),
    )
    review_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_runs.id"), index=True
    )
    format: Mapped[str]
    relative_path: Mapped[str]
    sha256: Mapped[str] = mapped_column(String(64))


class TraceRecord(Record):
    """Chronological bounded local audit event."""

    __tablename__ = "trace_events"
    __table_args__ = (
        UniqueConstraint("review_run_id", "sequence"),
        CheckConstraint("sequence >= 1"),
    )
    review_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_runs.id"), index=True
    )
    sequence: Mapped[int]
    agent_role: Mapped[str]
    event_type: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(UtcTimestamp)
    detail: Mapped[str] = mapped_column(Text)
