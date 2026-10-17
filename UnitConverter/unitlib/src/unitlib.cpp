// ============================================================
//  unitlib.cpp —— 单位转换的具体实现
//
//  这里只做两件事：定义换算因子与单位表、把规则装进 Converter。
//  换算函数用 lambda 表示，逻辑一目了然，也方便以后加新单位。
// ============================================================
#include "unitlib.h"

namespace unitlib {
namespace {

// ---- 换算因子（全部写成具名常量，避免魔法数字）----------------
constexpr double kFeetPerMeter       = 3.280839895013123;   // 1 m  = 3.2808… ft
constexpr double kMeterPerFeet       = 0.3048;              // 1 ft = 0.3048 m（精确定义）
constexpr double kPoundPerKilogram   = 2.2046226218487757;  // 1 kg = 2.2046… lb
constexpr double kKilogramPerPound   = 0.45359237;          // 1 lb = 0.45359237 kg（精确定义）

// ---- 物理下限：绝对零度，低于它的温度没有意义 -----------------
constexpr double kAbsoluteZeroCelsius    = -273.15;
constexpr double kAbsoluteZeroFahrenheit = -459.67;

const double kNoLimit = std::numeric_limits<double>::lowest();

// ---- 单位表 ---------------------------------------------------
const Unit kCelsius   {"°C", "摄氏度", kAbsoluteZeroCelsius};
const Unit kFahrenheit{"°F", "华氏度", kAbsoluteZeroFahrenheit};
const Unit kMeter     {"m",  "米"};
const Unit kFoot      {"ft", "英尺"};
const Unit kKilogram  {"kg", "千克"};
const Unit kPound     {"lb", "磅"};

}  // namespace

Converter::Converter() {
    rules_ = {
        // 温度：F = C * 9/5 + 32，C = (F - 32) * 5/9
        {kCelsius, kFahrenheit, [](double c) { return c * 9.0 / 5.0 + 32.0; }},
        {kFahrenheit, kCelsius, [](double f) { return (f - 32.0) * 5.0 / 9.0; }},

        // 长度
        {kMeter, kFoot, [](double m) { return m * kFeetPerMeter; }},
        {kFoot, kMeter, [](double ft) { return ft * kMeterPerFeet; }},

        // 质量
        {kKilogram, kPound, [](double kg) { return kg * kPoundPerKilogram; }},
        {kPound, kKilogram, [](double lb) { return lb * kKilogramPerPound; }},
    };
}

std::optional<double> Converter::convert(std::size_t index, double value) const {
    if (index >= rules_.size()) {
        return std::nullopt;                     // 下标越界
    }
    const Rule &rule = rules_[index];
    if (value < rule.from.min_value) {
        return std::nullopt;                     // 低于绝对零度的温度
    }
    return rule.convert(value);
}

}  // namespace unitlib
