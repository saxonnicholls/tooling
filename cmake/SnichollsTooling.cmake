#
#  SnichollsTooling.cmake
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The checks a repository's build runs, parameterised by its tooling.conf (README "tooling.conf"):
#
#      include(third_party/tooling/cmake/SnichollsTooling.cmake)
#
#      # every public header compiles on its own, twice, behind its named guard
#      snicholls_header_check(my_lib_header_check LINK my::lib)
#
#      # check_mirror.py, check_version.py, check_interfaces.py and single_include.py --check as CTests (label boundary)
#      snicholls_tooling_add_checks()
#
#      # every single_include/<name>.hpp compiles on its own, with nothing but the standard library
#      snicholls_single_include_check(my_lib_single_include COMPILE_OPTIONS -Werror)
#
#  snicholls_header_check(<target>
#      [LINK <library>...]            what the headers need: normally the library's own target
#      [COMPILE_OPTIONS <option>...]  e.g. the warnings as errors; or call your own options function on <target>
#      [EXCLUDE <regex>...]           headers compiled elsewhere, e.g. an optional backend not configured
#      [HEADERS <header>...]          only these, as included (snicholls/core/x.hpp); default every header
#      [CXX_STANDARD <n>]             e.g. 17 for a header kept C++17-clean
#      [CONFIG <tooling.conf>])       default ${CMAKE_CURRENT_SOURCE_DIR}/tooling.conf
#
#  defines an OBJECT library <target> with one translation unit per header under include_root. Each includes the
#  header, checks that guard_prefix + <path under include_root> (snicholls_core_meta_concepts_hpp) is defined, and
#  includes it again. Without guard_prefix the guard is not checked.
#
#  snicholls_single_include_check(<target> [COMPILE_OPTIONS <option>...] [CXX_STANDARD <n>] [CONFIG <tooling.conf>])
#
#  defines an OBJECT library <target> with one translation unit per single_include.<name> line, which includes
#  <single_include_dir>/<name>.hpp with no other include directory. single_include.py --check proves the file fresh;
#  this proves it self-contained.
#
#  snicholls_tooling_add_checks([MIRROR] [VERSION] [INTERFACES] [SINGLE_INCLUDE] [LABELS <label>...]
#                               [CONFIG <tooling.conf>])
#  adds the named checks (default all four) as CTests check.mirror, check.version, check.interfaces and
#  check.single_include.
#

include_guard(GLOBAL)
set(SNICHOLLS_TOOLING_DIR "${CMAKE_CURRENT_LIST_DIR}/.." CACHE INTERNAL "snicholls-tooling's checkout")

# Reads <config> into <prefix>_<key> in the caller's scope (the format: scripts/tooling_conf.py)
function(snicholls_tooling_read_config config prefix)
    if(NOT EXISTS "${config}")
        message(FATAL_ERROR "snicholls-tooling: no ${config}: every repository that uses tooling has one")
    endif()
    # Read whole and split by hand: a CMake list would split a value at ';' and join lines across an unclosed '['
    file(READ "${config}" _text)
    string(REPLACE ";" "@semicolon@" _text "${_text}")
    string(REPLACE "[" "@open@" _text "${_text}")
    string(REPLACE "]" "@close@" _text "${_text}")
    string(REPLACE "\r" "" _text "${_text}")
    string(REPLACE "\n" ";" _lines "${_text}")
    foreach(_line IN LISTS _lines)
        string(REGEX REPLACE "(^|[ \t])#.*$" "" _line "${_line}")
        string(REPLACE "@semicolon@" ";" _line "${_line}")
        string(REPLACE "@open@" "[" _line "${_line}")
        string(REPLACE "@close@" "]" _line "${_line}")
        if(_line MATCHES "^[ \t]*$")
            continue()
        endif()
        if(NOT _line MATCHES "^[ \t]*([A-Za-z0-9_.+-]+)[ \t]*=[ \t]*(.*)$")
            message(FATAL_ERROR "snicholls-tooling: ${config}: expected 'key = value', got: ${_line}")
        endif()
        set(_key "${CMAKE_MATCH_1}")
        string(STRIP "${CMAKE_MATCH_2}" _value)
        set(${prefix}_${_key} "${_value}" PARENT_SCOPE)
    endforeach()
endfunction()

function(snicholls_header_check target)
    cmake_parse_arguments(PARSE_ARGV 1 arg "" "CXX_STANDARD;CONFIG" "LINK;COMPILE_OPTIONS;EXCLUDE;HEADERS")
    if(NOT arg_CONFIG)
        set(arg_CONFIG "${CMAKE_CURRENT_SOURCE_DIR}/tooling.conf")
    endif()
    snicholls_tooling_read_config("${arg_CONFIG}" _conf)
    if(NOT _conf_include_root)
        message(FATAL_ERROR "snicholls_header_check: ${arg_CONFIG} sets no include_root")
    endif()
    if(NOT DEFINED _conf_include_dir)
        set(_conf_include_dir include)
    endif()
    get_filename_component(_repo "${arg_CONFIG}" DIRECTORY)
    set(_include "${_repo}/${_conf_include_dir}")
    file(RELATIVE_PATH _root_in_include "${_include}" "${_repo}/${_conf_include_root}")
    if(_root_in_include MATCHES "^\\.\\.")
        message(FATAL_ERROR "snicholls_header_check: include_root ${_conf_include_root} is not under ${_conf_include_dir}")
    endif()

    if(arg_HEADERS)
        set(_headers ${arg_HEADERS})
    else()
        file(GLOB_RECURSE _headers RELATIVE "${_include}" CONFIGURE_DEPENDS "${_repo}/${_conf_include_root}/*.hpp")
        list(SORT _headers)
    endif()

    set(_sources)
    foreach(_header IN LISTS _headers)
        set(_skip OFF)
        foreach(_regex IN LISTS arg_EXCLUDE)
            if(_header MATCHES "${_regex}")
                set(_skip ON)
            endif()
        endforeach()
        if(_skip)
            continue()
        endif()
        set(HEADER "${_header}")
        set(GUARD_CHECK "")
        if(_conf_guard_prefix)
            file(RELATIVE_PATH _in_root "${_repo}/${_conf_include_root}" "${_include}/${_header}")
            string(MAKE_C_IDENTIFIER "${_in_root}" _guard)
            set(_guard "${_conf_guard_prefix}${_guard}")
            set(GUARD_CHECK "#ifndef ${_guard}\n#error \"${_header} is not guarded by ${_guard}: a named guard, never #pragma once\"\n#endif")
        endif()
        string(MAKE_C_IDENTIFIER "${_header}" _id)
        configure_file("${SNICHOLLS_TOOLING_DIR}/cmake/header_check.cpp.in"
                       "${CMAKE_CURRENT_BINARY_DIR}/${target}/${_id}.cpp" @ONLY)
        list(APPEND _sources "${CMAKE_CURRENT_BINARY_DIR}/${target}/${_id}.cpp")
    endforeach()
    if(NOT _sources)
        message(FATAL_ERROR "snicholls_header_check: no headers under ${_conf_include_root}")
    endif()

    add_library(${target} OBJECT ${_sources})
    target_include_directories(${target} PRIVATE "${_include}")
    if(arg_LINK)
        target_link_libraries(${target} PRIVATE ${arg_LINK})
    endif()
    if(arg_COMPILE_OPTIONS)
        target_compile_options(${target} PRIVATE ${arg_COMPILE_OPTIONS})
    endif()
    if(arg_CXX_STANDARD)
        set_target_properties(${target} PROPERTIES
            CXX_STANDARD ${arg_CXX_STANDARD} CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)
    endif()
endfunction()

function(snicholls_tooling_add_checks)
    cmake_parse_arguments(PARSE_ARGV 0 arg "MIRROR;VERSION;INTERFACES;SINGLE_INCLUDE" "CONFIG" "LABELS")
    if(NOT arg_CONFIG)
        set(arg_CONFIG "${CMAKE_CURRENT_SOURCE_DIR}/tooling.conf")
    endif()
    if(NOT arg_LABELS)
        set(arg_LABELS boundary)
    endif()
    set(_checks)
    foreach(_check IN ITEMS MIRROR VERSION INTERFACES SINGLE_INCLUDE)
        if(arg_${_check})
            list(APPEND _checks ${_check})
        endif()
    endforeach()
    if(NOT _checks)
        set(_checks MIRROR VERSION INTERFACES SINGLE_INCLUDE)
    endif()
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
    get_filename_component(_repo "${arg_CONFIG}" DIRECTORY)
    foreach(_check IN LISTS _checks)
        string(TOLOWER "${_check}" _name)
        if(_name STREQUAL "single_include")
            set(_script single_include.py)
            set(_extra --check)
        else()
            set(_script check_${_name}.py)
            set(_extra)
        endif()
        add_test(NAME check.${_name}
                 COMMAND Python3::Interpreter "${SNICHOLLS_TOOLING_DIR}/scripts/${_script}"
                         --root "${_repo}" --config "${arg_CONFIG}" ${_extra})
        set_tests_properties(check.${_name} PROPERTIES LABELS "${arg_LABELS}")
    endforeach()
endfunction()

function(snicholls_single_include_check target)
    cmake_parse_arguments(PARSE_ARGV 1 arg "" "CXX_STANDARD;CONFIG" "COMPILE_OPTIONS")
    if(NOT arg_CONFIG)
        set(arg_CONFIG "${CMAKE_CURRENT_SOURCE_DIR}/tooling.conf")
    endif()
    file(STRINGS "${arg_CONFIG}" _lines REGEX "^[ \t]*single_include\\.[A-Za-z0-9_.+-]+[ \t]*=")
    if(NOT _lines)
        message(FATAL_ERROR "snicholls_single_include_check: ${arg_CONFIG} has no single_include.<name> line")
    endif()
    snicholls_tooling_read_config("${arg_CONFIG}" _conf)
    if(NOT DEFINED _conf_single_include_dir)
        set(_conf_single_include_dir single_include)
    endif()
    get_filename_component(_repo "${arg_CONFIG}" DIRECTORY)
    set(_sources)
    foreach(_line IN LISTS _lines)
        string(REGEX REPLACE "^[ \t]*single_include\\.([A-Za-z0-9_.+-]+).*$" "\\1" _name "${_line}")
        set(_cpp "${CMAKE_CURRENT_BINARY_DIR}/${target}/${_name}.cpp")
        file(CONFIGURE OUTPUT "${_cpp}" CONTENT "#include \"${_name}.hpp\"\n" @ONLY)
        list(APPEND _sources "${_cpp}")
    endforeach()
    add_library(${target} OBJECT ${_sources})
    target_include_directories(${target} PRIVATE "${_repo}/${_conf_single_include_dir}")
    if(arg_COMPILE_OPTIONS)
        target_compile_options(${target} PRIVATE ${arg_COMPILE_OPTIONS})
    endif()
    if(arg_CXX_STANDARD)
        set_target_properties(${target} PROPERTIES
            CXX_STANDARD ${arg_CXX_STANDARD} CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)
    endif()
endfunction()
