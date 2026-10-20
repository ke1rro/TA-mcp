# Analyst requirements and rubric

Rubric: `6b5e6291-4f71-50ec-b9e0-3e29783fffc5`
Scoring mode: POINTS
Maximum base points: 5
Needs clarification: False

## Criteria for the Grader

| Code | Criterion | Points | Verification method |
| --- | --- | --- | --- |
| CRIT_BUILD | Build | 1 | Run `cmake -S . -B build` followed by `cmake --build build` and check for successful creation of the `count_even` executable without build errors. |
| CRIT_CORRECTNESS | Correctness | 2 | Execute the binary with representative valid inputs including positive, negative, zero, and single-value ranges (e.g. 1 5, -3 3, 0 0) and verify that the count of even numbers in [left, right] is correct. |
| CRIT_CLI_VALIDATION | CLI validation | 1 | Invoke the program with invalid argument counts (expecting exit code 1) and with invalid numbers, values outside [-1000, 1000], or left &gt; right (expecting exit code 2), ensuring error messages are printed to stderr. |
| CRIT_OUTPUT_FORMAT | Output format | 1 | Verify that successful runs emit exactly one integer followed by newline to stdout with no extra text, and erroneous runs keep stdout completely empty while writing error messages to stderr. |

## Requirements and sources

### REQ_BUILD

CMake configuration and build must successfully compile and create the count_even executable without errors.

Necessity: mandatory; state: clear; criteria: CRIT_BUILD.
Source: assignment lines 53 through 55.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |

### REQ_CLI_VALIDATION

Validate CLI arguments, producing exit code 1 if argument count is not two, and exit code 2 for invalid numbers, numbers outside [-1000, 1000], or left &gt; right, printing a clear message to stderr.

Necessity: mandatory; state: clear; criteria: CRIT_CLI_VALIDATION.
Source: assignment lines 53 through 57.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |

### REQ_CORRECTNESS

The program must correctly count even integers in the inclusive interval [left, right], including zero and negative even numbers.

Necessity: mandatory; state: clear; criteria: CRIT_CORRECTNESS.
Source: assignment lines 53 through 56.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |

### REQ_OUTPUT_FORMAT

On success, output must contain only one integer count followed by \n to stdout with no other text. On error, stdout must be empty and errors sent to stderr.

Necessity: mandatory; state: clear; criteria: CRIT_OUTPUT_FORMAT.
Source: assignment lines 53 through 58.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |
> | Output format | 1 | Only one integer and a newline in stdout on success; stderr on errors |
