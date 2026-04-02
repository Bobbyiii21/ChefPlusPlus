cmake_minimum_required(VERSION 3.25)

function(add_mathcore_example example_name source_file)
    add_executable(${example_name} ${source_file})
    target_link_libraries(${example_name} PRIVATE MathCore::analytics)
endfunction()

add_mathcore_example(basic_usage basic_usage.cpp)
