#!/bin/bash

set -e
set -u
set -o pipefail

TEST_LABEL=${TEST_LABEL:-unit}
TEST_DIR=${TEST_DIR:-build}

echo "Running ${TEST_LABEL} tests"

ctest \
    --test-dir ${TEST_DIR} \
    -L ${TEST_LABEL} \
    --output-on-failure \
    --parallel $(nproc)

echo "All ${TEST_LABEL} tests passed"
