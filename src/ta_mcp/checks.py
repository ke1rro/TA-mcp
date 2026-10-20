import ast
import hashlib
import platform
from pathlib import Path
from time import monotonic_ns
from uuid import UUID

from ta_mcp.archive import InspectedArchive
from ta_mcp.domain import AssignmentDocument, CheckExecution, CheckStatus, GradingPolicy
from ta_mcp.local_checks import run_mini_checks


def run_available_checks(
    archive: InspectedArchive,
    review_run_id: UUID,
    policy: GradingPolicy,
    assignment: AssignmentDocument | None = None,
    artifacts: Path | None = None,
) -> list[CheckExecution]:
    """Run local Count Even checks or parse Python syntax without execution.

    Args:
        archive: Fully validated archive retained only in memory.
        review_run_id: Identity to attach to every tool result.
        policy: Trusted behavior flags for requested checks.
        assignment: Trusted assignment selecting the supported mini checker.
        artifacts: Directory for persistent local command logs.

    Returns:
        Actual bounded diagnostics and explicit unavailable or skipped checks.
    """
    environment = hashlib.sha256(
        f"ta-mcp:ast:{platform.python_version()}".encode()
    ).hexdigest()
    results = []
    is_mini_assignment = (
        assignment is not None
        and "count_even <left> <right>" in assignment.original_text
        and "CMakeLists.txt" in assignment.original_text
    )
    if is_mini_assignment and artifacts is not None:
        results.extend(run_mini_checks(archive, review_run_id, policy, artifacts))
    for kind, is_enabled in (
        ("compile", policy.check_correctness),
        ("tests", policy.run_tests),
        ("static", policy.check_code_quality),
        ("memory", policy.check_memory_safety),
    ):
        if (
            is_mini_assignment
            and artifacts is not None
            and kind in {"compile", "tests"}
        ):
            continue
        if not is_enabled:
            results.append(
                CheckExecution(
                    review_run_id=review_run_id,
                    kind=kind,
                    status=CheckStatus.SKIPPED,
                    tool_name="ta-mcp.policy",
                    environment_digest=environment,
                    reason="Disabled by grading policy",
                )
            )
        elif kind != "static":
            results.append(
                CheckExecution(
                    review_run_id=review_run_id,
                    kind=kind,
                    status=CheckStatus.UNAVAILABLE,
                    tool_name="ta-mcp.sandbox",
                    environment_digest=environment,
                    reason=(
                        "No isolated execution backend is configured. "
                        "Student code was not executed."
                    ),
                )
            )
        else:
            results.append(check_python_syntax(archive, review_run_id, environment))
    return results


def check_python_syntax(
    archive: InspectedArchive, review_run_id: UUID, environment: str
) -> CheckExecution:
    """Parse bounded UTF-8 Python source without importing or running it."""
    sources = [
        (name, text) for name, text in archive.texts.items() if name.endswith(".py")
    ]
    if not sources:
        return CheckExecution(
            review_run_id=review_run_id,
            kind="static",
            tool_name="ta-mcp.python-ast",
            environment_digest=environment,
            status=CheckStatus.UNAVAILABLE,
            reason="No UTF-8 Python source is available for syntax analysis",
        )
    if sum(len(text) for _, text in sources) > 256000:
        return CheckExecution(
            review_run_id=review_run_id,
            kind="static",
            tool_name="ta-mcp.python-ast",
            environment_digest=environment,
            status=CheckStatus.UNAVAILABLE,
            reason="Source exceeds the 256000-character safe parser budget",
        )
    start = monotonic_ns()
    errors = []
    try:
        for name, text in sources:
            ast.parse(text, filename=name)
    except (MemoryError, RecursionError) as error:
        return CheckExecution(
            review_run_id=review_run_id,
            kind="static",
            tool_name="ta-mcp.python-ast",
            environment_digest=environment,
            status=CheckStatus.ERROR,
            reason=type(error).__name__,
        )
    except SyntaxError as error:
        errors.append(f"{error.filename}:{error.lineno}:{error.offset}: {error.msg}")
    return CheckExecution(
        review_run_id=review_run_id,
        kind="static",
        tool_name="ta-mcp.python-ast",
        environment_digest=environment,
        status=CheckStatus.FAILED if errors else CheckStatus.PASSED,
        exit_code=1 if errors else 0,
        duration_ms=(monotonic_ns() - start) // 1000000,
        bounded_stdout=(
            ""
            if errors
            else f"Parsed syntax of {len(sources)} Python file(s); no code executed."
        ),
        bounded_stderr="\n".join(errors)[:16000],
    )
