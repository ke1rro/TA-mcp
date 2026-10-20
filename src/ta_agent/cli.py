import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

import weave
import yaml
from agents import RunConfig, set_trace_processors
from agents.exceptions import AgentsException
from agents.mcp import MCPServerStdio, MCPServerStdioParams
from openai import OpenAIError

from ta_agent.baseline import BaselineTAAgent
from ta_agent.multiagent import MultiagentTAAgent

weave.init("ucu-team4/nlp-lab")


async def get_submissions(
    analyst_mcp: MCPServerStdio, assignment_idx: str
) -> list[str]:
    """Get the list of submission indices for a given assignment."""
    call_tool_result = await analyst_mcp.call_tool(
        tool_name="list_assignment_submissions",
        arguments={"assignment_idx": assignment_idx},
    )

    if call_tool_result.is_error:
        raise AgentsException(
            f"Error listing submissions for assignment {assignment_idx}"
        )

    result = []
    for entry in call_tool_result.content:
        if not hasattr(entry, "text") or not isinstance(entry.text, str):
            raise AgentsException(
                f"Unexpected content type in list_assignment_submissions result: {type(entry)}"
            )

        result.append(entry.text)

    return result


async def multiagent_workflow(
    model: str,
    grader_mcp: MCPServerStdio,
    analyst_mcp: MCPServerStdio,
    run_config: RunConfig,
    assignment_idx: str,
) -> None:
    """Run the multiagent workflow with an analyst and a grader."""
    async with grader_mcp, analyst_mcp:
        agent = MultiagentTAAgent(
            model=model,
            analyst_mcp=analyst_mcp,
            grader_mcp=grader_mcp,
            run_config=run_config,
        )

        context = await agent.analyze(assignment_idx)
        for submission_idx in await get_submissions(analyst_mcp, assignment_idx):
            await agent.grade(context, submission_idx)
            print(f"Grading completed for submission {submission_idx}")


async def baseline_workflow(
    model: str,
    grader_mcp: MCPServerStdio,
    analyst_mcp: MCPServerStdio,
    run_config: RunConfig,
    assignment_idx: str,
) -> None:
    """Run the baseline workflow with a single agent."""
    async with grader_mcp, analyst_mcp:
        agent = BaselineTAAgent(
            model=model,
            analyst_mcp=analyst_mcp,
            grader_mcp=grader_mcp,
            run_config=run_config,
        )

        for submission_idx in await get_submissions(analyst_mcp, assignment_idx):
            await agent.grade(assignment_idx, submission_idx)
            print(f"Grading completed for submission {submission_idx}")


def main() -> None:
    """Review a local ZIP using an assignment and a JSON or YAML policy."""
    parser = argparse.ArgumentParser(
        description="Source-grounded AI lab review through scoped MCP tools"
    )
    parser.add_argument(
        "assignment_idx", type=str, help="Identifier for the assignment"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("TA_MCP_MODEL", "gpt-4.1-mini"),
        help="OpenAI model identifier",
    )
    parser.add_argument(
        "--workflow",
        choices=["multiagent", "baseline"],
        default="multiagent",
        help="Grading workflow: 'multiagent' (analyst + grader) or 'baseline' (single agent)",
    )
    arguments = parser.parse_args()

    run_config = RunConfig(group_id=str(uuid.uuid4()))

    grader_mcp = MCPServerStdio(
        params=MCPServerStdioParams(
            command=sys.executable, args=["-m", "ta_mcp", "grader"]
        )
    )

    analyst_mcp = MCPServerStdio(
        params=MCPServerStdioParams(
            command=sys.executable, args=["-m", "ta_mcp", "analyst"]
        )
    )

    if arguments.workflow == "multiagent":
        asyncio.run(
            multiagent_workflow(
                model=arguments.model,
                grader_mcp=grader_mcp,
                analyst_mcp=analyst_mcp,
                run_config=run_config,
                assignment_idx=arguments.assignment_idx,
            )
        )
    else:
        asyncio.run(
            baseline_workflow(
                model=arguments.model,
                grader_mcp=grader_mcp,
                analyst_mcp=analyst_mcp,
                run_config=run_config,
                assignment_idx=arguments.assignment_idx,
            )
        )


if __name__ == "__main__":
    main()
