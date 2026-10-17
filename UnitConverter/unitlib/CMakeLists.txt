# ============================================================
#  unitlib —— 转换库的构建文件
#  生成静态库 unitlib，并把 include/ 目录作为公开头文件路径导出
# ============================================================

add_library(unitlib STATIC src/unitlib.cpp)

# PUBLIC：不仅 unitlib 自己要用这个头文件目录，
# 所有链接了 unitlib 的目标（例如根目录的 unit_converter）也能用，
# 于是 main.cpp 里 #include "unitlib.h" 不需要再手动写 include 路径。
target_include_directories(unitlib
        PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

# 公开声明本库需要 C++17：谁链接它，谁就会自动用 C++17 编译
target_compile_features(unitlib PUBLIC cxx_std_17)

# 库本身的编译告警
if(MSVC)
  target_compile_options(unitlib PRIVATE /W4)
else()
  target_compile_options(unitlib PRIVATE -Wall -Wextra -pedantic)
endif()

# ---- 安装规则（可选）------------------------------------------
install(TARGETS unitlib ARCHIVE DESTINATION lib)
install(FILES include/unitlib.h DESTINATION include)
