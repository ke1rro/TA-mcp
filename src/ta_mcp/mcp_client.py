import asyncio
import json
import sys
from pathlib import Path
from time import monotonic
from types import TracebackType
from typing import Literal, Self

from agents.mcp import MCPServerStdio, create_static_tool_filter
from pydantic import TypeAdapter

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
from ta_mcp.domain import ArchiveInspection, Contract
from ta_mcp.observability import ExecutionLog, describe_error


class ToolCallError(ValueError):
    """Structured MCP failure surfaced at the application boundary."""

    def __init__(self, error: ToolError) -> None:
        self.error = error
        super().__init__(f"{error.code}: {error.message}")


class ReviewMCPClient:
    """Typed stdio transport with an explicit runtime role allowlist."""

    def __init__(
        self,
        role: Literal["analyst", "grader"],
        submission: Path,
        requirements: Path,
        policy: Path,
        output: Path,
        database: Path,
        observer: ExecutionLog | None = None,
    ) -> None:
        self.role = role
        self.observer = observer
        self.allowed_tools = {"inspect_archive"}
        if role == "grader":
            self.allowed_tools.update({"run_checks", "save_review"})
        arguments = ["-m", "ta_mcp.mcp_server", "--role", role]
        for name, path in (
            ("submission", submission),
            ("requirements", requirements),
            ("policy", policy),
            ("output", output),
            ("database", database),
        ):
            arguments.extend([f"--{name}", str(path.resolve())])
        self.server = MCPServerStdio(
            params={
                "command": sys.executable,
                "args": arguments,
                "env": {"PYTHONUNBUFFERED": "1", "FASTMCP_LOG_LEVEL": "ERROR"},
            },
            cache_tools_list=True,
            use_structured_content=True,
            client_session_timeout_seconds=180,
            max_retry_attempts=0,
            tool_filter=create_static_tool_filter(
                allowed_tool_names=sorted(self.allowed_tools)
            ),
        )

    async def __aenter__(self) -> Self:
        if self.observer is not None:
            self.observer.agent_role = self.role
            self.observer.emit(
                "SYSTEM",
                "mcp_connect_start",
                self.role,
                {"allowed_tools": sorted(self.allowed_tools)},
            )
        try:
            await self.server.connect()
        except Exception as error:
            if self.observer is not None:
                self.observer.emit(
                    "ERROR", "mcp_connect_failed", self.role, describe_error(error)
                )
            raise
        if self.observer is not None:
            self.observer.emit("SYSTEM", "mcp_connected", self.role)
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.server.cleanup()

    async def tool_names(self) -> set[str]:
        """Discover the actual tools registered by the scoped subprocess."""
        return {tool.name for tool in await self.server.list_tools()}

    async def invoke[T](
        self, name: str, request: Contract, response: TypeAdapter[T]
    ) -> T:
        """Authorize and validate one actual MCP request/response exchange.

        Emit sanitized metadata before dispatch, validate the typed result and
        record completion or failure without logging the contract payload.

        Args:
            name: Tool name permitted to the current role.
            request: Typed tool input, excluded from raw logs.
            response: Adapter for validating the expected tool response.

        Returns:
            The validated success response.
        """
        if name not in self.allowed_tools:
            raise PermissionError(f"This runtime role cannot call {name}")
        started_at = monotonic()
        if self.observer is not None:
            self.observer.emit(
                "MCP",
                "tool_start",
                self.role,
                {"tool": name, "arguments": summarize_tool_request(request)},
            )
        try:
            result = await self.server.call_tool(
                name, {"request": request.model_dump(mode="json")}
            )
            if result.is_error:
                raise ToolCallError(
                    ToolError(
                        code="INVALID_INPUT", message="MCP rejected the tool request"
                    )
                )
            payload = result.structured_content
            if payload is None:
                text = next(
                    (block.text for block in result.content if block.type == "text"),
                    None,
                )
                if text is None:
                    raise ValueError("MCP returned no structured result")
                payload = json.loads(text)
            parsed = response.validate_python(payload["result"])
            if isinstance(parsed, ToolFailure):
                raise ToolCallError(parsed.error)
        except (Exception, asyncio.CancelledError) as error:
            if self.observer is not None:
                self.observer.emit(
                    "ERROR",
                    "tool_failed",
                    self.role,
                    {
                        "tool": name,
                        "status": "error",
                        "duration_ms": round((monotonic() - started_at) * 1000),
                        "code": (
                            error.error.code
                            if isinstance(error, ToolCallError)
                            else None
                        ),
                        **describe_error(error),
                    },
                )
            raise
        if self.observer is not None:
            self.observer.emit(
                "MCP",
                "tool_complete",
                self.role,
                {
                    "tool": name,
                    "status": "ok",
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "result": summarize_tool_result(parsed),
                },
            )
        return parsed

    async def inspect(self, request: InspectArchiveRequest) -> ArchiveInspection:
        """Inspect the scoped ZIP through stdio MCP."""
        response = await self.invoke(
            "inspect_archive", request, TypeAdapter(InspectArchiveResponse)
        )
        if isinstance(response, ToolFailure):
            raise ToolCallError(response.error)
        return response.value

    async def run_checks(self, request: RunChecksRequest) -> CheckResults:
        """Freeze inputs and collect tool-produced check receipts through MCP."""
        response = await self.invoke(
            "run_checks", request, TypeAdapter(RunChecksResponse)
        )
        if isinstance(response, ToolFailure):
            raise ToolCallError(response.error)
        return response.value

    async def save(self, request: SaveReviewRequest) -> ReviewPaths:
        """Persist a validated review through the grader-only MCP capability."""
        response = await self.invoke(
            "save_review", request, TypeAdapter(SaveReviewResponse)
        )
        if isinstance(response, ToolFailure):
            raise ToolCallError(response.error)
        return response.value


def summarize_tool_request(request: Contract) -> dict[str, object]:
    """Select tool arguments without including source, prompts or full contracts.

    Args:
        request: Typed request passed to an authorized MCP tool.

    Returns:
        Safe archive names, record identities and collection sizes.
    """
    if isinstance(request, InspectArchiveRequest):
        return {
            "archive": Path(request.archive_path).name,
            "requested_path_count": len(request.requested_paths or []),
        }
    if isinstance(request, RunChecksRequest):
        return {
            "archive": Path(request.archive_path).name,
            "run_id": str(request.review_run_id),
            "assignment_sha256": request.assignment.sha256,
            "criteria": len(request.analysis.criteria),
        }
    if isinstance(request, SaveReviewRequest):
        return {
            "run_id": str(request.bundle.run.id),
            "assessments": len(request.bundle.assessments),
            "evidence_count": len(request.bundle.evidence),
        }
    return {}


def summarize_tool_result(result: object) -> dict[str, object]:
    """Summarize tool receipts without exposing student text.

    Args:
        result: Parsed typed MCP response.

    Returns:
        Manifest counts, check statuses or final report paths.
    """
    if not isinstance(result, ToolSuccess):
        return {}
    value = result.value
    if isinstance(value, ArchiveInspection):
        return {"files": len(value.files), "languages": value.languages}
    if isinstance(value, CheckResults):
        return {
            "checks": [
                {"kind": item.kind, "tool": item.tool_name, "status": item.status.value}
                for item in value.checks
            ]
        }
    if isinstance(value, ReviewPaths):
        return {"json_path": value.json_path, "markdown_path": value.markdown_path}
    return {}
