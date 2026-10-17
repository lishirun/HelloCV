// ============================================================
//  unitlib.h —— 单位转换库的对外接口
//
//  设计要点：
//   * 库只负责「数据 + 算法」，完全不碰控制台输入输出；
//   * 一条换算规则被封装成 Rule{ 源单位, 目标单位, 换算函数 }，
//     菜单由这些规则自动生成，主程序里不再写死任何单位名字；
//   * 换算失败（例如温度低于绝对零度）用 std::optional 表示，
//     调用方必须显式处理，不会悄悄拿到一个假结果。
// ============================================================
#pragma once

#include <cstddef>
#include <functional>
#include <limits>
#include <optional>
#include <string>
#include <vector>

namespace unitlib {

/// 一个单位：显示用的符号 + 中文名 + 允许的最小值（如温度的下限是绝对零度）
struct Unit {
    std::string symbol;              // 例如 "°C"
    std::string name;                // 例如 "摄氏度"
    double min_value = std::numeric_limits<double>::lowest();
};

/// 一条换算规则：把 from 单位的数值换算成 to 单位
struct Rule {
    Unit from;
    Unit to;
    std::function<double(double)> convert;   // 纯函数：输入值 -> 输出值

    /// 菜单里显示的标题，例如 "摄氏度 -> 华氏度"
    std::string label() const { return from.name + " -> " + to.name; }

    /// 菜单里显示的括号注释，例如 "(°C -> °F)"
    std::string hint() const { return "(" + from.symbol + " -> " + to.symbol + ")"; }
};

/// 换算器：持有全部换算规则，并提供统一的换算入口
class Converter {
public:
    Converter();

    const std::vector<Rule> &rules() const { return rules_; }
    std::size_t size() const { return rules_.size(); }

    /// 按规则下标把 value 换算成目标单位。
    /// 下标越界或数值不合法（低于源单位的 min_value）时返回 std::nullopt。
    std::optional<double> convert(std::size_t index, double value) const;

private:
    std::vector<Rule> rules_;
};

}  // namespace unitlib
