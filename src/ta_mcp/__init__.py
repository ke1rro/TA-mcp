import argparse

from ta_mcp.analyst import mcp as analyst_mcp
from ta_mcp.grader import mcp as grader_mcp


def main():
    parser = argparse.ArgumentParser(
        description="Run the MCP servers for the Analyst and Grader."
    )
    parser.add_argument(
        "mcp_type",
        choices=["analyst", "grader"],
        help="Specify which MCP server to run: 'analyst' or 'grader'.",
    )
    args = parser.parse_args()

    if args.mcp_type == "analyst":
        analyst_mcp.run()
    elif args.mcp_type == "grader":
        grader_mcp.run()


if __name__ == "__main__":
    main()
