import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


def reject_float(value: object) -> object:
    """Reject binary floating point at the grading boundary."""
    if isinstance(value, (float, bool)):
        raise ValueError("Points must be decimal strings or integers")
    return value


Points = Annotated[
    Decimal,
    BeforeValidator(reject_float),
    Field(ge=0, max_digits=16, decimal_places=4, allow_inf_nan=False),
]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Nonempty = Annotated[str, Field(min_length=1, max_length=12000)]


def canonical_path(value: str) -> str:
    """Validate an unambiguous relative POSIX archive path."""
    path = PurePosixPath(value)
    if (
        not value
        or "\x00" in value
        or "\\" in value
        or ":" in value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or str(path) != value
    ):
        raise ValueError("Expected a canonical relative POSIX path")
    return value


class Contract(BaseModel):
    """Versioned, closed data contract."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
    schema_version: Literal["1.0"] = "1.0"

    @field_serializer("*", when_used="json")
    def serialize_decimal(self, value: object) -> object:
        """Emit canonical decimal strings independent of storage scale."""
        if isinstance(value, Decimal):
            return format(value.normalize(), "f")
        return value

    @field_validator("*")
    @classmethod
    def validate_utc(cls, value: object) -> object:
        """Require timezone-aware UTC timestamps."""
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
                raise ValueError("Timestamps must use UTC")
        return value


class Entity(Contract):
    """Identified record within a portable review."""

    id: UUID = Field(default_factory=uuid4, description="Stable entity identifier")


class CriterionStatus(StrEnum):
    """Assessment truth states."""

    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class CheckStatus(StrEnum):
    """Execution outcomes, including unavailable environments."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class ScoringMode(StrEnum):
    """Authorized scoring modes."""

    UNSCORED = "UNSCORED"
    POINTS = "POINTS"


class CriterionRole(StrEnum):
    """Core, bonus, or qualitative criterion purpose."""

    CORE = "CORE"
    BONUS = "BONUS"
    ADVISORY = "ADVISORY"


class RunState(StrEnum):
    """Review lifecycle states."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class RunStrategy(StrEnum):
    """Runtime agent strategy recorded for audit."""

    MULTI_AGENT = "MULTI_AGENT"
    SINGLE_AGENT_BASELINE = "SINGLE_AGENT_BASELINE"


class SourceSpan(Contract):
    """Inclusive line span in an assignment or source file."""

    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        """Reject reversed line ranges."""
        if self.end_line < self.start_line:
            raise ValueError("Line range is reversed")
        return self


class AssignmentDocument(Entity):
    """Original assignment text and immutable provenance."""

    format: Literal["markdown", "text"] = "markdown"
    original_text: str = Field(min_length=1, max_length=100000)
    sha256: Digest
    provenance: Nonempty = "user-supplied assignment"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_text(cls, text: str, provenance: str = "user-supplied assignment") -> Self:
        """Create a document with a digest of its exact UTF-8 text."""
        return cls(
            original_text=text,
            sha256=hashlib.sha256(text.encode()).hexdigest(),
            provenance=provenance,
        )

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        """Verify the document digest."""
        if hashlib.sha256(self.original_text.encode()).hexdigest() != self.sha256:
            raise ValueError("Assignment digest mismatch")
        return self


class AssignmentRequirement(Entity):
    """Atomic requirement grounded in an exact assignment quote."""

    assignment_id: UUID
    code: Nonempty
    text: Nonempty
    kind: Literal["functional", "quality", "constraint", "scoring"] = "functional"
    necessity: Literal["mandatory", "optional"] = "mandatory"
    ambiguity_state: Literal["clear", "ambiguous", "conflicting"] = "clear"
    source: SourceSpan
    source_quote: Nonempty
    points: Points | None = None


class SubmissionArchive(Entity):
    """Immutable archive metadata without student identity."""

    archive_name: Nonempty
    sha256: Digest
    byte_size: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SubmissionFile(Entity):
    """Canonical manifest entry in exactly one archive."""

    submission_id: UUID
    relative_path: str
    sha256: Digest
    byte_size: int = Field(ge=0)
    language: str | None = None
    line_count: int | None = Field(default=None, ge=0)

    @field_validator("relative_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Validate the archive-relative filename."""
        return canonical_path(value)


class FileContent(Contract):
    """Bounded UTF-8 content returned by archive inspection."""

    submission_file_id: UUID
    text: str = Field(max_length=65536)
    is_truncated: bool = False


class ArchiveInspection(Contract):
    """Read-only archive manifest and requested text previews."""

    submission: SubmissionArchive
    files: list[SubmissionFile] = Field(max_length=1000)
    contents: list[FileContent] = Field(default_factory=list, max_length=1000)
    languages: list[str] = Field(default_factory=list)
    build_systems: list[str] = Field(default_factory=list)


class GradingPolicy(Entity):
    """Analysis preferences independent of source-defined point weights."""

    strictness: Literal["lenient", "balanced", "strict"] = "balanced"
    code_style: Literal["none", "google", "llvm", "custom"] = "none"
    custom_style_rules: str | None = Field(default=None, max_length=12000)
    feedback_detail: Literal["brief", "detailed", "educational"] = "detailed"
    check_correctness: bool = True
    check_memory_safety: bool = False
    check_code_quality: bool = True
    check_requirements: bool = True
    run_tests: bool = True
    max_score: Points | None = None
    version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_custom_style(self) -> Self:
        """Require rules when custom style is requested."""
        if self.code_style == "custom" and not self.custom_style_rules:
            raise ValueError("Custom style requires custom_style_rules")
        return self


class GradingRubric(Entity):
    """Frozen source-derived allocation and explicit bonus/cap policy."""

    assignment_id: UUID
    version: int = Field(default=1, ge=1)
    scoring_mode: ScoringMode = ScoringMode.UNSCORED
    status: Literal["FROZEN"] = "FROZEN"
    maximum_base_points: Points | None = None
    bonus_policy: Literal["NONE", "ADD"] = "NONE"
    grade_cap: Points | None = None
    grade_cap_requirement_id: UUID | None = None
    needs_clarification: bool = False


class RubricCriterion(Entity):
    """Independently assessable rubric item."""

    rubric_id: UUID
    code: Nonempty
    ordinal: int = Field(ge=1)
    title: Nonempty
    description: Nonempty
    category: Literal["correctness", "requirements", "quality", "memory", "tests"]
    role: CriterionRole = CriterionRole.CORE
    verification_method: Nonempty
    max_points: Points | None = None


class CriterionRequirementRef(Contract):
    """Many-to-many source binding for a criterion."""

    criterion_id: UUID
    requirement_id: UUID


class PenaltyRule(Entity):
    """Explicitly sourced, once-per-run deduction rule."""

    rubric_id: UUID
    code: Nonempty
    description: Nonempty
    amount: Points
    trigger: Nonempty
    requirement_ids: list[UUID] = Field(min_length=1, max_length=200)
    repeat_policy: Literal["ONCE"] = "ONCE"


class RubricAnalysis(Contract):
    """Structured Requirements Analyst handoff with normalized references."""

    requirements: list[AssignmentRequirement] = Field(min_length=1, max_length=200)
    rubric: GradingRubric
    criteria: list[RubricCriterion] = Field(min_length=1, max_length=200)
    criterion_requirements: list[CriterionRequirementRef] = Field(max_length=40000)
    penalty_rules: list[PenaltyRule] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def normalize_order(self) -> Self:
        """Use identical collection order before freezing and after exporting."""
        self.requirements.sort(key=lambda item: item.code)
        self.criteria.sort(key=lambda item: item.ordinal)
        self.criterion_requirements.sort(
            key=lambda item: (str(item.criterion_id), str(item.requirement_id))
        )
        self.penalty_rules.sort(key=lambda item: str(item.id))
        for rule in self.penalty_rules:
            rule.requirement_ids.sort(key=str)
        return self


class ReviewRun(Entity):
    """One immutable submission, rubric, and policy evaluation."""

    submission_id: UUID
    rubric_id: UUID
    policy_id: UUID
    strategy: RunStrategy = RunStrategy.MULTI_AGENT
    state: RunState = RunState.CREATED
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        """Reject reversed lifecycle timestamps."""
        if self.finished_at and self.finished_at < self.started_at:
            raise ValueError("Review cannot finish before it starts")
        return self


class CheckExecution(Entity):
    """Actual bounded tool result, including nonexecution reasons."""

    review_run_id: UUID
    kind: Literal["compile", "tests", "static", "memory"]
    status: CheckStatus
    tool_name: Nonempty
    exit_code: int | None = None
    duration_ms: int = Field(default=0, ge=0)
    bounded_stdout: str = Field(default="", max_length=16000)
    bounded_stderr: str = Field(default="", max_length=16000)
    environment_digest: Nonempty
    reason: Nonempty | None = None

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        """Keep unavailable results distinct from executed checks."""
        if self.status in {CheckStatus.PASSED, CheckStatus.FAILED}:
            if self.exit_code is None:
                raise ValueError("Executed checks require an exit code")
            if (self.status == CheckStatus.PASSED) != (self.exit_code == 0):
                raise ValueError("Exit code disagrees with check status")
        elif self.exit_code is not None or not self.reason:
            raise ValueError("Nonexecuted checks need a reason and no exit code")
        return self


class EvidenceBase(Entity):
    """Shared identity and provenance for a typed observation."""

    review_run_id: UUID
    summary: Nonempty


class SourceFileEvidence(EvidenceBase):
    """Exact inspected source excerpt supporting an assessment."""

    kind: Literal["source"] = "source"
    submission_file_id: UUID
    span: SourceSpan
    verified_excerpt: Nonempty


class CheckEvidence(EvidenceBase):
    """Exact diagnostic substring from a captured execution."""

    kind: Literal["check"] = "check"
    check_execution_id: UUID
    diagnostic_stream: Literal["stdout", "stderr"]
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    diagnostic: Nonempty
    exit_code: int


class ObservationEvidence(EvidenceBase):
    """Manifest-observable fact, never an invented execution claim."""

    kind: Literal["observation"] = "observation"
    observation: Literal["file_absent", "file_present"]
    relative_path: str
    provenance_description: Literal["inspected archive manifest"] = (
        "inspected archive manifest"
    )

    @field_validator("relative_path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Validate the observed relative filename."""
        return canonical_path(value)


Evidence = Annotated[
    SourceFileEvidence | CheckEvidence | ObservationEvidence,
    Field(discriminator="kind"),
]


class CriterionAssessment(Entity):
    """Evidence-linked decision for exactly one rubric criterion."""

    review_run_id: UUID
    criterion_id: UUID
    status: CriterionStatus
    explanation: Nonempty
    not_verifiable_reason: Nonempty | None = None
    awarded_points: Points | None = None
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    recommendations: str = Field(default="", max_length=12000)

    @model_validator(mode="after")
    def validate_reason(self) -> Self:
        """Require an explicit explanation of unverifiability."""
        if self.status == CriterionStatus.NOT_VERIFIABLE:
            if not self.not_verifiable_reason or self.awarded_points is not None:
                raise ValueError("NOT_VERIFIABLE requires a reason and null points")
        elif self.not_verifiable_reason is not None:
            raise ValueError("Only NOT_VERIFIABLE accepts an unverifiability reason")
        return self


class PenaltyApplication(Entity):
    """One evidence-backed use of an authorized deduction rule."""

    review_run_id: UUID
    penalty_rule_id: UUID
    applied_amount: Points
    explanation: Nonempty
    evidence_ids: list[UUID] = Field(min_length=1, max_length=1000)


class GradingDecisions(Contract):
    """Structured Submission Grader output without trusted totals."""

    evidence: list[Evidence] = Field(default_factory=list, max_length=1000)
    assessments: list[CriterionAssessment] = Field(max_length=200)
    penalty_applications: list[PenaltyApplication] = Field(
        default_factory=list, max_length=50
    )


class ReviewSummary(Contract):
    """Deterministically calculated recommendation and uncertainty bounds."""

    known_points: Points | None = None
    base_points: Points | None = None
    bonus_points: Points | None = None
    penalty_points: Points | None = None
    unresolved_criterion_ids: list[UUID] = Field(default_factory=list)
    minimum_possible_score: Points | None = None
    maximum_possible_score: Points | None = None
    recommended_score: Points | None = None


class TraceEvent(Entity):
    """Bounded chronological audit event without secrets or full prompts."""

    review_run_id: UUID
    sequence: int = Field(ge=1)
    agent_role: Literal["analyst", "grader", "orchestrator", "baseline"]
    event_type: Literal[
        "agent_start",
        "agent_result",
        "mcp_call",
        "mcp_result",
        "handoff",
        "error",
        "decision",
    ]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    detail: str = Field(max_length=4000)


class ReviewArtifact(Entity):
    """Checksum and relative path of a finalized report."""

    review_run_id: UUID
    format: Literal["json", "markdown"]
    relative_path: str
    sha256: Digest


class ReviewBundle(RubricAnalysis):
    """Canonical portable review containing collections and ID references."""

    assignment: AssignmentDocument
    policy: GradingPolicy
    submission: SubmissionArchive
    files: list[SubmissionFile] = Field(default_factory=list, max_length=1000)
    run: ReviewRun
    checks: list[CheckExecution] = Field(default_factory=list, max_length=20)
    evidence: list[Evidence] = Field(default_factory=list, max_length=1000)
    assessments: list[CriterionAssessment] = Field(max_length=200)
    penalty_applications: list[PenaltyApplication] = Field(
        default_factory=list, max_length=50
    )
    trace_events: list[TraceEvent] = Field(default_factory=list, max_length=500)
    summary: ReviewSummary | None = None

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        """Validate all entity links and recompute supplied scoring totals."""
        from ta_mcp.validation import validate_bundle

        validate_bundle(self)
        return self


def source_has_points(quote: str, points: Decimal) -> bool:
    """Recognize inline amounts or a cited Markdown points column.

    Args:
        quote: Exact source excerpt including a table header when needed.
        points: Explicit allocation to find in text or the final cited table row.

    Returns:
        Whether the source explicitly contains the requested allocation.
    """
    amounts = re.findall(
        r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*(?:points?\b|pts?\b|бал\w*)", quote, re.I
    )
    if any(Decimal(amount.replace(",", ".")) == points for amount in amounts):
        return True
    rows = [
        [cell.strip().strip("`*") for cell in line.strip().strip("|").split("|")]
        for line in quote.splitlines()
        if line.strip().startswith("|")
    ]
    if len(rows) < 3:
        return False
    return any(
        re.fullmatch(r"бали?|балів|points?|pts?", label, re.I)
        and index < len(rows[-1])
        and re.fullmatch(r"\d+(?:[.,]\d+)?", rows[-1][index])
        and Decimal(rows[-1][index].replace(",", ".")) == points
        for index, label in enumerate(rows[0])
    )
