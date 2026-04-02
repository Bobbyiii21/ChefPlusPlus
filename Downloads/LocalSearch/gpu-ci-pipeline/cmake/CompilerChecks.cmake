if(DEFINED MATHCORE_COMPILER_CHECKS_INCLUDED)
    return()
endif()
set(MATHCORE_COMPILER_CHECKS_INCLUDED TRUE)

function(mathcore_check_compiler)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS "9.0")
            message(FATAL_ERROR
                "GCC 9.0 or newer required.\n"
                "Found: GCC ${CMAKE_CXX_COMPILER_VERSION}\n"
            )
        endif()
        message(STATUS "Compiler: GCC ${CMAKE_CXX_COMPILER_VERSION}")

    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
        if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS "10.0")
            message(FATAL_ERROR
                "Clang 10.0 or newer required.\n"
                "Found: Clang ${CMAKE_CXX_COMPILER_VERSION}\n"
            )
        endif()
        message(STATUS "Compiler: Clang ${CMAKE_CXX_COMPILER_VERSION}")

    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "MSVC")
        if(CMAKE_CXX_COMPILER_VERSION VERSION_LESS "19.20")
            message(FATAL_ERROR
                "MSVC 19.20 or newer required.\n"
                "Found: MSVC ${CMAKE_CXX_COMPILER_VERSION}\n"
            )
        endif()
        message(STATUS "Compiler: MSVC ${CMAKE_CXX_COMPILER_VERSION}")
    endif()
endfunction()
