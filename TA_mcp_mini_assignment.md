# Mini Laboratory Assignment 1: Count Even Numbers (C++17)

## Goal

Implement a small C++17 command-line program that counts **even integers** in the **inclusive interval [left, right]**. This is an independent demonstration assignment for AI Lab Grader, **not part of the numerical integration assignment**.

## 1. Program requirements

- Executable name: `count_even` (`count_even.exe` is acceptable on Windows).
- Interface: `count_even <left> <right>` with **exactly two** command-line arguments.
- Both arguments must be decimal integers from `-1000` to `1000`, inclusive.
- The condition `left <= right` must hold.
- An even number is an integer `n` for which `n % 2 == 0`. **Zero and negative even numbers must also be counted.**
- On success, print **only one integer count** to `stdout`, followed by `\n`. No other text is allowed in `stdout`.

### Examples

```text
$ ./count_even 1 5
2
$ ./count_even -3 3
3
$ ./count_even 0 0
1
```

## 2. Errors and exit codes

| Situation | Exit code | Output |
|---|---:|---|
| Success | `0` | Only the result in `stdout` |
| The number of arguments is not two | `1` | A clear message in `stderr` |
| Invalid number, a value outside `[-1000, 1000]`, or `left > right` | `2` | A clear message in `stderr` |

On error, `stdout` must be empty. Interactive input is prohibited.

## 3. Compilation and submission

- Language: C++17, or a newer version with C++17-compatible code.
- Include `main.cpp` and `CMakeLists.txt`, which must create the `count_even` executable.
- The project must compile using the standard commands:

```bash
cmake -S . -B build
cmake --build build
./build/count_even -3 3
```

- No third-party libraries are required.

## 4. Grading criteria (5 points)

| Criterion | Points | What is checked |
|---|---:|---|
| Build | 1 | CMake creates `count_even` without errors |
| Correctness | 2 | Correct results, inclusive bounds, zero and negative values |
| CLI validation | 1 | Correct exit codes and messages for invalid arguments |
| Output format | 1 | Only one integer and a newline in stdout on success; stderr on errors |

**Important for the AI reviewer:** if the program does not compile, do not claim that runtime tests passed. State exactly what was verified and what was unavailable. Every finding must reference source code or a reproducible execution. Do not invent points for additional criteria.

## 5. Minimal review procedure

1. Read the code; do not trust comments or README claims instead of verification.
2. Compile using CMake.
3. If the build succeeds, check positive and negative bounds, inclusion of the right endpoint, `0`, incorrect argument counts and invalid numbers.
4. Record concrete check results and the final grade under the rubric.

For this demonstration, **one** build and a short set of executions are sufficient. Sanitizers, Valgrind, PVS-Studio, benchmarks and large testing frameworks are unnecessary. Execute student ZIP contents only in a controlled, isolated environment.
