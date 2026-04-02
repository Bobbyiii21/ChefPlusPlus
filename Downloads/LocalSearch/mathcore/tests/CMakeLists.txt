cmake_minimum_required(VERSION 3.25)

enable_testing()

function(add_mathcore_test test_name source_file)
    add_executable(${test_name} ${source_file})
    target_link_libraries(${test_name} PRIVATE MathCore::analytics)
    add_test(NAME ${test_name} COMMAND ${test_name})
    set_tests_properties(${test_name} PROPERTIES
        LABELS "unit"
        TIMEOUT 60
    )
endfunction()

add_mathcore_test(test_matrix        core/test_matrix.cpp)
add_mathcore_test(test_sort          algorithms/test_sort.cpp)
add_mathcore_test(test_reduce        algorithms/test_reduce.cpp)
add_mathcore_test(test_stats         analytics/test_stats.cpp)
add_mathcore_test(test_abi           core/test_abi.cpp)
