import logging
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ta_mcp.utils import find_assignment_dir

logger = logging.getLogger("ta_mcp.analyst")

mcp = MCPServer("AnalystServer")


@mcp.tool(
    title="Get Assignment Requirements",
    description="Retrieve the requirements for a specific assignment.",
)
def get_assignment(assignment_idx: str) -> str:
    """Get the requirements for a specific assignment.

    Args:
        assignment_idx: The identifier of the assignment.

    Returns:
        The contents of the assignment requirements document.
    """
    assignment_dir = find_assignment_dir(assignment_idx)
    requirements_path = assignment_dir / "requirements.md"

    if not requirements_path.is_file():
        raise ToolError(f"requirements.md not found for {assignment_idx}")

    return requirements_path.read_text(encoding="utf-8")


@mcp.tool(
    title="List Assignment Submissions",
    description="List all submission identifiers for a given assignment.",
)
def list_assignment_submissions(assignment_idx: str) -> list[str]:
    """List all submission identifiers for a given assignment.

    Args:
        assignment_idx: The identifier of the assignment.

    Returns:
        A list of submission identifiers found for the assignment.
    """
    assignment_dir = find_assignment_dir(assignment_idx)
    return [
        f"{assignment_idx}/{archive_path.stem}"
        for archive_path in assignment_dir.glob("*.zip")
    ]


if __name__ == "__main__":
    mcp.run()
