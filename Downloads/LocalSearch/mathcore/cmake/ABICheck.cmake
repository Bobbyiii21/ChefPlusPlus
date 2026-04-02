function(check_abi_compatibility target map_file)
    if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
        return()
    endif()

    if(NOT EXISTS "${map_file}")
        message(WARNING "ABI map file not found: ${map_file}")
        return()
    endif()

    message(STATUS "ABI version script enabled for ${target}: ${map_file}")
endfunction()
