import hashlib
import json
from html import escape

from ta_mcp.domain import ReviewBundle
from ta_mcp.scoring import ScoreCalculator


def render_json(bundle: ReviewBundle) -> str:
    """Render canonical portable JSON with exact decimal strings."""
    return (
        json.dumps(
            bundle.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
        )
        + "\n"
    )


def content_digest(content: str) -> str:
    """Hash exact UTF-8 report bytes."""
    return hashlib.sha256(content.encode()).hexdigest()


def markdown_cell(text: object) -> str:
    """Escape untrusted content for a Markdown table cell."""
    return escape(str(text)).replace("|", "\\|").replace("\n", " ")


def render_markdown(bundle: ReviewBundle) -> str:
    """Project the same validated decisions into a human-readable report."""
    summary = ScoreCalculator.calculate(bundle)
    criteria = {item.id: item for item in bundle.criteria}
    files = {item.id: item.relative_path for item in bundle.files}
    lines = [
        "# Lab review",
        "",
        "Recommendation for human confirmation. This is not an official grade.",
        "",
        f"Run: `{bundle.run.id}`",
        f"State: **{bundle.run.state}**",
        f"Assignment SHA-256: `{bundle.assignment.sha256}`",
        f"Submission SHA-256: `{bundle.submission.sha256}`",
        "",
    ]
    if summary.known_points is None:
        lines += [
            "Numeric scoring: **UNSCORED**. No authorized allocation is available.",
            "",
        ]
    else:
        recommendation = (
            summary.recommended_score
            if summary.recommended_score is not None
            else "pending verification"
        )
        lines += [
            f"Known earned points: {summary.known_points}",
            f"Base: {summary.base_points}; bonus: {summary.bonus_points}; "
            f"penalties: {summary.penalty_points}",
            f"Possible score: {summary.minimum_possible_score} "
            f"to {summary.maximum_possible_score}",
            f"Recommended score: {recommendation}",
            "",
        ]
    lines += [
        "| Criterion | Status | Points | Explanation |",
        "| --- | --- | --- | --- |",
    ]
    for assessment in bundle.assessments:
        criterion = criteria[assessment.criterion_id]
        awarded = (
            assessment.awarded_points if assessment.awarded_points is not None else "?"
        )
        points = (
            "unscored"
            if criterion.max_points is None
            else f"{awarded} / {criterion.max_points}"
        )
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(value)
                for value in (
                    criterion.title,
                    assessment.status,
                    points,
                    assessment.explanation,
                )
            )
            + " |"
        )
    lines += ["", "## Evidence", ""]
    for evidence in bundle.evidence:
        location = ""
        if evidence.kind == "source":
            location = (
                f"{files[evidence.submission_file_id]}:"
                f"{evidence.span.start_line}-{evidence.span.end_line}"
            )
        elif evidence.kind == "check":
            location = (
                f"check {evidence.check_execution_id}, {evidence.diagnostic_stream}"
                f"[{evidence.start_offset}:{evidence.end_offset}]"
            )
        else:
            location = f"{evidence.observation}: {evidence.relative_path}"
        lines += [
            f"* `{evidence.id}`: {markdown_cell(location)}. "
            f"{markdown_cell(evidence.summary)}"
        ]
    lines += ["", "## Decisions and recommendations", ""]
    for assessment in bundle.assessments:
        lines += [
            f"### {markdown_cell(criteria[assessment.criterion_id].title)}",
            "",
            markdown_cell(assessment.explanation),
            "",
        ]
        if assessment.not_verifiable_reason:
            lines += [
                f"Unverified: {markdown_cell(assessment.not_verifiable_reason)}",
                "",
            ]
        if assessment.recommendations:
            lines += [markdown_cell(assessment.recommendations), ""]
        if assessment.evidence_ids:
            lines += [
                "Evidence: "
                + ", ".join(
                    f"`{identifier}`" for identifier in assessment.evidence_ids
                ),
                "",
            ]
    if bundle.penalty_applications:
        lines += ["## Explicit deductions", ""]
        for application in bundle.penalty_applications:
            lines += [
                f"* {application.applied_amount}: "
                f"{markdown_cell(application.explanation)}"
            ]
    lines += ["", "## Checks and limitations", ""]
    for check in bundle.checks:
        reason = markdown_cell(check.reason or f"exit code {check.exit_code}")
        lines += [f"* {check.kind}: **{check.status}**. {reason}"]
    if bundle.rubric.needs_clarification:
        lines += ["", "Assignment ambiguities require human clarification."]
    return "\n".join(lines).rstrip() + "\n"
