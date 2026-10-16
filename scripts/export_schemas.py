import json
from pathlib import Path

from pydantic import TypeAdapter

from ta_mcp.contracts import (
    InspectArchiveRequest,
    InspectArchiveResponse,
    RunChecksRequest,
    RunChecksResponse,
    SaveReviewRequest,
    SaveReviewResponse,
)
from ta_mcp.domain import GradingDecisions, GradingPolicy, ReviewBundle, RubricAnalysis


def main() -> None:
    """Export versioned public contract schemas deterministically."""
    output = Path(__file__).resolve().parents[1] / "schemas" / "1.0"
    output.mkdir(parents=True, exist_ok=True)
    contracts = {
        "review-bundle": ReviewBundle,
        "rubric-analysis": RubricAnalysis,
        "grading-decisions": GradingDecisions,
        "grading-policy": GradingPolicy,
        "inspect-archive-request": InspectArchiveRequest,
        "inspect-archive-response": InspectArchiveResponse,
        "run-checks-request": RunChecksRequest,
        "run-checks-response": RunChecksResponse,
        "save-review-request": SaveReviewRequest,
        "save-review-response": SaveReviewResponse,
    }
    for name, contract in contracts.items():
        schema = TypeAdapter(contract).json_schema()
        (output / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
