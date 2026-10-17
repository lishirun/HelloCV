// ============================================================
//  main.cpp —— 单位转换器的交互界面
//
//  主程序只负责「界面」：
//    * 从 Converter 里取出规则，自动生成菜单；
//    * 读入用户选择与数值（带校验）；
//    * 调用库换算并打印结果。
//  单位名称、换算公式一律不在这里出现，将来加单位只改库。
// ============================================================
#include <iomanip>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>

#include "unitlib.h"

#if defined(_WIN32)
#include <windows.h>
#endif

namespace {

// ------------------------------------------------------------ 控制台工具
// Windows 控制台默认使用 GBK，切到 UTF-8 才能正常显示中文和 ° 符号。
void enableUtf8Console() {
#if defined(_WIN32)
    ::SetConsoleOutputCP(CP_UTF8);
    ::SetConsoleCP(CP_UTF8);
#endif
}

// 计算 UTF-8 字符串在终端里占多少列：中日韩字符算 2 列，其余算 1 列。
// printf 的 %-10s、std::setw 都按字节数补齐，中英文混排会错位，所以自己算。
std::size_t displayWidth(const std::string &text) {
    std::size_t width = 0;
    for (std::size_t i = 0; i < text.size();) {
        const unsigned char lead = static_cast<unsigned char>(text[i]);
        std::size_t length = 1;
        unsigned int code = lead;
        if (lead < 0x80) {
            length = 1;
        } else if ((lead & 0xE0) == 0xC0) {
            code = lead & 0x1F;
            length = 2;
        } else if ((lead & 0xF0) == 0xE0) {
            code = lead & 0x0F;
            length = 3;
        } else {
            code = lead & 0x07;
            length = 4;
        }
        for (std::size_t k = 1; k < length && i + k < text.size(); ++k) {
            code = (code << 6) | (static_cast<unsigned char>(text[i + k]) & 0x3F);
        }
        i += length;
        width += (code >= 0x2E80) ? 2 : 1;
    }
    return width;
}

// 输出文本并把光标补到第 columns 列，让后面的内容对齐
void printPadded(const std::string &text, std::size_t columns) {
    std::cout << text;
    for (std::size_t i = displayWidth(text); i < columns; ++i) {
        std::cout << ' ';
    }
}

// ------------------------------------------------------------ 输入解析
// 判断从第 used 个字符开始是否只剩空白（用来拒绝 "12abc" 这类输入）
bool onlyBlanksLeft(const std::string &line, std::size_t used) {
    for (std::size_t i = used; i < line.size(); ++i) {
        const char c = line[i];
        if (c != ' ' && c != '\t' && c != '\r' && c != '\n') {
            return false;
        }
    }
    return true;
}

// 读一行并解析为整数。用户直接关闭输入（Ctrl+D / Ctrl+Z）时返回 std::nullopt。
std::optional<int> readInt(const std::string &prompt) {
    for (;;) {
        std::cout << prompt;
        std::string line;
        if (!std::getline(std::cin, line)) {
            return std::nullopt;                 // 输入结束
        }
        try {
            std::size_t used = 0;
            const int value = std::stoi(line, &used);
            if (onlyBlanksLeft(line, used)) {
                return value;
            }
        } catch (const std::exception &) {
            // 解析失败，落到下面统一提示
        }
        std::cout << "！请输入一个数字。\n";
    }
}

// 同上，读一个浮点数
std::optional<double> readDouble(const std::string &prompt) {
    for (;;) {
        std::cout << prompt;
        std::string line;
        if (!std::getline(std::cin, line)) {
            return std::nullopt;
        }
        try {
            std::size_t used = 0;
            const double value = std::stod(line, &used);
            if (onlyBlanksLeft(line, used)) {
                return value;
            }
        } catch (const std::exception &) {
        }
        std::cout << "！请输入一个数字。\n";
    }
}

// ------------------------------------------------------------ 菜单
// 菜单内容完全由 Converter 里的规则决定，主程序不写死单位名
void printMenu(const unitlib::Converter &converter) {
    std::cout << "\n==============================================\n"
                 "             单位转换器  Unit Converter\n"
                 "==============================================\n";
    for (std::size_t i = 0; i < converter.size(); ++i) {
        const unitlib::Rule &rule = converter.rules()[i];
        std::cout << "  " << (i + 1) << ") ";
        printPadded(rule.label(), 17);
        std::cout << rule.hint() << '\n';
    }
    std::cout << "  0) 退出\n"
                 "==============================================\n";
}

}  // namespace

int main() {
    enableUtf8Console();

    const unitlib::Converter converter;
    printMenu(converter);

    const std::string choose_prompt =
        "请选择转换类型 [0-" + std::to_string(converter.size()) + "]: ";

    for (;;) {
        // ---- 1. 选择转换类型 -----------------------------------
        const std::optional<int> choice = readInt(choose_prompt);
        if (!choice) {
            std::cout << "\n输入结束，再见。\n";
            break;
        }
        if (*choice == 0) {
            std::cout << "再见。\n";
            break;
        }
        if (*choice < 1 || static_cast<std::size_t>(*choice) > converter.size()) {
            std::cout << "！没有这个选项，请输入 0-" << converter.size() << " 之间的数字。\n";
            continue;
        }

        const std::size_t index = static_cast<std::size_t>(*choice) - 1;
        const unitlib::Rule &rule = converter.rules()[index];

        // ---- 2. 读入待转换的数值 -------------------------------
        const std::optional<double> value =
            readDouble("请输入数值（" + rule.from.symbol + "）: ");
        if (!value) {
            std::cout << "\n输入结束，再见。\n";
            break;
        }

        // ---- 3. 调用库换算并输出 -------------------------------
        const std::optional<double> result = converter.convert(index, *value);
        if (!result) {
            std::cout << "！这个数值不在合理范围内（温度不能低于绝对零度）。\n";
            continue;
        }
        std::cout << ">>> " << std::fixed << std::setprecision(4)
                  << *value << ' ' << rule.from.symbol << " = "
                  << *result << ' ' << rule.to.symbol << '\n';
        std::cout << "（可继续选择，输入 0 退出）\n";
    }

    return 0;
}
