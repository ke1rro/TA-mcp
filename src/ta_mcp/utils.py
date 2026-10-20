import logging
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

logger = logging.getLogger("ta_mcp.common")

EXAMPLES_DIR = Path("examples")
REPORTS_DIR = Path("reports")


def unarchive_submission(submission_idx: str, destination: Path) -> None:
    """Extract the contents of a ZIP archive to a specified destination.

    Args:
        archive_path: The path to the ZIP archive.
        destination: The directory where the contents will be extracted.
    """
    archive_path = find_submission_path(submission_idx)

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(destination)
    except zipfile.BadZipFile as error:
        raise ToolError(
            f"Submission {submission_idx} is not a valid zip archive"
        ) from error


def find_submission_path(submission_idx: str) -> Path:
    """Locate the file path for a given submission archive.

    Args:
        submission_idx: The identifier of the submission.

    Returns:
        The resolved file path to the submission zip archive.
    """
    target_file = EXAMPLES_DIR / f"{submission_idx}.zip"
    if target_file.is_file():
        return target_file

    raise ToolError(f"Submission {submission_idx} not found")


def find_assignment_dir(assignment_idx: str) -> Path:
    """Locate the directory for a given assignment.

    Args:
        assignment_idx: The identifier of the assignment.

    Returns:
        The resolved directory path for the assignment.
    """
    target_dir = EXAMPLES_DIR / assignment_idx
    if target_dir.is_dir():
        return target_dir

    raise ToolError(f"Assignment {assignment_idx} not found")


def save_report(submission_idx: str, report: str) -> None:
    """Save the grading report to a file in the reports directory.

    Args:
        submission_idx: The identifier of the submission.
        report: The contents of the grading report.
    """
    report_path = REPORTS_DIR / f"{submission_idx}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    logger.info("Saved report to %s", report_path)
