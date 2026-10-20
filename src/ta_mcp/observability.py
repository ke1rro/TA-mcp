import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Literal
from uuid import uuid4

from httpx2 import Request, Response
from openai import APIStatusError, APITimeoutError, OpenAIError
from pydantic import ValidationError

AGENT_NAMES = {
    "analyst": "Requirements Analyst",
    "grader": "Submission Grader",
    "orchestrator": "Coordinator",
}


class RequestLimitReached(RuntimeError):
    """Exhausted local LLM request budget before another HTTP attempt."""


def describe_error(error: BaseException) -> dict[str, object]:
    """Describe a failure without exposing provider bodies or model outputs.

    Args:
        error: Exception raised at a model, tool or validation boundary.

    Returns:
        Safe exception metadata and an operator-facing recovery instruction.
    """
    details: dict[str, object] = {"error_type": type(error).__name__}
    if isinstance(error, APIStatusError):
        details["http_status"] = error.status_code
        if error.status_code >= 500:
            details["recovery"] = (
                "Provider service failed; no automatic retry. Retry manually later."
            )
        elif error.status_code == 429:
            details["recovery"] = (
                "Quota or rate limit reached; no automatic retry. Check the provider "
                "quota before starting another run."
            )
        else:
            details["recovery"] = (
                "Check the API model ID, project access and credentials locally. "
                "No automatic retry."
            )
    elif isinstance(error, (APITimeoutError, TimeoutError)):
        details["recovery"] = (
            "Model call exceeded the configured wait limit; no automatic retry. "
            "Retry manually later or increase --llm-timeout. "
            "A timeout alone does not establish a quota or credential failure."
        )
    elif isinstance(error, RequestLimitReached):
        details["recovery"] = "Local request cap reached; no further request was sent."
    elif isinstance(error, ValidationError):
        details["validation_errors"] = [
            {
                "field": ".".join(str(part) for part in item["loc"]),
                "type": item["type"],
                **(
                    {"message": item["msg"][:500]}
                    if item["type"] == "value_error"
                    else {}
                ),
            }
            for item in error.errors(include_input=False, include_context=False)[:8]
        ]
        details["recovery"] = (
            "Structured output rejected. Gemini --repair-output permits one repair "
            "within --max-llm-requests; invalid repaired output is still rejected."
        )
    elif isinstance(error, OpenAIError):
        details["recovery"] = (
            "Provider connection or response failed; no automatic retry. "
            "Check the network before another manual attempt."
        )
    elif type(error) is ValueError:
        safe_messages = {
            "Requirement source quote does not match assignment lines",
            "Point amount is not explicitly present in source quote",
            "Criterion must belong to this rubric and cite source",
            "Unknown criterion/source requirement link",
            "Rubric base total disagrees with core allocation",
            "Use a Gemini API model ID such as gemini-3.8-flash",
            "Set GEMINI_API_KEY in .env to run the two LLM agents",
            "Set OPENAI_API_KEY in .env to run the two LLM agents",
        }
        if str(error) in safe_messages:
            details["message"] = str(error)
        details["recovery"] = "Validation failed; no automatic repair or retry."
    else:
        details["recovery"] = "Review local inputs and the last successful trace event."
    return details


class ExecutionLog:
    """Live terminal events, optional JSONL output and a shared HTTP budget.

    Args:
        is_verbose: Display progressive events on stderr when enabled.
        trace_path: New JSONL file to create exclusively, or no trace file.
        max_llm_requests: Maximum model HTTP attempts across both agents.
    """

    def __init__(
        self,
        is_verbose: bool = False,
        trace_path: Path | None = None,
        max_llm_requests: int = 2,
    ) -> None:
        if max_llm_requests < 1:
            raise ValueError("The LLM request limit must be positive")
        self.is_verbose = is_verbose
        self.max_llm_requests = max_llm_requests
        self.trace_path = trace_path
        self.stream = None
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            self.stream = trace_path.open("x", encoding="utf-8")
        self.session_id = str(uuid4())
        self.run_id: str | None = None
        self.provider = "unconfigured"
        self.model_name = "unconfigured"
        self.agent_role = "orchestrator"
        self.started_at = monotonic()
        self.api_requests = 0
        self.llm_requests = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.usage_reports = 0

    def emit(
        self,
        category: Literal["AGENT", "LLM", "MCP", "ERROR", "SYSTEM"],
        event: str,
        role: str = "orchestrator",
        details: dict[str, object] | None = None,
    ) -> None:
        """Flush an event containing only caller-selected safe metadata.

        Args:
            category: Terminal category for the event.
            event: Stable event name without user-provided text.
            role: Current workflow role.
            details: Whitelisted metadata prepared at the calling boundary.
        """
        record = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "session_id": self.session_id,
            "run_id": self.run_id,
            "category": category,
            "event": event,
            "agent_role": role,
            "agent_name": AGENT_NAMES[role],
            "provider": self.provider,
            "model": self.model_name,
            "elapsed_ms": round((monotonic() - self.started_at) * 1000),
            "details": details or {},
        }
        if self.stream is not None:
            self.stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.stream.flush()
        if self.is_verbose or category == "ERROR" or event == "run_summary":
            metadata = json.dumps(record["details"], ensure_ascii=False)
            print(
                f"{record['timestamp']} [{category}] {role}/"
                f"{record['agent_name']} {event} {metadata}",
                file=sys.stderr,
                flush=True,
            )

    def require_llm_slot(self) -> None:
        """Reject another LLM call when the shared budget has been exhausted."""
        if self.llm_requests >= self.max_llm_requests:
            self.emit(
                "ERROR",
                "request_limit_reached",
                self.agent_role,
                {"llm_requests": self.llm_requests, "limit": self.max_llm_requests},
            )
            raise RequestLimitReached("Local LLM request limit reached")

    async def api_request_started(self, request: Request) -> None:
        """Count and log an HTTP attempt without reading its headers or body.

        Args:
            request: Provider request passed by the HTTP client's event hook.
        """
        is_llm_request = request.url.path.endswith(("/chat/completions", "/responses"))
        if is_llm_request:
            self.require_llm_slot()
            self.llm_requests += 1
        self.api_requests += 1
        self.emit(
            "LLM" if is_llm_request else "SYSTEM",
            "request_start",
            self.agent_role,
            {
                "method": request.method,
                "endpoint": request.url.path,
                "model": self.model_name,
                "api_requests": self.api_requests,
                "llm_requests": self.llm_requests,
                "limit": self.max_llm_requests,
            },
        )

    async def api_response_received(self, response: Response) -> None:
        """Log HTTP status without exposing the provider response body.

        Args:
            response: Provider response passed by the HTTP client's event hook.
        """
        self.emit(
            "ERROR" if response.status_code >= 400 else "LLM",
            "http_response",
            self.agent_role,
            {"http_status": response.status_code, "automatic_retry": False},
        )

    def close(self) -> None:
        """Display final counters and close the flushed JSONL stream."""
        self.emit(
            "SYSTEM",
            "run_summary",
            details={
                "provider": self.provider,
                "model": self.model_name,
                "api_requests": self.api_requests,
                "llm_requests": self.llm_requests,
                "limit": self.max_llm_requests,
                "input_tokens": self.input_tokens if self.usage_reports else None,
                "output_tokens": self.output_tokens if self.usage_reports else None,
                "usage_reports": self.usage_reports,
                "usage_is_partial": self.usage_reports < self.llm_requests,
                "trace_file": str(self.trace_path) if self.trace_path else None,
                "duration_ms": round((monotonic() - self.started_at) * 1000),
            },
        )
        if self.stream is not None:
            self.stream.close()
