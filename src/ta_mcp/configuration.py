import json
from pathlib import Path

import yaml

from ta_mcp.domain import GradingPolicy


def read_policy(path: Path) -> GradingPolicy:
    """Load a bounded JSON or safe YAML policy with closed fields."""
    text = read_text_input(path)
    payload = (
        json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    )
    return GradingPolicy.model_validate(payload)


def read_text_input(path: Path) -> str:
    """Read bounded UTF-8 configuration or assignment text."""
    with path.open("rb") as stream:
        content = stream.read(100001)
    if len(content) > 100000:
        raise ValueError("Text input exceeds the 100000-byte limit")
    return content.decode("utf-8")
