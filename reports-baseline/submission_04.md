# Single Agent Output Contract

## SECTION A: RUBRIC ANALYSIS

### 1. Rubric Metadata
* **Assignment ID:** `assignment2_synthetic`
* **Rubric ID:** `a7b2e3f4-5678-90ab-cdef-1234567890ab`
* **Scoring Mode:** `POINTS`
* **Maximum Base Points:** `5.0000`
* **Bonus Policy:** `NONE`
* **Grade Cap:** `null`
* **Needs Clarification:** `false`

### 2. Requirements & Criteria

#### Criterion 1: Збірка
* **Criterion ID:** `c1a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5o`
* **Code:** `build_success`
* **Role:** `CORE`
* **Max Points:** `1.0000`
* **Verification Method:** `compile`
* **Atomic Requirements:**
  * **Req ID:** `r1a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5p` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `1 - 1`
    * **Quote:** `> # Мінілабораторна №1: Count Even Numbers (C++17)`

#### Criterion 2: Коректність
* **Criterion ID:** `c2a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5q`
* **Code:** `correctness`
* **Role:** `CORE`
* **Max Points:** `2.0000`
* **Verification Method:** `tests`
* **Atomic Requirements:**
  * **Req ID:** `r2a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5r` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `2.0000`
    * **Lines:** `12 - 15`
    * **Quote:** `> int total = 0;
> for (int current = left; current <= right; ++current) {
>     if (current % 2 == 0) ++total;
> }`

#### Criterion 3: Валідація CLI
* **Criterion ID:** `c3a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5s`
* **Code:** `cli_validation`
* **Role:** `CORE`
* **Max Points:** `1.0000`
* **Verification Method:** `tests`
* **Atomic Requirements:**
  * **Req ID:** `r3a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5t` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `6 - 10`
    * **Quote:** `> if (argc != 3) {
>     std::cerr << "Expected exactly two integers\n";
>     return 1;
> }`

#### Criterion 4: Формат виводу
* **Criterion ID:** `c4a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5u`
* **Code:** `output_format`
* **Role:** `CORE`
* **Max Points:** `1.0000`
* **Verification Method:** `tests`
* **Atomic Requirements:**
  * **Req ID:** `r4a1b2c3-d4e5-6f7g-8h9i-0j1k2l3m4n5v` | **Kind:** `mandatory` | **Necessity:** `mandatory`
    * **Points:** `1.0000`
    * **Lines:** `16 - 17`
    * **Quote:** `> std::cout << total << '\n';
> return 0;`