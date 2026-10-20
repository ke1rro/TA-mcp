# Lab review

Recommendation for human confirmation. This is not an official grade.

Run: `3f0fe5c5-b3a9-5dbd-b9fe-a3e07044c65b`
State: **COMPLETED**
Assignment SHA-256: `65ee46d89b8a97d303d6ade8c630f38e8e754df9fc41f64a9e5ce35f5e0844f2`
Submission SHA-256: `ee43502cb3c60ede6f6bc17e2a9b953ada224c0b2c345477f6d2781a831a833d`

Known earned points: 4
Base: 4; bonus: 0; penalties: 0
Possible score: 4 to 4
Recommended score: 4

| Criterion | Status | Points | Explanation |
| --- | --- | --- | --- |
| Output format | PASS | 1 / 1 | Success writes only an integer and a newline. Rejected input leaves stdout empty and writes stderr. Incorrect negative-range counts affect correctness but retain the required output format. |
| CLI validation | PASS | 1 / 1 | The parser checks full consumption, catches conversion errors, and enforces [-1000, 1000]. Incorrect argument counts return 1; malformed numbers, out-of-range endpoints, and reversed bounds return 2 with stderr diagnostics. |
| Build | PASS | 1 / 1 | CMake configures the C++17 count_even target and the build reaches [100%] Built target count_even. |
| Correctness | PARTIAL | 1 / 2 | The loop starts at zero when left is negative (main.cpp:32). For -3 3 it returns 2 instead of 3; for -6 -2 it returns 0 instead of 3. Non-negative intervals, zero, and the inclusive right endpoint work. Award 1 of 2 correctness points for the working cases. |

## Evidence

* `06511a02-7feb-54de-8f43-1ea134cb7eb8`: main.cpp:5-29. Inspected main.cpp:5-29 for cli validation.
* `36193cc9-e3aa-59f6-bf26-115a95503259`: check f7b6b418-0cbd-5a73-aad3-82bee39a2606, stdout[67:164]. Check diagnostic for output format.
* `4137586c-0fb9-535a-94d0-fa638de26083`: CMakeLists.txt:1-5. Inspected CMakeLists.txt:1-5 for build.
* `6339dfb6-0b23-5487-8a64-949c98767e14`: check dbeeb9dd-ecb1-5add-87bd-ce677c2b921e, stdout[170:274]. Check diagnostic for correctness.
* `7d3fe2af-f4b0-50a9-b05b-ba8bc8bf9373`: check 25ca3643-dffe-54b2-95b4-cbba1e84f0e5, stdout[105:135]. Check diagnostic for build.
* `b5096271-bc7b-5894-98f0-799bd08efae8`: main.cpp:27-38. Inspected main.cpp:27-38 for output format.
* `c44e5e44-241b-54e6-b8a6-117ff38f516c`: check 42ddf13d-1531-555b-bb47-c4023a8ffe36, stdout[67:184]. Check diagnostic for cli validation.
* `f801e1ab-127f-588e-b7e2-1dd37c8766c8`: main.cpp:31-36. Inspected main.cpp:31-36 for correctness.

## Decisions and recommendations

### Output format

Success writes only an integer and a newline. Rejected input leaves stdout empty and writes stderr. Incorrect negative-range counts affect correctness but retain the required output format.

Keep stdout machine-readable. Put any future progress or debugging messages in stderr rather than adding labels before the count.

Evidence: `36193cc9-e3aa-59f6-bf26-115a95503259`, `b5096271-bc7b-5894-98f0-799bd08efae8`

### CLI validation

The parser checks full consumption, catches conversion errors, and enforces [-1000, 1000]. Incorrect argument counts return 1; malformed numbers, out-of-range endpoints, and reversed bounds return 2 with stderr diagnostics.

Keep the full-consumption and range checks when changing the counting logic. Include malformed suffixes such as 2x in the parsing regression cases.

Evidence: `06511a02-7feb-54de-8f43-1ea134cb7eb8`, `c44e5e44-241b-54e6-b8a6-117ff38f516c`

### Build

CMake configures the C++17 count_even target and the build reaches [100%] Built target count_even.

Retain the CMake target and C++17 requirement while repairing the loop; no build-system change is needed for this defect.

Evidence: `4137586c-0fb9-535a-94d0-fa638de26083`, `7d3fe2af-f4b0-50a9-b05b-ba8bc8bf9373`

### Correctness

The loop starts at zero when left is negative (main.cpp:32). For -3 3 it returns 2 instead of 3; for -6 -2 it returns 0 instead of 3. Non-negative intervals, zero, and the inclusive right endpoint work. Award 1 of 2 correctness points for the working cases.

Initialize value directly from left. Add cases [-6, -2], [-3, 3], and [-2, -2] so negative-only and mixed intervals exercise the corrected starting point.

Evidence: `6339dfb6-0b23-5487-8a64-949c98767e14`, `f801e1ab-127f-588e-b7e2-1dd37c8766c8`


## Checks and limitations

* memory: **SKIPPED**. The selected grading policy does not request a memory-safety check.
* compile: **PASSED**. exit code 0
* tests: **PASSED**. exit code 0
* static: **UNAVAILABLE**. The archive contains C++ files; Python AST verification does not apply.
* compile: **PASSED**. exit code 0
* tests: **FAILED**. exit code 1
* tests: **PASSED**. exit code 0
