import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic_ns
from uuid import UUID

from ta_mcp.archive import InspectedArchive
from ta_mcp.domain import CheckExecution, CheckStatus, GradingPolicy

VALID_CASES = (
    ("1", "5", 2),
    ("-3", "3", 3),
    ("0", "0", 1),
    ("2", "2", 1),
    ("3", "3", 0),
    ("-4", "-2", 2),
    ("-1000", "1000", 1001),
    ("-1000", "-1000", 1),
    ("999", "1000", 1),
    ("1000", "1000", 1),
)
INVALID_CASES = (
    ([], 1),
    (["1"], 1),
    (["1", "2", "3"], 1),
    (["abc", "3"], 2),
    (["1.5", "3"], 2),
    (["2x", "3"], 2),
    (["", "3"], 2),
    (["-1001", "3"], 2),
    (["0", "1001"], 2),
    (["4", "2"], 2),
    (["999999999999999999999999", "3"], 2),
)


@dataclass(frozen=True)
class CommandResult:
    """Bounded local process output and its actual termination status."""

    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int


def limit_resources() -> None:
    """Bound CPU time, output file size, file descriptors, and core dumps."""
    import resource

    for kind, maximum in (
        (resource.RLIMIT_CPU, 30),
        (resource.RLIMIT_FSIZE, 8 * 1024 * 1024),
        (resource.RLIMIT_NOFILE, 128),
        (resource.RLIMIT_CORE, 0),
    ):
        _, hard = resource.getrlimit(kind)
        limit = maximum if hard == resource.RLIM_INFINITY else min(maximum, hard)
        resource.setrlimit(kind, (limit, limit))


def run_command(
    command: list[str], directory: Path, log: Path, timeout: int
) -> CommandResult:
    """Execute one local command with bounded logs and a wall-clock deadline.

    Args:
        command: Executable and arguments, without shell interpretation.
        directory: Temporary working directory for the command.
        log: Prefix for persistent stdout and stderr files.
        timeout: Maximum elapsed seconds before terminating the process group.

    Returns:
        Actual exit code, bounded output, and elapsed time; no exit code on timeout.
    """
    start = monotonic_ns()
    stdout_path = log.with_suffix(".stdout.log")
    stderr_path = log.with_suffix(".stderr.log")
    environment = {
        "PATH": os.environ.get("PATH", os.defpath),
        "TMPDIR": str(directory),
        "LC_ALL": "C",
    }
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        with subprocess.Popen(
            command,
            cwd=directory,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
            preexec_fn=limit_resources,
        ) as process:
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                exit_code = None
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
    with stdout_path.open("rb") as stdout, stderr_path.open("rb") as stderr:
        return CommandResult(
            exit_code,
            stdout.read(16000).decode("utf-8", errors="replace"),
            stderr.read(16000).decode("utf-8", errors="replace"),
            (monotonic_ns() - start) // 1000000,
        )


def check_count_even(
    executable: Path, workspace: Path, logs: Path, run_id: UUID, environment: str
) -> list[CheckExecution]:
    """Check the mini assignment's results, CLI errors, and output independently.

    Args:
        executable: Compiled count_even program.
        workspace: Temporary working directory for child processes.
        logs: Directory for persistent per-case stdout and stderr.
        run_id: Review identity attached to the receipts.
        environment: Digest identifying the local checker environment.

    Returns:
        Separate receipts for numerical correctness, CLI validation, and output.
    """
    diagnostics: dict[str, list[str]] = {"correctness": [], "cli": [], "output": []}
    failures = dict.fromkeys(diagnostics, False)
    timeouts = dict.fromkeys(diagnostics, False)
    has_ambiguous_result = False
    durations = dict.fromkeys(diagnostics, 0)
    cases = [([left, right], 0, expected) for left, right, expected in VALID_CASES] + [
        (arguments, code, None) for arguments, code in INVALID_CASES
    ]
    for index, (arguments, expected_code, expected_count) in enumerate(cases, 1):
        result = run_command(
            [str(executable), *arguments], workspace, logs / f"case-{index:02}", 2
        )
        groups = ("correctness", "output") if expected_code == 0 else ("cli", "output")
        record = (
            f"args={json.dumps(arguments)} expected_exit={expected_code} "
            f"actual_exit={result.exit_code} expected_count={expected_count} "
            f"stdout={json.dumps(result.stdout[:200])} "
            f"stderr={json.dumps(result.stderr[:200])}"
        )
        if result.exit_code is None:
            verdicts = dict.fromkeys(groups, False)
        elif expected_code == 0:
            numbers = re.findall(r"(?<![\w.])-?\d+(?![\w.])", result.stdout)
            has_ambiguous_result |= result.exit_code == 0 and len(numbers) != 1
            verdicts = {
                "correctness": result.exit_code == 0
                and len(numbers) == 1
                and Decimal(numbers[0]) == expected_count,
                "output": re.fullmatch(r"[+-]?\d+\n", result.stdout) is not None
                and result.stderr == "",
            }
        else:
            verdicts = {
                "cli": result.exit_code == expected_code
                and bool(result.stderr.strip()),
                "output": result.stdout == "" and bool(result.stderr.strip()),
            }
        for group in groups:
            failures[group] |= not verdicts[group]
            timeouts[group] |= result.exit_code is None
            durations[group] += result.duration_ms
            verdict = "TIMEOUT" if result.exit_code is None else str(verdicts[group])
            diagnostics[group].append(f"{record} {group}={verdict}")
    return [
        CheckExecution(
            review_run_id=run_id,
            kind="tests",
            tool_name=f"ta-mcp.local.{group}",
            environment_digest=environment,
            status=(
                CheckStatus.TIMEOUT
                if timeouts[group]
                else (
                    CheckStatus.ERROR
                    if group == "correctness" and has_ambiguous_result
                    else CheckStatus.FAILED if failures[group] else CheckStatus.PASSED
                )
            ),
            exit_code=(
                None
                if timeouts[group] or (group == "correctness" and has_ambiguous_result)
                else int(failures[group])
            ),
            duration_ms=durations[group],
            bounded_stdout=(
                "Harness exit code is 0 for all cases passing, 1 for a failed case.\n"
                + "\n".join(diagnostics[group])
            )[:16000],
            reason=(
                "A count_even process exceeded 2 seconds"
                if timeouts[group]
                else (
                    "Cannot extract one unambiguous count; inspect output and source"
                    if group == "correctness" and has_ambiguous_result
                    else None
                )
            ),
        )
        for group in diagnostics
    ]


def run_mini_checks(
    archive: InspectedArchive,
    run_id: UUID,
    policy: GradingPolicy,
    logs: Path,
) -> list[CheckExecution]:
    """Build and check one Count Even submission locally without model requests.

    Materialize validated text files in a temporary directory, configure and build
    with CMake, then check the executable against fixed assignment-derived cases.

    Args:
        archive: Validated archive containing the mini assignment's text files.
        run_id: Review identity for persisted check receipts.
        policy: Trusted flags controlling compilation and test execution.
        logs: Directory for command logs and structured check receipts.

    Returns:
        Actual CMake and runtime results, with explicit nonexecution reasons.
    """
    logs.mkdir(parents=True, exist_ok=True)
    cmake = shutil.which("cmake")
    environment = hashlib.sha256(
        f"ta-mcp:local-mini-v1:{platform.platform()}:{cmake}".encode()
    ).hexdigest()
    can_build = policy.check_correctness or policy.run_tests
    reason = None
    if not can_build:
        reason = "Compilation and tests are disabled by grading policy"
    elif os.name != "posix":
        reason = "Local resource-limited execution requires macOS or Linux"
    elif cmake is None:
        reason = "CMake is not installed or is absent from PATH"
    elif len(archive.texts) != len(archive.inspection.files):
        reason = "Local mini checker requires an archive containing only UTF-8 files"
    if reason:
        return [
            CheckExecution(
                review_run_id=run_id,
                kind=kind,
                tool_name="ta-mcp.local",
                environment_digest=environment,
                status=CheckStatus.UNAVAILABLE if can_build else CheckStatus.SKIPPED,
                reason=reason,
            )
            for kind in ("compile", "tests")
        ]
    results: list[CheckExecution] = []
    with TemporaryDirectory(prefix="ta-mcp-mini-") as temporary:
        workspace = Path(temporary)
        source, build = workspace / "source", workspace / "build"
        source.mkdir()
        for name, text in archive.texts.items():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        commands = (
            ([str(cmake), "-S", str(source), "-B", str(build)], "configure", 30),
            ([str(cmake), "--build", str(build), "--parallel", "2"], "build", 45),
        )
        for command, name, timeout in commands:
            result = run_command(command, workspace, logs / name, timeout)
            results.append(
                CheckExecution(
                    review_run_id=run_id,
                    kind="compile",
                    tool_name=f"cmake.{name}",
                    environment_digest=environment,
                    status=(
                        CheckStatus.TIMEOUT
                        if result.exit_code is None
                        else (
                            CheckStatus.PASSED
                            if result.exit_code == 0
                            else CheckStatus.FAILED
                        )
                    ),
                    exit_code=result.exit_code,
                    duration_ms=result.duration_ms,
                    bounded_stdout=result.stdout,
                    bounded_stderr=result.stderr,
                    reason=(
                        f"CMake exceeded {timeout} seconds"
                        if result.exit_code is None
                        else None
                    ),
                )
            )
            if result.exit_code != 0:
                break
        executable = build / "count_even"
        has_built = len(results) == 2 and results[-1].status == CheckStatus.PASSED
        if has_built and not executable.is_file():
            results.append(
                CheckExecution(
                    review_run_id=run_id,
                    kind="compile",
                    tool_name="ta-mcp.local.build-artifact",
                    environment_digest=environment,
                    status=CheckStatus.FAILED,
                    exit_code=1,
                    bounded_stderr="CMake completed but build/count_even is missing",
                )
            )
        if has_built and executable.is_file() and policy.run_tests:
            results.extend(
                check_count_even(executable, workspace, logs, run_id, environment)
            )
        else:
            results.append(
                CheckExecution(
                    review_run_id=run_id,
                    kind="tests",
                    tool_name="ta-mcp.local.count_even",
                    environment_digest=environment,
                    status=CheckStatus.SKIPPED,
                    reason=(
                        "Tests disabled by grading policy"
                        if not policy.run_tests
                        else "No executable is available; inspect CMake results"
                    ),
                )
            )
    (logs / "checks.json").write_text(
        json.dumps([item.model_dump(mode="json") for item in results], indent=2),
        encoding="utf-8",
    )
    return results
