# Lab review

Recommendation for human confirmation. This is not an official grade.

Run: `5e9265a4-df9c-5ab1-8f55-40ee93d6dcb8`
State: **NEEDS_REVIEW**
Assignment SHA-256: `65ee46d89b8a97d303d6ade8c630f38e8e754df9fc41f64a9e5ce35f5e0844f2`
Submission SHA-256: `7352e17a6efd44ed056b5ca084511437560dbe342bb53df7b92620abfe38d117`

Known earned points: 0
Base: 0; bonus: 0; penalties: 0
Possible score: 0 to 4
Recommended score: pending verification

| Criterion | Status | Points | Explanation |
| --- | --- | --- | --- |
| Correctness | NOT_VERIFIABLE | ? / 2 | The source loop includes both endpoints and tests value % 2 == 0, but compilation produces no executable. Correctness cannot be verified until the build is repaired. |
| Output format | NOT_VERIFIABLE | ? / 1 | The output expression contains the syntax error that blocks compilation. No student stdout or stderr is available, so output format remains unverified. |
| CLI validation | NOT_VERIFIABLE | ? / 1 | The source contains argument-count, full-consumption, and range checks. The failed build prevents exercising exit codes or diagnostics, so CLI validation remains unverified. |
| Build | FAIL | 0 / 1 | main.cpp:37 lacks a semicolon after std::cout &lt;&lt; count &lt;&lt; &#x27;\n&#x27;. Configuration succeeds, but compilation reports expected &#x27;;&#x27; after expression and the build exits 2. Build receives 0 of 1 point. |

## Evidence

* `0c0489bc-c32e-50a8-b55c-37cbe48f1d30`: main.cpp:5-29. Inspected main.cpp:5-29 for cli validation.
* `bab3466f-2aa6-5df4-8cfc-b390d87e845d`: check 35f5b86c-00ce-5607-82bd-b691bd05f0dc, stderr[0:65]. Check diagnostic for build.
* `c1b549b6-56be-575f-a8a2-d2b30c2644d2`: main.cpp:36-39. Inspected main.cpp:36-39 for build.
* `c506cc6d-bae7-5fd6-9107-e17722159b35`: main.cpp:31-36. Inspected main.cpp:31-36 for correctness.
* `f1a128b7-282d-5107-9c8c-0f5514b76ca5`: main.cpp:36-39. Inspected main.cpp:36-39 for output format.

## Decisions and recommendations

### Correctness

The source loop includes both endpoints and tests value % 2 == 0, but compilation produces no executable. Correctness cannot be verified until the build is repaired.

Unverified: No runtime observation is available in this failed-build demo. Compilation must be repaired before this criterion can be verified.

After compilation is repaired, check [-3, 3], [0, 0], and [2, 2] to confirm signed values, zero, and the inclusive endpoint using actual executions.

Evidence: `c506cc6d-bae7-5fd6-9107-e17722159b35`

### Output format

The output expression contains the syntax error that blocks compilation. No student stdout or stderr is available, so output format remains unverified.

Unverified: No runtime observation is available in this failed-build demo. Compilation must be repaired before this criterion can be verified.

Once the binary exists, capture stdout and stderr separately. Confirm that valid output ends in one newline and every rejected invocation leaves stdout empty.

Evidence: `f1a128b7-282d-5107-9c8c-0f5514b76ca5`

### CLI validation

The source contains argument-count, full-consumption, and range checks. The failed build prevents exercising exit codes or diagnostics, so CLI validation remains unverified.

Unverified: No runtime observation is available in this failed-build demo. Compilation must be repaired before this criterion can be verified.

Run the repaired executable with a missing argument, abc, 1001, and reversed bounds; confirm exit codes 1 and 2 and the diagnostic stream.

Evidence: `0c0489bc-c32e-50a8-b55c-37cbe48f1d30`

### Build

main.cpp:37 lacks a semicolon after std::cout &lt;&lt; count &lt;&lt; &#x27;\n&#x27;. Configuration succeeds, but compilation reports expected &#x27;;&#x27; after expression and the build exits 2. Build receives 0 of 1 point.

Terminate std::cout &lt;&lt; count &lt;&lt; &#x27;\n&#x27; with a semicolon, then configure and build the existing count_even target again. Verify the compiler result before interpreting any runtime criterion.

Evidence: `bab3466f-2aa6-5df4-8cfc-b390d87e845d`, `c1b549b6-56be-575f-a8a2-d2b30c2644d2`


## Checks and limitations

* memory: **SKIPPED**. The selected grading policy does not request a memory-safety check.
* compile: **FAILED**. exit code 2
* static: **UNAVAILABLE**. The archive contains C++ files; Python AST verification does not apply.
* compile: **PASSED**. exit code 0
* tests: **SKIPPED**. Runtime checks unavailable after the failed-build scenario.
* tests: **SKIPPED**. Runtime checks unavailable after the failed-build scenario.
* tests: **SKIPPED**. Runtime checks unavailable after the failed-build scenario.
