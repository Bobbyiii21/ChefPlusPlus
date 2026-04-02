cmake_minimum_required(VERSION 3.25)

add_library(core SHARED
    src/types.cpp
    src/memory.cpp
)

add_library(MathCore::core ALIAS core)

target_include_directories(core
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_compile_features(core PUBLIC cxx_std_17)

set_target_properties(core PROPERTIES
    VERSION 2.1.0
    SOVERSION 2
)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(core
        PUBLIC
            -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/core.map
    )
endif()

include(GNUInstallDirs)
install(TARGETS core EXPORT MathCoreTargets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
