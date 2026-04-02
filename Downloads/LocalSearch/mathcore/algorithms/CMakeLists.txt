cmake_minimum_required(VERSION 3.25)

add_library(algorithms SHARED
    src/sort.cpp
    src/reduce.cpp
)

add_library(MathCore::algorithms ALIAS algorithms)

target_include_directories(algorithms
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(algorithms PUBLIC MathCore::core)

set_target_properties(algorithms PROPERTIES
    VERSION 2.1.0
    SOVERSION 2
)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(algorithms
        PUBLIC
            -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/algorithms.map
    )
endif()

include(GNUInstallDirs)
install(TARGETS algorithms EXPORT MathCoreTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
