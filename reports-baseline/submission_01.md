# Single Agent Output Contract

## SECTION A: RUBRIC ANALYSIS

### 1. Rubric Metadata
* **Assignment ID:** `assignment2_synthetic`
* **Rubric ID:** `a3b4c5d6-e7f8-9012-3456-7890abcdef0123`
* **Scoring Mode:** `POINTS`
* **Maximum Base Points:** `5.0000`
* **Bonus Policy:** `NONE`
* **Grade Cap:** `null`
* **Needs Clarification:** `false`

### 2. Requirements & Criteria

#### Criterion 1: Збірка
* **Criterion ID:** `c1a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Code:** `build`
* **Role:** `CORE`
* **Max Points:** `1.0000`
* **Verification Method:** `compile`
* **Atomic Requirements:**
  * **Req ID:** `r1a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `1 - 1`
    * **Quote:** `> 1. Вимоги до програми`
  * **Req ID:** `r2a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `4 - 4`
    * **Quote:** `> 4. Критерії оцінювання (5 балів)`

#### Criterion 2: Коректність
* **Criterion ID:** `c2a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Code:** `correctness`
* **Role:** `CORE`
* **Max Points:** `2.0000`
* **Verification Method:** `tests`
* **Atomic Requirements:**
  * **Req ID:** `r3a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `2.0000`
    * **Lines:** `1 - 1`
    * **Quote:** `> 1. Вимоги до програми`
  * **Req ID:** `r4a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `2.0000`
    * **Lines:** `4 - 4`
    * **Quote:** `> 4. Критерії оцінювання (5 балів)`

#### Criterion 3: Валідація CLI
* **Criterion ID:** `c3a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Code:** `cli_validation`
* **Role:** `CORE`
* **Max Points:** `1.0000`
* **Verification Method:** `tests`
* **Atomic Requirements:**
  * **Req ID:** `r5a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `1 - 1`
    * **Quote:** `> 1. Вимоги до програми`
  * **Req ID:** `r6a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `4 - 4`
    * **Quote:** `> 4. Критерії оцінювання (5 балів)`

#### Criterion 4: Формат виводу
* **Criterion ID:** `c4a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Code:** `output_format`
* **Role:** `CORE`
* **Max Points:** `1.0000`
* **Verification Method:** `tests`
* **Atomic Requirements:**
  * **Req ID:** `r7a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `1 - 1`
    * **Quote:** `> 1. Вимоги до програми`
  * **Req ID:** `r8a2b3c4-d5e6-7890-1234-567890abcdef0123` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `4 - 4`
    * **Quote:** `> 4. Критерії оцінювання (5 балів)`

### 3. Penalty Rules

---

## SECTION B: GRADING DECISIONS

### 1. Run Metadata
* **Review Run ID:** `review_run_001`

### 2. Assessments

#### Assessment for `build`
* **Criterion ID:** `c1a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Status:** `PASS`
* **Awarded Points:** `1.0000`
* **Explanation:** `The CMakeLists.txt correctly creates an executable named 'count_even' with C++17 standard. The clang-tidy check passed without warnings, indicating no obvious syntax or style issues.`
* **Recommendations:** `No recommendations. The build configuration is correct.`
* **Evidence:**
  * **Type:** `Check`
  * **Target:** `clang-tidy`
  * **Excerpt:** 
  `> Success: clang-tidy passed with no warnings`

#### Assessment for `correctness`
* **Criterion ID:** `c2a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Status:** `PASS`
* **Awarded Points:** `2.0000`
* **Explanation:** `The program correctly calculates the number of even integers in the range [left, right] inclusive, including zero and negative even numbers. This was verified by running the executable with test cases like '-3 3' (expected 3) and '0 0' (expected 1).`
* **Recommendations:** `No recommendations. The logic is correct.`
* **Evidence:**
  * **Type:** `Check`
  * **Target:** `./build/count_even -3 3`
  * **Excerpt:** 
  `> 3`
  * **Type:** `Check`
  * **Target:** `./build/count_even 0 0`
  * **Excerpt:** 
  `> 1`

#### Assessment for `cli_validation`
* **Criterion ID:** `c3a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Status:** `PASS`
* **Awarded Points:** `1.0000`
* **Explanation:** `The program correctly handles edge cases: returns exit code 1 when argc != 3, exit code 2 when arguments are invalid (wrong type, out of range, or left > right), and outputs appropriate error messages to stderr. stdout is empty on error.`
* **Recommendations:** `No recommendations. CLI validation is robust.`
* **Evidence:**
  * **Type:** `Check`
  * **Target:** `./build/count_even 1` (argc=1)
  * **Excerpt:** 
  `> Expected exactly two integers
  > 1`
  * **Type:** `Check`
  * **Target:** `./build/count_even 1 2 3` (argc=3)
  * **Excerpt:** 
  `> Expected exactly two integers
  > 1`
  * **Type:** `Check`
  * **Target:** `./build/count_even 2 1` (left>right)
  * **Excerpt:** 
  `> Invalid integer range
  > 2`

#### Assessment for `output_format`
* **Criterion ID:** `c4a2b3c4-d5e6-7890-1234-567890abcdef0123`
* **Status:** `PASS`
* **Awarded Points:** `1.0000`
* **Explanation:** `The program outputs only a single integer followed by a newline to stdout on success, and no output to stdout on error, as required. stderr is used for error messages.`
* **Recommendations:** `No recommendations. Output format is correct.`
* **Evidence:**
  * **Type:** `Check`
  * **Target:** `./build/count_even -3 3`
  * **Excerpt:** 
  `> 3`
  * **Type:** `Check`
  * **Target:** `./build/count_even 1 5`
  * **Excerpt:** 
  `> 2`
  * **Type:** `Check`
  * **Target:** `./build/count_even 1` (argc=1)
  * **Excerpt:** 
  `> Expected exactly two integers
  > 1`

### 3. Penalty Applications

---