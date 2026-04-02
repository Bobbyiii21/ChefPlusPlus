cmake_minimum_required(VERSION 3.25)

project(GPUCIPipeline VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

include(CompilerChecks)
include(DAGScheduler)

mathcore_check_compiler()

dag_add_job(compile-ubuntu-20)
dag_add_job(compile-ubuntu-22)
dag_add_job(compile-windows)
dag_add_job(compile-centos)
dag_add_job(test-ubuntu-20   DEPS compile-ubuntu-20)
dag_add_job(test-ubuntu-22   DEPS compile-ubuntu-22)
dag_add_job(test-windows     DEPS compile-windows)
dag_add_job(test-centos      DEPS compile-centos)
dag_add_job(integration-tests DEPS test-ubuntu-20 test-ubuntu-22 test-windows test-centos)
dag_add_job(package          DEPS integration-tests)

dag_compute_levels()
dag_print_schedule()
