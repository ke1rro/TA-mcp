import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastmcp import FastMCP

from ta_mcp.archive import ArchiveError, InspectedArchive, inspect_archive
from ta_mcp.checks import run_available_checks
from ta_mcp.configuration import read_policy, read_text_input
from ta_mcp.contracts import (
    CheckResults,
    InspectArchiveRequest,
    InspectArchiveResponse,
    ReviewPaths,
    RunChecksRequest,
    RunChecksResponse,
    SaveReviewRequest,
    SaveReviewResponse,
    ToolError,
    ToolFailure,
    ToolSuccess,
)
from ta_mcp.domain import ArchiveInspection, RubricAnalysis, SourceFileEvidence
from ta_mcp.reporting import content_digest
from ta_mcp.repository import ReviewConflict, ReviewRepository
from ta_mcp.validation import validate_analysis


@dataclass(frozen=True)
class ServerScope:
    """User-authorized filesystem boundaries and runtime role."""

    role: Literal["analyst", "grader"]
    submission: Path
    requirements: Path
    policy: Path
    database: Path
    output: Path

    def __post_init__(self) -> None:
        inputs = {
            path.resolve() for path in (self.submission, self.requirements, self.policy)
        }
        if self.database.resolve() in inputs or self.output.resolve() in inputs:
            raise ValueError("Persistent output paths must differ from input files")


class ToolSession:
    """Ephemeral inspection/check receipts for one scoped MCP subprocess."""

    def __init__(self, scope: ServerScope) -> None:
        self.scope = scope
        self.archive: InspectedArchive | None = None
        self.frozen: dict[UUID, tuple[str, CheckResults]] = {}

    def inspect(
        self, archive_path: str, requested_paths: list[str] | None = None
    ) -> InspectedArchive:
        """Read only the authorized archive and detect mid-review changes."""
        if Path(archive_path).resolve() != self.scope.submission.resolve():
            raise PermissionError("Archive path is outside this MCP session's scope")
        archive = inspect_archive(self.scope.submission, requested_paths)
        if (
            self.archive
            and self.archive.inspection.submission != archive.inspection.submission
        ):
            raise ReviewConflict("Submission changed during review")
        self.archive = archive
        return archive

    def freeze_inputs(self, request: RunChecksRequest) -> str:
        """Validate trusted source/policy snapshots and freeze rubric content."""
        if request.assignment.original_text != read_text_input(self.scope.requirements):
            raise ValueError("Assignment does not match the user-authorized source")
        trusted_policy = read_policy(self.scope.policy)
        if trusted_policy.model_dump(exclude={"id"}) != request.policy.model_dump(
            exclude={"id"}
        ):
            raise ValueError("Policy does not match the user-authorized configuration")
        validate_analysis(request.assignment, request.analysis)
        payload = request.model_dump(mode="json", exclude={"archive_path"})
        digest = content_digest(json.dumps(payload, sort_keys=True, ensure_ascii=False))
        previous = self.frozen.get(request.review_run_id)
        if previous is not None and previous[0] != digest:
            raise ReviewConflict("Rubric or policy changed after review began")
        return digest

    def save(self, request: SaveReviewRequest) -> ReviewPaths:
        """Verify tool provenance before persisting any grading decision."""
        bundle = request.bundle
        repository = ReviewRepository(self.scope.database, self.scope.output)
        if repository.matches_existing(bundle):
            saved = repository.save(bundle)
            return ReviewPaths(
                json_path=str(saved.json_path),
                markdown_path=str(saved.markdown_path),
                content_digest=saved.digest,
            )
        archive = self.inspect(str(self.scope.submission))
        frozen_request = RunChecksRequest(
            review_run_id=bundle.run.id,
            archive_path=str(self.scope.submission),
            assignment=bundle.assignment,
            policy=bundle.policy,
            analysis=RubricAnalysis.model_validate(
                bundle.model_dump(include=set(RubricAnalysis.model_fields))
            ),
        )
        digest = self.freeze_inputs(frozen_request)
        previous = self.frozen.get(bundle.run.id)
        if previous is None or previous[0] != digest:
            raise ValueError("No trusted run_checks receipt exists for this review")
        if {item.id: item for item in bundle.checks} != {
            item.id: item for item in previous[1].checks
        }:
            raise ValueError("Submitted check results disagree with actual MCP results")
        if (
            bundle.submission != archive.inspection.submission
            or bundle.files != archive.inspection.files
        ):
            raise ValueError("Submitted manifest disagrees with the inspected archive")
        file_paths = {entry.id: entry.relative_path for entry in bundle.files}
        for evidence in bundle.evidence:
            if isinstance(evidence, SourceFileEvidence):
                text = archive.texts[file_paths[evidence.submission_file_id]]
                excerpt = "\n".join(
                    text.splitlines()[
                        evidence.span.start_line - 1 : evidence.span.end_line
                    ]
                )
                if excerpt != evidence.verified_excerpt:
                    raise ValueError(
                        "Source evidence excerpt does not match archived content"
                    )
        saved = repository.save(bundle)
        return ReviewPaths(
            json_path=str(saved.json_path),
            markdown_path=str(saved.markdown_path),
            content_digest=saved.digest,
        )


def failure(error: Exception) -> ToolFailure:
    """Translate a recovered tool boundary failure into a typed result."""
    if isinstance(error, PermissionError):
        code = "FORBIDDEN"
    elif isinstance(error, ArchiveError):
        code = "UNSAFE_ARCHIVE"
    elif isinstance(error, ReviewConflict):
        code = "CONFLICT"
    elif isinstance(error, OSError):
        code = "IO_ERROR"
    else:
        code = "INVALID_INPUT"
    return ToolFailure(error=ToolError(code=code, message=str(error)[:4000]))


def create_server(scope: ServerScope) -> FastMCP:
    """Register only tools permitted to this server's authenticated local role."""
    server = FastMCP("TA-mcp", mask_error_details=True)
    session = ToolSession(scope)

    @server.tool(name="inspect_archive", annotations={"readOnlyHint": True})
    def inspect_archive_tool(request: InspectArchiveRequest) -> InspectArchiveResponse:
        """Inspect the authorized local ZIP without extracting or executing it."""
        try:
            return ToolSuccess[ArchiveInspection](
                value=session.inspect(
                    request.archive_path, request.requested_paths
                ).inspection
            )
        except (ValueError, OSError) as error:
            return failure(error)

    if scope.role == "grader":

        @server.tool(name="run_checks", annotations={"readOnlyHint": True})
        def run_checks_tool(request: RunChecksRequest) -> RunChecksResponse:
            """Freeze review inputs and run only the available safe checks."""
            try:
                archive = session.inspect(request.archive_path)
                digest = session.freeze_inputs(request)
                previous = session.frozen.get(request.review_run_id)
                if previous is not None:
                    return ToolSuccess[CheckResults](value=previous[1])
                results = CheckResults(
                    checks=run_available_checks(
                        archive, request.review_run_id, request.policy
                    ),
                    frozen_input_digest=digest,
                )
                session.frozen[request.review_run_id] = (digest, results)
                return ToolSuccess[CheckResults](value=results)
            except (ValueError, OSError) as error:
                return failure(error)

        @server.tool(
            name="save_review",
            annotations={"readOnlyHint": False, "idempotentHint": True},
        )
        def save_review_tool(request: SaveReviewRequest) -> SaveReviewResponse:
            """Verify provenance and save immutable JSON, Markdown, and audit rows."""
            try:
                return ToolSuccess[ReviewPaths](value=session.save(request))
            except (ValueError, OSError) as error:
                return failure(error)

    return server


def main() -> None:
    """Run the scoped local stdio MCP server."""
    parser = argparse.ArgumentParser(description="TA-mcp scoped stdio tools")
    parser.add_argument("--role", choices=["analyst", "grader"], required=True)
    for argument in ("submission", "requirements", "policy", "database", "output"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    arguments = parser.parse_args()
    scope = ServerScope(**vars(arguments))
    create_server(scope).run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
