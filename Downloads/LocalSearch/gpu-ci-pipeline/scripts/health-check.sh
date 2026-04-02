#!/bin/bash

set -e
set -u
set -o pipefail

echo "Running nightly health check"

check_dependency() {
    local dep=$1
    local version_cmd=$2
    echo -n "Checking ${dep}... "
    if eval "${version_cmd}" > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAILED"
        exit 1
    fi
}

check_dependency "CMake"   "cmake --version"
check_dependency "Ninja"   "ninja --version"
check_dependency "g++"     "g++ --version"
check_dependency "Python"  "python3 --version"

echo "Running clean build..."
cmake -B build_health -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build_health --parallel $(nproc)

echo "Running all tests..."
ctest --test-dir build_health --output-on-failure

echo "Health check passed"
