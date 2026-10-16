from decimal import Decimal
from uuid import UUID

from ta_mcp.domain import (
    AssignmentDocument,
    CheckEvidence,
    CheckStatus,
    CriterionRole,
    CriterionStatus,
    Entity,
    ObservationEvidence,
    ReviewBundle,
    RubricAnalysis,
    RunState,
    ScoringMode,
    SourceFileEvidence,
    source_has_points,
)
from ta_mcp.scoring import ScoreCalculator


def index_entities[T: Entity](entities: list[T]) -> dict[UUID, T]:
    """Index entities and reject duplicated identities."""
    indexed = {entity.id: entity for entity in entities}
    if len(indexed) != len(entities):
        raise ValueError("Duplicate entity ID")
    return indexed


def require_unique(values: list[object], label: str) -> None:
    """Reject duplicated natural keys and association links."""
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


def validate_analysis(assignment: AssignmentDocument, analysis: RubricAnalysis) -> None:
    """Validate source citations, rubric allocation, and assignment membership."""
    requirements = index_entities(analysis.requirements)
    criteria = index_entities(analysis.criteria)
    rules = index_entities(analysis.penalty_rules)
    rubric = analysis.rubric
    if rubric.assignment_id != assignment.id:
        raise ValueError("Rubric references another assignment")
    lines = assignment.original_text.splitlines()
    for requirement in requirements.values():
        span = requirement.source
        if requirement.assignment_id != assignment.id or span.end_line > len(lines):
            raise ValueError(
                "Requirement references another assignment or invalid lines"
            )
        quote = "\n".join(lines[span.start_line - 1 : span.end_line])
        if quote != requirement.source_quote:
            raise ValueError("Requirement source quote does not match assignment lines")
        if requirement.points is not None and not source_has_points(
            quote, requirement.points
        ):
            raise ValueError("Point amount is not explicitly present in source quote")
    require_unique([item.code for item in requirements.values()], "requirement code")
    require_unique([item.code for item in criteria.values()], "criterion code")
    require_unique([item.ordinal for item in criteria.values()], "criterion ordinal")
    require_unique([item.code for item in rules.values()], "penalty code")
    links: dict[UUID, list[UUID]] = {identifier: [] for identifier in criteria}
    for link in analysis.criterion_requirements:
        if link.criterion_id not in criteria or link.requirement_id not in requirements:
            raise ValueError("Unknown criterion/source requirement link")
        links[link.criterion_id].append(link.requirement_id)
    require_unique(
        [
            (link.criterion_id, link.requirement_id)
            for link in analysis.criterion_requirements
        ],
        "criterion requirement link",
    )
    allocated_requirements: list[object] = []
    for criterion in criteria.values():
        if criterion.rubric_id != rubric.id or not links[criterion.id]:
            raise ValueError("Criterion must belong to this rubric and cite source")
        cited = [requirements[identifier] for identifier in links[criterion.id]]
        if any(item.ambiguity_state != "clear" for item in cited):
            if not rubric.needs_clarification or criterion.max_points is not None:
                raise ValueError(
                    "Ambiguous requirements need clarification, not weights"
                )
        if criterion.role == CriterionRole.ADVISORY:
            if criterion.max_points is not None:
                raise ValueError("ADVISORY cannot carry points")
        elif rubric.scoring_mode == ScoringMode.POINTS:
            sources = [item for item in cited if item.points is not None]
            if not sources or criterion.max_points is None or criterion.max_points <= 0:
                raise ValueError("Criterion lacks a positive source-backed allocation")
            if (
                sum(
                    (item.points for item in sources if item.points is not None),
                    Decimal(0),
                )
                != criterion.max_points
            ):
                raise ValueError("Criterion weight disagrees with cited allocation")
            allocated_requirements.extend(item.id for item in sources)
            if criterion.role == CriterionRole.BONUS and not any(
                item.necessity == "optional" for item in sources
            ):
                raise ValueError("Bonus points require an optional source requirement")
        elif criterion.max_points is not None:
            raise ValueError("UNSCORED rubric cannot invent weights")
    require_unique(allocated_requirements, "point allocation across criteria")
    if rubric.scoring_mode == ScoringMode.UNSCORED:
        if (
            rubric.maximum_base_points is not None
            or rubric.grade_cap is not None
            or rules
        ):
            raise ValueError("UNSCORED rubric cannot contain numeric rules")
    else:
        core_total = sum(
            (
                item.max_points
                for item in criteria.values()
                if item.role == CriterionRole.CORE and item.max_points is not None
            ),
            Decimal(0),
        )
        if core_total <= 0 or rubric.maximum_base_points != core_total:
            raise ValueError("Rubric base total disagrees with core allocation")
        has_bonus = any(item.role == CriterionRole.BONUS for item in criteria.values())
        if has_bonus != (rubric.bonus_policy == "ADD"):
            raise ValueError("Bonus handling must explicitly match bonus criteria")
    if rubric.grade_cap is not None:
        cap_source = requirements.get(rubric.grade_cap_requirement_id)
        if cap_source is None or cap_source.points != rubric.grade_cap:
            raise ValueError("Grade cap requires an explicit cited source amount")
    elif rubric.grade_cap_requirement_id is not None:
        raise ValueError("Cap source without a cap")
    for rule in rules.values():
        if rule.rubric_id != rubric.id:
            raise ValueError("Penalty rule belongs to another rubric")
        require_unique(list(rule.requirement_ids), "penalty source")
        if any(identifier not in requirements for identifier in rule.requirement_ids):
            raise ValueError("Penalty source is unknown")
        if not any(
            requirements[identifier].kind == "scoring"
            and requirements[identifier].ambiguity_state == "clear"
            and source_has_points(requirements[identifier].source_quote, rule.amount)
            for identifier in rule.requirement_ids
        ):
            raise ValueError("Penalty amount needs an explicit scoring source")


def validate_bundle(bundle: ReviewBundle) -> None:
    """Reject dangling references, invented evidence, and inconsistent scoring."""
    bundle.files.sort(key=lambda item: item.relative_path)
    bundle.checks.sort(key=lambda item: str(item.id))
    bundle.evidence.sort(key=lambda item: str(item.id))
    bundle.assessments.sort(key=lambda item: str(item.criterion_id))
    bundle.penalty_applications.sort(key=lambda item: str(item.id))
    for item in [*bundle.assessments, *bundle.penalty_applications]:
        item.evidence_ids.sort(key=str)
    validate_analysis(bundle.assignment, bundle)
    run = bundle.run
    if (
        run.rubric_id != bundle.rubric.id
        or run.policy_id != bundle.policy.id
        or run.submission_id != bundle.submission.id
    ):
        raise ValueError("Run references the wrong rubric, policy, or submission")
    files = index_entities(bundle.files)
    checks = index_entities(bundle.checks)
    evidence = index_entities(bundle.evidence)
    assessments = index_entities(bundle.assessments)
    applications = index_entities(bundle.penalty_applications)
    traces = index_entities(bundle.trace_events)
    require_unique([item.relative_path for item in files.values()], "submission path")
    for item in files.values():
        if item.submission_id != bundle.submission.id:
            raise ValueError("File belongs to another submission")
    for item in [
        *checks.values(),
        *evidence.values(),
        *assessments.values(),
        *applications.values(),
        *traces.values(),
    ]:
        if item.review_run_id != run.id:
            raise ValueError("Cross-run record reference")
    paths = {item.relative_path for item in files.values()}
    for item in evidence.values():
        if isinstance(item, SourceFileEvidence):
            source = files.get(item.submission_file_id)
            if source is None or source.line_count is None:
                raise ValueError("Source evidence references an unknown or binary file")
            if item.span.end_line > source.line_count:
                raise ValueError("Source evidence line range does not exist")
            if len(item.verified_excerpt.splitlines()) != (
                item.span.end_line - item.span.start_line + 1
            ):
                raise ValueError("Source excerpt line count disagrees with its span")
        elif isinstance(item, CheckEvidence):
            check = checks.get(item.check_execution_id)
            if check is None or check.status not in {
                CheckStatus.PASSED,
                CheckStatus.FAILED,
            }:
                raise ValueError("Evidence requires an actual executed check")
            output = (
                check.bounded_stdout
                if item.diagnostic_stream == "stdout"
                else check.bounded_stderr
            )
            if (
                item.end_offset > len(output)
                or item.start_offset >= item.end_offset
                or output[item.start_offset : item.end_offset] != item.diagnostic
                or item.exit_code != check.exit_code
            ):
                raise ValueError("Diagnostic evidence disagrees with captured output")
        elif isinstance(item, ObservationEvidence):
            is_present = item.relative_path in paths
            if is_present != (item.observation == "file_present"):
                raise ValueError("Observable fact disagrees with archive manifest")
    require_unique([item.criterion_id for item in assessments.values()], "assessment")
    criterion_ids = {criterion.id for criterion in bundle.criteria}
    if {item.criterion_id for item in assessments.values()} != criterion_ids:
        raise ValueError("Every rubric criterion needs exactly one assessment")
    for item in assessments.values():
        require_unique(list(item.evidence_ids), "assessment evidence")
        if any(identifier not in evidence for identifier in item.evidence_ids):
            raise ValueError("Assessment evidence is unknown")
        if item.status != CriterionStatus.NOT_VERIFIABLE and not item.evidence_ids:
            raise ValueError("Verifiable decisions require supporting evidence")
        if item.status == CriterionStatus.PASS and not any(
            isinstance(evidence[identifier], (SourceFileEvidence, CheckEvidence))
            for identifier in item.evidence_ids
        ):
            raise ValueError("PASS requires source or executed-check evidence")
    rules = {rule.id: rule for rule in bundle.penalty_rules}
    require_unique([item.penalty_rule_id for item in applications.values()], "penalty")
    for item in applications.values():
        rule = rules.get(item.penalty_rule_id)
        if rule is None or item.applied_amount != rule.amount:
            raise ValueError("Penalty application disagrees with its rule")
        require_unique(list(item.evidence_ids), "penalty evidence")
        if any(identifier not in evidence for identifier in item.evidence_ids):
            raise ValueError("Penalty evidence is unknown")
    require_unique([item.sequence for item in traces.values()], "trace sequence")
    if [item.sequence for item in bundle.trace_events] != sorted(
        item.sequence for item in bundle.trace_events
    ):
        raise ValueError("Trace events must be ordered")
    if (
        any(
            item.status == CriterionStatus.NOT_VERIFIABLE
            for item in assessments.values()
        )
        or bundle.rubric.needs_clarification
    ):
        if run.state == RunState.COMPLETED:
            raise ValueError("Unresolved review must be marked NEEDS_REVIEW")
    summary = ScoreCalculator.calculate(bundle)
    if bundle.summary is not None and bundle.summary != summary:
        raise ValueError("Submitted score summary disagrees with computed totals")
