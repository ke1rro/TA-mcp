from pathlib import Path
from agents import Agent, Runner
from mcp.server.mcpserver import MCPServer, Context

mcp = MCPServer("TA-mcp")

rubric_agent = Agent(
    name="Rubric Architect",
    instructions="Generate grading criteria from the assignment.",
)

grader_agent = Agent(
    name="Lab Grader",
    instructions="Evaluate code according to the rubric.",
)


@mcp.tool()
async def grade_submission(
    assignment: str,
    path_to_task: Path,
) -> str:
    """Grade a student source file against the assignment."""
    code = path_to_task.read_text(encoding="utf-8")

    rubric = await Runner.run(
        rubric_agent,
        assignment,
    )

    review = await Runner.run(
        grader_agent,
        f"Rubric:\n{rubric.final_output}\n\nCode:\n{code}",
    )

    return str(review.final_output)


if __name__ == "__main__":
    mcp.run()
