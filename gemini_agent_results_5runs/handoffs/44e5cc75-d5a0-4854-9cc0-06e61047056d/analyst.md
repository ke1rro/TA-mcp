# Analyst requirements and rubric

Rubric: `76e31ba6-d586-4444-a621-3fc7d4902875`
Scoring mode: POINTS
Maximum base points: 5
Needs clarification: False

## Criteria for the Grader

| Code | Criterion | Points | Verification method |
| --- | --- | --- | --- |
| CRIT-BUILD | Build | 1 | Run `cmake -S . -B build` and `cmake --build build`, verifying that build completes successfully and produces the executable. |
| CRIT-CORRECTNESS | Correctness | 2 | Execute `count_even` on test intervals including positive, negative, zero, and single-element bounds, checking the returned count. |
| CRIT-CLI-VALIDATION | CLI validation | 1 | Run `count_even` with invalid argument counts (expecting exit code 1), non-integers, out-of-range values, and left &gt; right (expecting exit code 2 and stderr message). |
| CRIT-OUTPUT-FORMAT | Output format | 1 | Verify stdout format on success contains only the single count integer followed by \n; verify stdout is empty and errors are routed to stderr on failure. |

## Requirements and sources

### REQ-BUILD-CMAKE

CMake creates the count_even executable without errors using standard cmake commands.

Necessity: mandatory; state: clear; criteria: CRIT-BUILD.
Source: assignment lines 53 through 55.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |

### REQ-CLI-VALIDATION

Handle invalid arguments with correct exit codes and error messages in stderr (exit code 1 if argument count != 2, exit code 2 if invalid number, outside [-1000, 1000], or left &gt; right).

Necessity: mandatory; state: clear; criteria: CRIT-CLI-VALIDATION.
Source: assignment lines 53 through 57.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |

### REQ-CORRECTNESS

Count even integers correctly in the inclusive interval [left, right], including zero, positive, and negative values.

Necessity: mandatory; state: clear; criteria: CRIT-CORRECTNESS.
Source: assignment lines 53 through 56.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |

### REQ-OUTPUT-FORMAT

On success, print only one integer count followed by a newline to stdout with exit code 0; on error, stdout must be empty and a clear message printed to stderr.

Necessity: mandatory; state: clear; criteria: CRIT-OUTPUT-FORMAT.
Source: assignment lines 53 through 58.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |
> | Output format | 1 | Only one integer and a newline in stdout on success; stderr on errors |
