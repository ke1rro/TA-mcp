# Analyst requirements and rubric

Rubric: `bb49872e-0ee8-4c9b-b0b3-1cb0e4c6c2b1`
Scoring mode: POINTS
Maximum base points: 5
Needs clarification: False

## Criteria for the Grader

| Code | Criterion | Points | Verification method |
| --- | --- | --- | --- |
| CRIT_BUILD | Build | 1 | Run `cmake -S . -B build` and `cmake --build build` to verify clean compilation without errors producing the `count_even` executable. |
| CRIT_CORRECTNESS | Correctness | 2 | Execute CLI runs across positive, negative, zero, and boundary intervals (e.g. 1 5 -&gt; 2; -3 3 -&gt; 3; 0 0 -&gt; 1) and verify the counted even values. |
| CRIT_CLI_VALIDATION | CLI validation | 1 | Execute tests with arity != 2 (expect exit code 1 and stderr message), and with non-integer inputs, out-of-range inputs (&lt; -1000 or &gt; 1000), or left &gt; right (expect exit code 2 and stderr message). |
| CRIT_OUTPUT_FORMAT | Output format | 1 | Inspect standard output on successful runs to ensure exactly one integer count and a newline with no other text, and verify stdout is completely empty on error conditions. |

## Requirements and sources

### REQ_BUILD

The project must include main.cpp and CMakeLists.txt, which builds the executable count_even (or count_even.exe) without errors using CMake and C++17.

Necessity: mandatory; state: clear; criteria: CRIT_BUILD.
Source: assignment lines 53 through 55.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |

### REQ_CLI_VALIDATION

CLI validation must reject argument counts other than two with exit code 1 and a message in stderr, and reject invalid numbers, values outside [-1000, 1000], or left &gt; right with exit code 2 and a message in stderr.

Necessity: mandatory; state: clear; criteria: CRIT_CLI_VALIDATION.
Source: assignment lines 53 through 57.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |

### REQ_CORRECTNESS

The program must correctly count even integers in the inclusive interval [left, right], properly accounting for zero, negative values, and inclusive bounds.

Necessity: mandatory; state: clear; criteria: CRIT_CORRECTNESS.
Source: assignment lines 53 through 56.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |

### REQ_OUTPUT_FORMAT

On success, print only one integer count followed by newline to stdout (no other text). On error, stdout must be empty and error messages must go to stderr.

Necessity: mandatory; state: clear; criteria: CRIT_OUTPUT_FORMAT.
Source: assignment lines 53 through 58.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |
> | Output format | 1 | Only one integer and a newline in stdout on success; stderr on errors |
