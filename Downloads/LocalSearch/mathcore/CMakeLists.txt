cmake_minimum_required(VERSION 3.25)

project(MathCore VERSION 2.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(BUILD_SHARED_LIBS ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

include(VersionInfo)
include(ValidateCompiler)

add_subdirectory(core)
add_subdirectory(algorithms)
add_subdirectory(analytics)
add_subdirectory(tests)
add_subdirectory(examples)
