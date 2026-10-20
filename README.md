# TA-mcp: manual multi-agent grading demo

TA-mcp reviews one student ZIP against an assignment, produces evidence-backed findings, and saves `review.json` and `review.md`. Grades are recommendations for the instructor.

The demo uses **Count Even Numbers, C++17**:

- `TA_mcp_mini_assignment.md`: the English assignment and its 5-point rubric.
- `TA_mcp_five_mini_submissions.zip`: five independent student ZIPs.

Keep `TA_mcp_evaluation_gold.json` outside agent inputs. Do not pass it as an assignment, policy, submission, or archive member. The application reads the explicitly selected inputs.

## Two agents and MCP

1. The coordinator connects to MCP as `analyst` and inspects the archive.
2. **Requirements Analyst** receives the assignment and policy, without student code. It returns source-backed requirements and a rubric.
3. Python validates citations, references, and point allocations, then saves the analyst handoff.
4. The coordinator connects as `grader`, confirms the archive, and invokes the available checks.
5. **Submission Grader** receives the frozen rubric, source previews, and actual check results. It returns assessments and evidence.
6. Python validates evidence, calculates totals using `Decimal`, and calls MCP `save_review`.

Both agents use the configured Gemini model through the OpenAI Agents SDK and Chat Completions compatibility API. The model returns text containing JSON. The Python coordinator calls MCP tools; model-side tool calling is unnecessary. Pydantic validates structured responses.

| MCP tool | Purpose | Allowed roles |
| --- | --- | --- |
| `inspect_archive` | Validate a ZIP in memory and return a manifest and bounded text previews. | `analyst`, `grader` |
| `run_checks` | Freeze the rubric and policy, compile the mini submission, and check numerical results, CLI behavior, and output. | `grader` |
| `save_review` | Verify evidence against source and tool receipts, then save reports and SQLite audit records. | `grader` |

Each role uses a separate scoped stdio MCP process. Permissions are enforced by server registration and the client allowlist. The analyst has no `run_checks` or `save_review` capability. The coordinator writes traces and handoff snapshots. Gemini credentials are excluded from the CMake and student-process environments.

## Installation

Use Python 3.14 and `uv`:

```bash
cd /Users/nikitalenyk/Desktop/TA-mcp
uv sync --locked --no-editable --reinstall-package ta-mcp
```

The reinstall option refreshes the installed project after source changes. `--no-editable` avoids the hidden `.pth` issue observed in this macOS workspace. SQLite needs no separate database server.

The local C++ checks require `cmake`, a C++17 compiler, and a build tool in `PATH`. For the mini assignment, checks run on your computer with your user permissions in a temporary directory. Configuration is limited to 30 seconds, compilation to 45 seconds with two build jobs, and each student execution to 2 seconds. CPU time, output file size, open descriptors, and core dumps are bounded. There are 10 valid-input cases and 11 invalid-input cases. No Docker installation is required for this local demo.

## Environment

Create `.env` only if it does not exist:

```bash
test -f .env || cp .env.example .env
```

Edit it locally:

```dotenv
GEMINI_API_KEY=your_key_here
TA_MCP_PROVIDER=gemini
TA_MCP_MODEL=gemini-3.8-flash
TA_MCP_MAX_LLM_REQUESTS=2
TA_MCP_LLM_TIMEOUT_SECONDS=180
```

Use an API model identifier available to your project. An AI Studio display name is insufficient. The application strips an optional `models/` prefix and makes no model-discovery request. It does not automatically substitute another model. Do not expose `.env` or API keys in recordings, logs, or chat.

The application loads `.env` from the current directory. Exported environment variables take precedence over `.env`; CLI options take precedence over the corresponding environment values. `--llm-timeout` controls the HTTP timeout, with five additional seconds for the coordinator's agent deadline.

## Extract the submissions

```bash
mkdir -p gemini_agent_test/inputs
unzip -n TA_mcp_five_mini_submissions.zip 'submissions/*.zip' \
  -d gemini_agent_test/inputs
```

This only extracts the five nested ZIP files. Pass one nested ZIP to TA-mcp, rather than the outer package. Use the English assignment from the repository root; the package's original assignment copy is not loaded.

## Review one submission manually

This command sends live Gemini requests:

```bash
uv run --no-editable ta-mcp \
  --provider gemini \
  --submission gemini_agent_test/inputs/submissions/submission_01.zip \
  --requirements TA_mcp_mini_assignment.md \
  --policy examples/policy.yaml \
  --output gemini_agent_test/reviews \
  --database gemini_agent_test/audit.sqlite \
  --verbose \
  --llm-timeout 180 \
  --trace-file "gemini_agent_test/traces/submission_01_$(date +%Y%m%d_%H%M%S).jsonl" \
  --max-llm-requests 2
```

A successful run normally uses two LLM requests: one per agent. Automatic HTTP, SDK, MCP, and rate-limit retries are disabled. JSON repair is disabled by default. The request cap is shared by both agents within one process. A cap of 1 can stop the workflow after analysis without creating a review. Trace files are created exclusively; timestamped names allow repeated manual runs without overwriting a trace.

For a Gemini response rejected by Pydantic, such as an unexpected `$defs` field, add `--repair-output --max-llm-requests 3`. This permits one additional model call across the entire workflow, using the same role agent, original input, rejected JSON, and validation errors. A valid initial response needs no repair call. The repaired output must pass the same strict contract; unknown fields are never silently discarded. Source citations, scoring rules, and evidence still undergo the existing workflow validation. Semantic validation failures after parsing, HTTP errors, and timeouts do not trigger repair.

The repair consumes the shared HTTP budget and reported tokens. Logs include `output_validation_failed`, `output_repair_start`, and, only after successful validation, `output_repair_complete`. They do not include rejected JSON or repair prompts. `--llm-timeout` remains the per-request timeout; with repair enabled, each role's outer deadline allows two request windows plus cleanup time. No additional repair is attempted if either role already used it.

For a repeatable manual JSON repair demonstration, additionally use `--demo-json-error`. It requires `--repair-output --max-llm-requests 3`. After the first contract-valid Gemini response, the coordinator deliberately adds the forbidden root field `demo_extra_field`. Pydantic rejects it, and the existing repair path makes a real additional Gemini request. Logs explicitly record `demo_fault_injected`, `injected_by: coordinator`, and `original_contract_valid: true`. This is deliberate fault injection, not an observed model mistake or an MCP tool error. If the original response is already invalid, its natural validation failure uses the single repair instead; no additional fault is injected. API availability and a successful repaired response cannot be guaranteed. Keep such runs separate from measurements of natural model error rates. Without the flag, no fault is injected.

## Review all five manually

This sequential loop starts up to five processes and allows at most ten LLM request attempts. Each process has a cap of two. It stops at the first failure:

```bash
for submission_id in 01 02 03 04 05; do
  uv run --no-editable ta-mcp \
    --provider gemini \
    --submission "gemini_agent_test/inputs/submissions/submission_${submission_id}.zip" \
    --requirements TA_mcp_mini_assignment.md \
    --policy examples/policy.yaml \
    --output gemini_agent_test/reviews \
    --database gemini_agent_test/audit.sqlite \
    --verbose \
    --llm-timeout 180 \
    --trace-file "gemini_agent_test/traces/submission_${submission_id}_$(date +%Y%m%d_%H%M%S).jsonl" \
    --max-llm-requests 2 || break
done
```

Review your provider quota before starting the loop. To continue a stopped batch, list only the submission numbers still needed. Requests from other programs and previous attempts also affect the real provider quota.

## Live observability

`--verbose` streams events to stderr and flushes each event. `--trace-file` writes the same events as JSONL and flushes every record. Either option can be used independently.

| Category | Visible information |
| --- | --- |
| `AGENT` | Agent start and completion, role names, criterion and assessment counts. |
| `LLM` | Request start and completion, model, HTTP status, duration, request counters, input size, and reported token usage. |
| `MCP` | Tool name, sanitized arguments, status, duration, and concise results. |
| `SYSTEM` | Provider settings, connections, handoffs, validation, saved artifact paths, and the final summary. |
| `ERROR` | Request caps, API errors, validation failures, tool errors, and interruption. |

Events contain UTC timestamps, session and run IDs, agent names, and elapsed time. During a non-streaming model request, `request_start` may remain the last event until the provider responds. The application does not display hidden reasoning. It does not log authorization headers, API bodies, complete prompts, or student source code.

`run_summary` reports HTTP attempts, LLM attempts, duration, and available token usage. Failed requests may have unknown usage, shown as `null`. These counters do not show remaining Google quota. Use Ctrl+C to interrupt a run; an already-sent request may still count toward provider usage.

## Outputs and the analyst handoff

```text
gemini_agent_test/
  audit.sqlite
  traces/submission_<number>_<timestamp>.jsonl
  handoffs/<run_id>/analyst.json
  handoffs/<run_id>/analyst.md
  checks/<run_id>/checks.json
  checks/<run_id>/*.log
  reviews/<run_id>/review.json
  reviews/<run_id>/review.md
  reviews/<run_id>/COMPLETED
```

Immediately after analyst validation, `analyst_handoff_saved` prints the paths to the exact structured `RubricAnalysis` and its readable Markdown view. Open these while the grader is running. They remain available if grading fails later. Saving them adds no LLM requests.

The final CLI output prints report paths and the score. `COMPLETED` confirms persistence, even when the grading state is `NEEDS_REVIEW`. JSON, Markdown, completion markers, and SQLite checksums form an immutable audit record.

Both agents are instructed to generate English narrative text. The assignment and Markdown headings are also English. Exact source and diagnostic evidence is preserved in its original language. Historical English presentation copies use `.en.md`; they do not replace the original audited JSON or source quotes and do not represent a new grading run.

If final validation fails, `review_validation_failed` reports the reason and saves `checks/<run_id>/invalid-review.json`. This is an unvalidated diagnostic draft, not a completed review. It can contain short source excerpts. The coordinator resolves citation positions only when the exact diagnostic has one unique match in an actual executed check. Unknown or ambiguous evidence remains subject to strict validation. Offset corrections are logged as `evidence_offsets_resolved` and use no extra LLM requests.

The final report's `trace_events` contain coordinator audit events. The JSONL trace also contains HTTP counters and final persistence events. Avoid enabling raw third-party DEBUG logs.

## Interpret the grade

The rubric assigns build 1 point, correctness 2 points, CLI validation 1 point, and output format 1 point. General style preferences do not introduce additional penalties.

- `PASS`: evidence establishes compliance.
- `PARTIAL`: evidence supports a partial award with an explanation.
- `FAIL`: a verified defect is supported by source or execution evidence.
- `NOT_VERIFIABLE`: the available evidence is insufficient.

`UNAVAILABLE` describes a tool check; `NOT_VERIFIABLE` describes a criterion assessment. An unavailable compilation check does not prove a build failure. Unresolved criteria can leave the final score null with lower and upper bounds. `UNSCORED` means no valid numeric allocation was established. Recommendations alone are not proven defects.

The mini checker has no dedicated C++ static analyzer or memory checker. Python AST analysis is unavailable for a C++-only archive, and memory checks are disabled by the example policy. These are not additional mini-assignment grading criteria. Keep any comparison with the separate gold file outside agent context.

## Single-agent baseline

The single-agent baseline is not implemented. The data-model enum value `SINGLE_AGENT_BASELINE` does not provide a runtime workflow. The CLI has no `--single-agent`, `--baseline`, or `--strategy` option. Current commands use the two existing agents.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Missing input | Check the working directory, filenames, and ZIP extraction. |
| Missing key, HTTP 401 or 403 | Check `.env`, exported variables, and project permissions locally. Never print the key. |
| HTTP 404 or model rejection | Check the API model ID and project access. No automatic model substitution occurs. |
| HTTP 429 | Check provider rate limits and quota before a new manual attempt. There is no automatic retry. |
| HTTP 503 | The provider returned a server error. Retry manually later. The status alone does not prove a key or quota problem. |
| `APITimeoutError` or `TimeoutError` | The wait limit expired. Retry later or adjust `--llm-timeout`; no automatic retry occurs. |
| `RequestLimitReached` | The local shared request cap was exhausted. Inspect `run_summary`. |
| `ValidationError` | Inspect the field, validation stage, and any saved invalid draft. Invalid citations, enum values, IDs, JSON, or scores block completion. |
| MCP error | Inspect the role, tool name, error code, authorized paths, and directory permissions. |
| Existing trace file | Select a new trace filename. This failure occurs before any API request. |
| `ModuleNotFoundError: ta_mcp` or unknown new CLI option | Repeat installation with `--no-editable --reinstall-package ta-mcp`. |

Run full grading commands manually. Setup, formatting, and offline report inspection do not require Gemini requests.
