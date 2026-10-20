# Analyst requirements and rubric

Rubric: `e305f884-a169-4560-b97c-9b19dfb43d3b`
Scoring mode: POINTS
Maximum base points: 5
Needs clarification: False

## Criteria for the Grader

| Code | Criterion | Points | Verification method |
| --- | --- | --- | --- |
| CRIT-BUILD | Build | 1 | Run cmake configuration and build commands and verify that count_even is generated without errors. |
| CRIT-CORRECTNESS | Correctness | 2 | Run the executable with various valid intervals (including negative numbers, zero, and single-value intervals) and verify correct counts. |
| CRIT-CLI-VALIDATION | CLI validation | 1 | Execute program with incorrect argument counts, out-of-range arguments, non-integers, and left &gt; right, checking exit codes (1 or 2) and non-empty stderr. |
| CRIT-OUTPUT-FORMAT | Output format | 1 | Inspect standard output and standard error across successful and error test cases to verify exact formatting. |

## Requirements and sources

### REQ-BUILD

The project must compile using CMake to create the count_even executable without errors.

Necessity: mandatory; state: clear; criteria: CRIT-BUILD.
Source: assignment lines 53 through 55.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |

### REQ-CLI-VALIDATION

The program must validate CLI arguments, exiting with code 1 for wrong argument count and code 2 for invalid numbers, out-of-range values, or left &gt; right, printing clear error messages to stderr.

Necessity: mandatory; state: clear; criteria: CRIT-CLI-VALIDATION.
Source: assignment lines 53 through 57.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |

### REQ-CORRECTNESS

The program must compute correct results for even integer counts across the inclusive interval [left, right], including zero and negative numbers.

Necessity: mandatory; state: clear; criteria: CRIT-CORRECTNESS.
Source: assignment lines 53 through 56.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |

### REQ-OUTPUT-FORMAT

On success, output must contain only one integer and a newline in stdout. On errors, stdout must be empty and errors directed to stderr.

Necessity: mandatory; state: clear; criteria: CRIT-OUTPUT-FORMAT.
Source: assignment lines 53 through 58.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |
> | Output format | 1 | Only one integer and a newline in stdout on success; stderr on errors |
