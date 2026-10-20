#include <iostream>
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
