```markdown
# Single Agent Output Contract

## SECTION A: RUBRIC ANALYSIS

### 1. Rubric Metadata
* **Assignment ID:** 99751a5e-530f-419d-8f4a-2425333e553f
* **Rubric ID:** 0b9332a4-50bf-47a0-9e3b-522c1b9d046f
* **Scoring Mode:** POINTS
* **Maximum Base Points:** 5.0000
* **Bonus Policy:** NONE
* **Grade Cap:** null
* **Needs Clarification:** false

### 2. Requirements & Criteria

#### Criterion 1: Збірка
* **Criterion ID:** 4d4389c9-592d-455a-8958-3327507b3619
* **Code:** build
* **Role:** CORE
* **Max Points:** 1.0000
* **Verification Method:** compile
* **Atomic Requirements:**
  * **Req ID:** 26a10e38-8a7e-47d7-b88b-9f161689b5d4 | **Kind:** mandatory | **Necessity:** mandatory
    * **Points:** 1.0000
    * **Lines:** 1 - 1
    * **Quote:** > # Мінілабораторна №1: Count Even Numbers (C++17)

#### Criterion 2: Коректність
* **Criterion ID:** d48d92a8-97a3-40b9-8122-4712388735d0
* **Code:** correctness
* **Role:** CORE
* **Max Points:** 2.0000
* **Verification Method:** tests
* **Atomic Requirements:**
  * **Req ID:** 242b5884-84bf-493a-905e-8e0416980531 | **Kind:** mandatory | **Necessity:** mandatory
    * **Points:** 2.0000
    * **Lines:** 1 - 1
    * **Quote:** > # Мінілабораторна №1: Count Even Numbers (C++17)

#### Criterion 3: Валідація CLI
* **Criterion ID:** 92b7c401-926d-4390-9041-31b2742785c7
* **Code:** cli_validation
* **Role:** CORE
* **Max Points:** 1.0000
* **Verification Method:** tests
* **Atomic Requirements:**
  * **Req ID:** 25654e67-333e-4e90-845a-3c54605323f4 | **Kind:** mandatory | **Necessity:** mandatory
    * **Points:** 1.0000
    * **Lines:** 1 - 1
    * **Quote:** > # Мінілабораторна №1: Count Even Numbers (C++17)

#### Criterion 4: Формат виводу
* **Criterion ID:** d2c58910-0243-4518-90e9-8463727305e5
* **Code:** output_format
* **Role:** CORE
* **Max Points:** 1.0000
* **Verification Method:** tests
* **Atomic Requirements:**
  * **Req ID:** 29d30917-8765-4469-88a2-113b69d0b14d | **Kind:** mandatory | **Necessity:** mandatory
    * **Points:** 1.0000
    * **Lines:** 1 - 1
    * **Quote:** > # Мінілабораторна №1: Count Even Numbers (C++17)

### 3. Penalty Rules

---

## SECTION B: GRADING DECISIONS

### 1. Run Metadata
* **Review Run ID:** 2187f7b6-4572-436c-8f8e-802076452080

### 2. Assessments

#### Assessment for build
* **Criterion ID:** 4d4389c9-592d-455a-8958-3327507b3619
* **Status:** PASS
* **Awarded Points:** 1.0000
* **Explanation:** clang-tidy analysis passed with no warnings, indicating correct C++17 syntax and style.
* **Recommendations:** None required.
* **Evidence:**
  * **Type:** Check
  * **Target:** clang-tidy
  * **Excerpt:**
  > Success: clang-tidy passed with no warnings

#### Assessment for correctness
* **Criterion ID:** d48d92a8-97a3-40b9-8122-4712388735d0
* **Status:** PARTIAL
* **Awarded Points:** 1.0000
* **Explanation:** The code correctly calculates even numbers in [left, right], but fails to handle negative ranges correctly. For example, `count_even -3 3` should return 3, but the code starts from 0 when left is negative, which is incorrect.
* **Recommendations:** Fix the loop to start from `left` even when it's negative.
* **Evidence:**
  * **Type:** Source
  * **Target:** main.cpp
  * **Excerpt:**
  > for (int value = (left < 0 ? 0 : left); value <= right; ++value) {
  >     if (value % 2 == 0) {
  >         ++count;
  >     }
  > }

#### Assessment for cli_validation
* **Criterion ID:** 92b7c401-926d-4390-9041-31b2742785c7
* **Status:** PASS
* **Awarded Points:** 1.0000
* **Explanation:** The code correctly handles incorrect number of arguments and invalid ranges with appropriate exit codes and error messages.
* **Recommendations:** None required.
* **Evidence:**
  * **Type:** Source
  * **Target:** main.cpp
  * **Excerpt:**
  > if (argc != 3) {
  >     std::cerr << "Expected exactly two integers\n";
  >     return 1;
  > }
  > if (!parse_number(argv[1], left) || !parse_number(argv[2], right) || left > right) {
  >     std::cerr << "Invalid integer range\n";
  >     return 2;
  > }

#### Assessment for output_format
* **Criterion ID:** d2c58910-0243-4518-90e9-8463727305e5
* **Status:** PASS
* **Awarded Points:** 1.0000
* **Explanation:** The code outputs only the count and a newline to stdout on success, and no output to stdout on error.
* **Recommendations:** None required.
* **Evidence:**
  * **Type:** Source
  * **Target:** main.cpp
  * **Excerpt:**
  > std::cout << count << '\n';

---

```