from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from ta_mcp.domain import (
    ArchiveInspection,
    AssignmentDocument,
    CheckExecution,
    Contract,
    GradingPolicy,
    ReviewBundle,
    RubricAnalysis,
)


class ToolError(Contract):
    """Machine-actionable boundary failure without an implementation traceback."""

    code: Literal[
        "INVALID_INPUT",
        "UNSAFE_ARCHIVE",
        "CONFLICT",
        "UNAVAILABLE",
        "IO_ERROR",
        "FORBIDDEN",
    ]
    message: str = Field(max_length=4000)
    retryable: bool = False
    hint: str | None = None


class ToolFailure(Contract):
    """Discriminated MCP failure result."""

    status: Literal["error"] = "error"
    error: ToolError


class ToolSuccess[T](Contract):
    """Discriminated typed MCP success result."""

    status: Literal["ok"] = "ok"
    value: T


class InspectArchiveRequest(Contract):
    """Request inspection of the single server-authorized archive."""

    archive_path: str
    requested_paths: list[str] | None = Field(default=None, max_length=1000)


type InspectArchiveResponse = Annotated[
    ToolSuccess[ArchiveInspection] | ToolFailure, Field(discriminator="status")
]


class RunChecksRequest(Contract):
    """Freeze trusted review inputs before collecting actual check results."""

    review_run_id: UUID
    archive_path: str
    assignment: AssignmentDocument
    analysis: RubricAnalysis
    policy: GradingPolicy


class CheckResults(Contract):
    """Actual executions and the frozen input digest for audit."""

    checks: list[CheckExecution]
    frozen_input_digest: str


type RunChecksResponse = Annotated[
    ToolSuccess[CheckResults] | ToolFailure, Field(discriminator="status")
]


class SaveReviewRequest(Contract):
    """Validated complete review, with no caller-controlled output paths."""

    bundle: ReviewBundle


class ReviewPaths(Contract):
    """Finalized outputs from the only persistent-state MCP operation."""

    json_path: str
    markdown_path: str
    content_digest: str
    is_complete: Literal[True] = True


type SaveReviewResponse = Annotated[
    ToolSuccess[ReviewPaths] | ToolFailure, Field(discriminator="status")
]
