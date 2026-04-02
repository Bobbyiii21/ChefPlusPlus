#!/bin/bash

set -e
set -u
set -o pipefail

BUILD_TYPE=${BUILD_TYPE:-Release}
OS_TARGET=${OS_TARGET:-ubuntu-22}
JOBS=${JOBS:-$(nproc)}

echo "Building for OS: ${OS_TARGET}"
echo "Build type: ${BUILD_TYPE}"
echo "Using ${JOBS} parallel jobs"

cmake -B build \
    -G Ninja \
    -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

cmake --build build --parallel ${JOBS}

echo "Build complete for ${OS_TARGET}"
