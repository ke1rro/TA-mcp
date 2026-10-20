# Lab review

Recommendation for human confirmation. This is not an official grade.

Run: `878f9775-b8d1-5381-8f54-2af7ac13866d`
State: **COMPLETED**
Assignment SHA-256: `65ee46d89b8a97d303d6ade8c630f38e8e754df9fc41f64a9e5ce35f5e0844f2`
Submission SHA-256: `42e249b29ed7c46213432c87d2e0cc065c4a253056aa15ebea1bc3e04cf6433e`

Known earned points: 3
Base: 3; bonus: 0; penalties: 0
Possible score: 3 to 3
Recommended score: 3

| Criterion | Status | Points | Explanation |
| --- | --- | --- | --- |
| Correctness | PASS | 2 / 2 | The inclusive loop counts zero, negative even integers, and both endpoints correctly for valid inputs. Cases -3 3, 0 0, 2 2, and -1000 1000 match the required results. |
| Build | PASS | 1 / 1 | The CMake configuration succeeds and the build completes the count_even executable. |
| Output format | FAIL | 0 / 1 | Invalid numeric input reaches the success output: abc 3 produces 2 plus a newline on stdout with empty stderr. This violates the explicit requirement that invalid input leave stdout empty and write an error to stderr. |
| CLI validation | FAIL | 0 / 1 | atoi silently converts abc to 0, 1.5 to 1, and 2x to 2. The program accepts these inputs with exit 0 and also omits the [-1000, 1000] bounds check. Argument-count and reversed-bound checks do not cover these failures. |

## Evidence

* `144b0e3a-e54c-54ac-80a0-64c2396c2749`: main.cpp:4-14. Inspected main.cpp:4-14 for cli validation.
* `1cc57c39-3d1a-5b53-b851-3639665ed85f`: main.cpp:9-20. Inspected main.cpp:9-20 for output format.
* `4c5cc13f-c03c-581e-8df4-cfb514454ac0`: check c024c65e-80bb-5693-b135-afe794fd79f0, stdout[1461:1564]. Check diagnostic for output format.
* `5259f9d4-ea6d-5fec-b020-d532d81aac8c`: CMakeLists.txt:1-5. Inspected CMakeLists.txt:1-5 for build.
* `557f4ef3-b546-5eb1-a7a8-93c614be882a`: main.cpp:15-20. Inspected main.cpp:15-20 for correctness.
* `a0ed4353-bfd2-57e9-a29e-bf44b0198dd1`: check c11d33ef-b257-55a7-8cd4-b642043c4f0f, stdout[67:169]. Check diagnostic for correctness.
* `b330d41e-e370-5718-b915-5d2c9841297f`: check 642263b1-292d-5176-b221-c35dc9cc2f0b, stdout[437:537]. Check diagnostic for cli validation.
* `f628a112-bfa0-520f-95e7-acda7183bec9`: check f340953b-2787-583d-acf3-f68832180dff, stdout[105:135]. Check diagnostic for build.

## Decisions and recommendations

### Correctness

The inclusive loop counts zero, negative even integers, and both endpoints correctly for valid inputs. Cases -3 3, 0 0, 2 2, and -1000 1000 match the required results.

Keep the inclusive loop and signed remainder check. Exercise it at both -1000 and 1000 after tightening input validation.

Evidence: `557f4ef3-b546-5eb1-a7a8-93c614be882a`, `a0ed4353-bfd2-57e9-a29e-bf44b0198dd1`

### Build

The CMake configuration succeeds and the build completes the count_even executable.

Preserve the target name while replacing the input parser; the identified defects do not require additional libraries or CMake dependencies.

Evidence: `5259f9d4-ea6d-5fec-b020-d532d81aac8c`, `f628a112-bfa0-520f-95e7-acda7183bec9`

### Output format

Invalid numeric input reaches the success output: abc 3 produces 2 plus a newline on stdout with empty stderr. This violates the explicit requirement that invalid input leave stdout empty and write an error to stderr.

Route every parse or bounds failure to a branch that writes a clear stderr message, returns 2, and never reaches cout. Check all three properties together for abc 3 and 2xyz 4.

Evidence: `1cc57c39-3d1a-5b53-b851-3639665ed85f`, `4c5cc13f-c03c-581e-8df4-cfb514454ac0`

### CLI validation

atoi silently converts abc to 0, 1.5 to 1, and 2x to 2. The program accepts these inputs with exit 0 and also omits the [-1000, 1000] bounds check. Argument-count and reversed-bound checks do not cover these failures.

Replace atoi with a checked conversion such as from_chars or a full-consumption stol parser. Reject malformed text, numeric suffixes, and endpoints outside the permitted bounds before entering the loop.

Evidence: `144b0e3a-e54c-54ac-80a0-64c2396c2749`, `b330d41e-e370-5718-b915-5d2c9841297f`


## Checks and limitations

* static: **UNAVAILABLE**. The archive contains C++ files; Python AST verification does not apply.
* tests: **FAILED**. exit code 1
* compile: **PASSED**. exit code 0
* tests: **FAILED**. exit code 1
* tests: **PASSED**. exit code 0
* memory: **SKIPPED**. The selected grading policy does not request a memory-safety check.
* compile: **PASSED**. exit code 0
