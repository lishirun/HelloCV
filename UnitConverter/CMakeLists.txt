# ============================================================
#  UnitConverter —— 根目录构建文件
#  职责：定义工程、把 unitlib 子目录接进来、生成可执行程序
#
#  标准用法（源码外构建）：
#      mkdir build && cd build && cmake .. && make
#      ./unit_converter            # Windows: .\unit_converter.exe
# ============================================================
cmake_minimum_required(VERSION 3.16)

project(UnitConverter
        VERSION 2.0.0
        DESCRIPTION "三组单位换算的交互式小工具（CMake 练习，C++ 版）"
        LANGUAGES CXX)

# ---- C++ 标准：库用了 std::optional / lambda，需要 C++17 --------
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# 单配置生成器（Makefile/Ninja）没指定构建类型时，默认给 Debug
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Debug CACHE STRING "构建类型" FORCE)
endif()

# ---- 友好提示：提醒使用源码外构建 -----------------------------
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(WARNING
    "检测到源码内构建：生成的文件会混进源码目录。\n"
    "推荐做法：mkdir build && cd build && cmake .. && make")
endif()

# ---- 子目录：转换库 -------------------------------------------
add_subdirectory(unitlib)

# ---- 主程序 ---------------------------------------------------
add_executable(unit_converter src/main.cpp)

# 链接转换库。unitlib 把 include/ 声明为 PUBLIC，所以链接它之后
# main.cpp 里可以直接 #include "unitlib.h"，不用再写 include 路径。
target_link_libraries(unit_converter PRIVATE unitlib)

# 编译告警（按编译器选择对应写法）
if(MSVC)
  target_compile_options(unit_converter PRIVATE /W4)
else()
  target_compile_options(unit_converter PRIVATE -Wall -Wextra -pedantic)
endif()

# ---- 安装规则（可选，make install 用）--------------------------
install(TARGETS unit_converter RUNTIME DESTINATION bin)
