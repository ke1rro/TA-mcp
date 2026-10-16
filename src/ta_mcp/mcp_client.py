import json
import sys
from pathlib import Path
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
)
from ta_mcp.domain import ArchiveInspection, Contract


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
    ) -> None:
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
            client_session_timeout_seconds=30,
            max_retry_attempts=0,
            tool_filter=create_static_tool_filter(
                allowed_tool_names=sorted(self.allowed_tools)
            ),
        )

    async def __aenter__(self) -> Self:
        await self.server.connect()
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
        """Authorize and validate one actual MCP request/response exchange."""
        if name not in self.allowed_tools:
            raise PermissionError(f"This runtime role cannot call {name}")
        result = await self.server.call_tool(
            name, {"request": request.model_dump(mode="json")}
        )
        if result.is_error:
            raise ToolCallError(
                ToolError(code="INVALID_INPUT", message="MCP rejected the tool request")
            )
        payload = result.structured_content
        if payload is None:
            text = next(
                (block.text for block in result.content if block.type == "text"), None
            )
            if text is None:
                raise ValueError("MCP returned no structured result")
            payload = json.loads(text)
        parsed = response.validate_python(payload["result"])
        if isinstance(parsed, ToolFailure):
            raise ToolCallError(parsed.error)
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
