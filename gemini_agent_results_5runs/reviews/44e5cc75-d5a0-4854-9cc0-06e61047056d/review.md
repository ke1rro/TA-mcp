# Lab review

Recommendation for human confirmation. This is not an official grade.

Run: `44e5cc75-d5a0-4854-9cc0-06e61047056d`
State: **COMPLETED**
Assignment SHA-256: `65ee46d89b8a97d303d6ade8c630f38e8e754df9fc41f64a9e5ce35f5e0844f2`
Submission SHA-256: `42e249b29ed7c46213432c87d2e0cc065c4a253056aa15ebea1bc3e04cf6433e`

Known earned points: 3
Base: 3; bonus: 0; penalties: 0
Possible score: 3 to 3
Recommended score: 3

| Criterion | Status | Points | Explanation |
| --- | --- | --- | --- |
| Correctness | PASS | 2 / 2 | The program correctly counts even integers across negative, zero, and positive bounds on all valid input cases. |
| CLI validation | FAIL | 0 / 1 | Input validation is incomplete. While argument count and range ordering (left &gt; right) are checked, non-integer inputs and values outside [-1000, 1000] are parsed with std::atoi without error handling or exit code 2. |
| Output format | FAIL | 0 / 1 | The requirement specifies that on error, stdout must be empty and errors reported to stderr. Because invalid inputs (e.g. non-numeric strings or out-of-range numbers) are treated as valid numbers, erroneous inputs print results to stdout with exit code 0. |
| Build | PASS | 1 / 1 | CMake build configured and built target count_even without errors. |

## Evidence

* `1ef1d4ec-d2ec-4847-8b06-4e58bca88939`: check 7632b2f9-33b1-40e4-9cf7-adc431d72ea2, stdout[1461:1564]. Output format check failed because error input produced output to stdout instead of empty stdout with stderr error.
* `4487b3e0-6311-460f-9040-cfc94f5359a3`: main.cpp:9-10. Arguments parsed via std::atoi without validation of bounds or non-numeric tokens.
* `6a2fa5aa-82d6-4fe4-a8fe-3bc4daea66da`: check 75421787-ad0a-4277-a899-8e06690cc6a8, stdout[105:136]. CMake target count_even built successfully.
* `b744b80b-aa85-484a-95b7-7c7d42cf38f9`: check 8c627970-d27d-4e83-8e23-ee91e63eb134, stdout[437:537]. CLI validation failed on non-integer input &#x27;abc&#x27;.
* `c5d315cb-b565-4d2b-b6b6-398e09fce7eb`: check 9f73eabb-11d0-4b45-bb13-a5c1526a5c26, stdout[688:803]. Correctness check passed for the full interval [-1000, 1000].

## Decisions and recommendations

### Correctness

The program correctly counts even integers across negative, zero, and positive bounds on all valid input cases.

Evidence: `c5d315cb-b565-4d2b-b6b6-398e09fce7eb`

### CLI validation

Input validation is incomplete. While argument count and range ordering (left &gt; right) are checked, non-integer inputs and values outside [-1000, 1000] are parsed with std::atoi without error handling or exit code 2.

Use std::strtol or std::from_chars to thoroughly validate that arguments are valid integers within the [-1000, 1000] bounds, and exit with code 2 and a message on stderr when validation fails.

Evidence: `4487b3e0-6311-460f-9040-cfc94f5359a3`, `b744b80b-aa85-484a-95b7-7c7d42cf38f9`

### Output format

The requirement specifies that on error, stdout must be empty and errors reported to stderr. Because invalid inputs (e.g. non-numeric strings or out-of-range numbers) are treated as valid numbers, erroneous inputs print results to stdout with exit code 0.

Ensure all error conditions prevent any output to stdout and emit appropriate error messages to stderr.

Evidence: `1ef1d4ec-d2ec-4847-8b06-4e58bca88939`

### Build

CMake build configured and built target count_even without errors.

Evidence: `6a2fa5aa-82d6-4fe4-a8fe-3bc4daea66da`


## Checks and limitations

* compile: **PASSED**. exit code 0
* compile: **PASSED**. exit code 0
* tests: **FAILED**. exit code 1
* tests: **FAILED**. exit code 1
* tests: **PASSED**. exit code 0
* memory: **SKIPPED**. Disabled by grading policy
* static: **UNAVAILABLE**. No UTF-8 Python source is available for syntax analysis
