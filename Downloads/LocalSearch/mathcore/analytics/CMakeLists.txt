cmake_minimum_required(VERSION 3.25)

add_library(analytics SHARED
    src/stats.cpp
    src/aggregate.cpp
)

add_library(MathCore::analytics ALIAS analytics)

target_include_directories(analytics
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(analytics PUBLIC MathCore::algorithms)

set_target_properties(analytics PROPERTIES
    VERSION 2.1.0
    SOVERSION 2
)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(analytics
        PUBLIC
            -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/analytics.map
    )
endif()

include(GNUInstallDirs)
install(TARGETS analytics EXPORT MathCoreTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
