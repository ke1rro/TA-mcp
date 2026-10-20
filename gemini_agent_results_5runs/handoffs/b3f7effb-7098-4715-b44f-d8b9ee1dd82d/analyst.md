# Analyst requirements and rubric

Rubric: `8cb60c41-a67b-4d4b-972d-d01c6f5db1d4`
Scoring mode: POINTS
Maximum base points: 5
Needs clarification: False

## Criteria for the Grader

| Code | Criterion | Points | Verification method |
| --- | --- | --- | --- |
| CRIT-BUILD | Build | 1 | Execute CMake configure and build commands (`cmake -S . -B build &amp;&amp; cmake --build build`) and verify successful creation of the `count_even` executable. |
| CRIT-CORRECTNESS | Correctness | 2 | Run test cases covering positive/negative bounds, inclusion of endpoints, and ranges containing 0 (e.g. `1 5` -&gt; 2, `-3 3` -&gt; 3, `0 0` -&gt; 1). |
| CRIT-CLI-VALIDATION | CLI validation | 1 | Verify exit code 1 with stderr output when arg count != 2, and exit code 2 with stderr output when numbers are invalid, outside [-1000, 1000], or left &gt; right. |
| CRIT-OUTPUT-FORMAT | Output format | 1 | Verify stdout contains only the integer count followed by &#x27;\n&#x27; on success, and stdout is completely empty on error conditions. |

## Requirements and sources

### REQ-BUILD

CMake creates the count_even executable without errors using C++17 or newer.

Necessity: mandatory; state: clear; criteria: CRIT-BUILD.
Source: assignment lines 53 through 55.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |

### REQ-CLI-VALIDATION

Validate CLI arguments: exit code 1 with stderr message if argument count is not two; exit code 2 with stderr message if invalid number, outside [-1000, 1000], or left &gt; right.

Necessity: mandatory; state: clear; criteria: CRIT-CLI-VALIDATION.
Source: assignment lines 53 through 57.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |

### REQ-CORRECTNESS

Correct results counting even numbers in inclusive interval [left, right], including zero and negative values.

Necessity: mandatory; state: clear; criteria: CRIT-CORRECTNESS.
Source: assignment lines 53 through 56.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |

### REQ-OUTPUT-FORMAT

Output format: print only one integer count followed by \n to stdout on success with exit code 0; on error, stdout must be empty and message in stderr.

Necessity: mandatory; state: clear; criteria: CRIT-OUTPUT-FORMAT.
Source: assignment lines 53 through 58.

> | Criterion | Points | What is checked |
> |---|---:|---|
> | Build | 1 | CMake creates `count_even` without errors |
> | Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
> | CLI validation | 1 | Correct exit codes and messages for invalid arguments |
> | Output format | 1 | Only one integer and a newline in stdout on success; stderr on errors |
