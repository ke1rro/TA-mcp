import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml
from agents.exceptions import AgentsException
from openai import OpenAIError

from ta_mcp.configuration import read_policy, read_text_input
from ta_mcp.runtime_agents import OpenAIReviewModel
from ta_mcp.workflow import grade_submission


def main() -> None:
    """Review a local ZIP using an assignment and a JSON or YAML policy."""
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
        "--model",
        default=os.environ.get("TA_MCP_MODEL", "gpt-4.1-mini"),
        help="OpenAI model identifier",
    )
    arguments = parser.parse_args()
    try:
        inputs = [arguments.submission, arguments.requirements, arguments.policy]
        for path in inputs:
            if not path.is_file():
                raise ValueError(f"Input file does not exist: {path}")
        if arguments.database.resolve() in {path.resolve() for path in inputs}:
            raise ValueError("Database path must differ from all input files")
        read_text_input(arguments.requirements)
        read_policy(arguments.policy)
        if not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("Set OPENAI_API_KEY to run the two LLM agents")
        result = asyncio.run(
            grade_submission(
                arguments.submission,
                arguments.requirements,
                arguments.policy,
                arguments.output,
                arguments.database,
                OpenAIReviewModel(arguments.model),
            )
        )
    except (
        ValueError,
        OSError,
        TimeoutError,
        yaml.YAMLError,
        AgentsException,
        OpenAIError,
    ) as error:
        print(f"Review failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        print("Review interrupted", file=sys.stderr)
        raise SystemExit(130) from None
    recommendation = result.recommended_score or "no final numeric recommendation"
    print(f"{result.state}: {recommendation}")
    print(f"JSON: {result.json_path}")
    print(f"Markdown: {result.markdown_path}")
