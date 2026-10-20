# Grading Decisions Report

## 1. Run Metadata
* **Review Run ID:** review_001
* **Submission ID:** assignment2_synthetic/submission_01
* **Rubric ID:** RUB-001

## 2. Criterion Assessments

### Assessment: CRIT-01
* **Criterion ID:** CRIT-01
* **Status:** PASS
* **Awarded Points:** "1.0000"
* **Explanation:** The submission includes `main.cpp` and `CMakeLists.txt`, compiles with C++17 standard as required, and uses standard CMake build process.
* **Not Verifiable Reason:** null
* **Recommendations:** The code is well-structured and meets all structural requirements.

**Evidence:**
* **Type:** Source
* **File/Tool:** main.cpp
* **Excerpt/Diagnostic:**
> #include <iostream>
#include <string>
#include <exception>

bool parse_number(const char* text, int& value) {
    try {
        std::size_t parsed_chars = 0;
        std::string input(text);
        long candidate = std::stol(input, &parsed_chars, 10);
        if (parsed_chars != input.size() || candidate < -1000 || candidate > 1000) {
            return false;
        }
        value = static_cast<int>(candidate);
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Expected exactly two integers\n";
        return 1;
    }
    int left = 0;
    int right = 0;
    if (!parse_number(argv[1], left) || !parse_number(argv[2], right) || left > right) {
        std::cerr << "Invalid integer range\n";
        return 2;
    }
    int count = 0;
    for (int value = left; value <= right; ++value) {
        if (value % 2 == 0) {
            ++count;
        }
    }
    std::cout << count << '\n';
    return 0;
}

### Assessment: CRIT-02
* **Criterion ID:** CRIT-02
* **Status:** PASS
* **Awarded Points:** "2.0000"
* **Explanation:** The program correctly counts even integers in the range [left, right] inclusive, including zero and negative even numbers, and outputs exactly one integer followed by a newline to stdout.
* **Not Verifiable Reason:** null
* **Recommendations:** The logic for counting even numbers is correct and efficient.

**Evidence:**
* **Type:** Source
* **File/Tool:** main.cpp
* **Excerpt/Diagnostic:**
> int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Expected exactly two integers\n";
        return 1;
    }
    int left = 0;
    int right = 0;
    if (!parse_number(argv[1], left) || !parse_number(argv[2], right) || left > right) {
        std::cerr << "Invalid integer range\n";
        return 2;
    }
    int count = 0;
    for (int value = left; value <= right; ++value) {
        if (value % 2 == 0) {
            ++count;
        }
    }
    std::cout << count << '\n';
    return 0;
}

### Assessment: CRIT-03
* **Criterion ID:** CRIT-03
* **Status:** PASS
* **Awarded Points:** "1.0000"
* **Explanation:** The program exits with code 0 on success, code 1 for incorrect argument count, code 2 for invalid arguments, and stdout is empty on error.
* **Not Verifiable Reason:** null
* **Recommendations:** The CLI validation logic is robust and meets all requirements.

**Evidence:**
* **Type:** Source
* **File/Tool:** main.cpp
* **Excerpt/Diagnostic:**
> int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Expected exactly two integers\n";
        return 1;
    }
    int left = 0;
    int right = 0;
    if (!parse_number(argv[1], left) || !parse_number(argv[2], right) || left > right) {
        std::cerr << "Invalid integer range\n";
        return 2;
    }
    int count = 0;
    for (int value = left; value <= right; ++value) {
        if (value % 2 == 0) {
            ++count;
        }
    }
    std::cout << count << '\n';
    return 0;
}

### Assessment: CRIT-04
* **Criterion ID:** CRIT-04
* **Status:** PASS
* **Awarded Points:** "1.0000"
* **Explanation:** On success, the program outputs only one integer followed by a newline to stdout, and on error, stdout is empty and stderr contains an understandable message.
* **Not Verifiable Reason:** null
* **Recommendations:** The output format is correct and meets all requirements.

**Evidence:**
* **Type:** Source
* **File/Tool:** main.cpp
* **Excerpt/Diagnostic:**
> int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Expected exactly two integers\n";
        return 1;
    }
    int left = 0;
    int right = 0;
    if (!parse_number(argv[1], left) || !parse_number(argv[2], right) || left > right) {
        std::cerr << "Invalid integer range\n";
        return 2;
    }
    int count = 0;
    for (int value = left; value <= right; ++value) {
        if (value % 2 == 0) {
            ++count;
        }
    }
    std::cout << count << '\n';
    return 0;
}

## 3. Penalty Applications

