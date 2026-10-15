from mcp.server.mcpserver import MCPServer, Context
from agents import Agent, Runner
from pathlib import Path

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
    rubric = await Runner.run(
        rubric_agent,
        assignment,
    )

    review = await Runner.run(
        grader_agent,
        f"Rubric:\n{rubric.final_output}\n\nTask:\n{path_to_task}",
    )

    return review.final_output
