import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml
from agents.exceptions import AgentsException
from dotenv import load_dotenv
from openai import OpenAIError

from ta_mcp.configuration import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    read_policy,
    read_text_input,
)
from ta_mcp.observability import ExecutionLog, RequestLimitReached, describe_error
from ta_mcp.runtime_agents import create_review_model
from ta_mcp.workflow import WorkflowResult, grade_submission


def main() -> None:
    """Review one ZIP with bounded model calls and optional progressive events.

    Validate local inputs before constructing the provider, share a request budget
    across both roles and always close the provider and trace after the workflow.
    """
    load_dotenv(Path.cwd() / ".env")
    for name in ("openai", "openai.agents", "httpx2", "httpcore2"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    parser = argparse.ArgumentParser(
        description="Source-grounded AI lab review through scoped MCP tools"
    )
    parser.add_argument(
        "--submission", type=Path, required=True, help="Local student ZIP archive"
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        required=True,
        help="UTF-8 assignment Markdown or text",
    )
    parser.add_argument(
        "--policy", type=Path, required=True, help="JSON or YAML grading policy"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reviews"),
        help="Parent directory for per-run reports",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("reviews.sqlite"),
        help="Local SQLite audit database",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        default=os.environ.get("TA_MCP_PROVIDER", "openai"),
        help="Agents SDK model provider; credentials are loaded from .env",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("TA_MCP_MODEL"),
        help="API model identifier; no automatic model-discovery request",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Stream sanitized execution events"
    )
    parser.add_argument(
        "--llm-timeout",
        type=int,
        default=os.environ.get(
            "TA_MCP_LLM_TIMEOUT_SECONDS", str(DEFAULT_LLM_TIMEOUT_SECONDS)
        ),
        help="Provider timeout in seconds per model call (default: 180)",
    )
    parser.add_argument(
        "--trace-file",
        type=Path,
        help="New JSONL trace path; an existing file is never overwritten",
    )
    parser.add_argument(
        "--repair-output",
        action="store_true",
        help="Allow one Gemini JSON repair across both agents, within the request cap",
    )
    parser.add_argument(
        "--demo-json-error",
        action="store_true",
        help="DEMO: inject one labeled extra JSON field to exercise Gemini repair",
    )
    parser.add_argument(
        "--max-llm-requests",
        type=int,
        default=os.environ.get("TA_MCP_MAX_LLM_REQUESTS", "2"),
        help="Maximum LLM HTTP attempts shared by both agents (default: 2)",
    )
    arguments = parser.parse_args()
    if arguments.max_llm_requests < 1:
        parser.error("--max-llm-requests must be positive")
    if arguments.llm_timeout < 1:
        parser.error("--llm-timeout must be positive")
    if arguments.repair_output and arguments.provider != "gemini":
        parser.error("--repair-output currently supports Gemini only")
    if arguments.demo_json_error and (
        not arguments.repair_output or arguments.max_llm_requests < 3
    ):
        parser.error(
            "--demo-json-error requires --repair-output and --max-llm-requests >= 3"
        )
    observer: ExecutionLog | None = None
    try:
        inputs = [arguments.submission, arguments.requirements, arguments.policy]
        for path in inputs:
            if not path.is_file():
                print(f"Missing input file: {path.name}", file=sys.stderr)
                raise ValueError(f"Input file does not exist: {path}")
        if arguments.database.resolve() in {path.resolve() for path in inputs}:
            raise ValueError("Database path must differ from all input files")
        read_text_input(arguments.requirements)
        read_policy(arguments.policy)
        observer = ExecutionLog(
            arguments.verbose, arguments.trace_file, arguments.max_llm_requests
        )
        observer.emit(
            "SYSTEM",
            "run_start",
            details={
                "max_llm_requests": arguments.max_llm_requests,
                "llm_timeout_seconds": arguments.llm_timeout,
                "output_repair_limit": 1 if arguments.repair_output else 0,
                "demo_json_error": arguments.demo_json_error,
            },
        )

        async def run_review() -> WorkflowResult:
            """Configure the provider and grade within the same event loop."""
            model = await create_review_model(
                arguments.provider,
                arguments.model,
                observer,
                arguments.llm_timeout,
                should_repair_output=arguments.repair_output,
                should_inject_json_error=arguments.demo_json_error,
            )
            try:
                return await grade_submission(
                    arguments.submission,
                    arguments.requirements,
                    arguments.policy,
                    arguments.output,
                    arguments.database,
                    model,
                    observer,
                    arguments.llm_timeout,
                    should_repair_output=arguments.repair_output,
                )
            finally:
                await model.close()

        result = asyncio.run(run_review())
    except FileExistsError:
        print(
            "Trace file already exists. Choose a new --trace-file path; "
            "no API request was sent.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
    except (
        ValueError,
        OSError,
        TimeoutError,
        yaml.YAMLError,
        AgentsException,
        OpenAIError,
        RequestLimitReached,
    ) as error:
        details = describe_error(error)
        if observer is not None:
            observer.emit("ERROR", "run_failed", observer.agent_role, details)
        else:
            print(f"Review failed: {details}", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        if observer is not None:
            observer.emit("ERROR", "run_interrupted", observer.agent_role)
        else:
            print("Review interrupted before any API request", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as error:
        if observer is not None:
            observer.emit(
                "ERROR", "run_failed", observer.agent_role, describe_error(error)
            )
        else:
            print(f"Review failed: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        if observer is not None:
            observer.close()
    recommendation = result.recommended_score or "no final numeric recommendation"
    print(f"{result.state}: {recommendation}")
    print(f"JSON: {result.json_path}")
    print(f"Markdown: {result.markdown_path}")
    if arguments.trace_file is not None:
        print(f"Trace: {arguments.trace_file}")
