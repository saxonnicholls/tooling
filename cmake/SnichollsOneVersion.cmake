#
#  SnichollsOneVersion.cmake
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  One version of each library in a build (STANDARDS section 2), for any library: snicholls-core's three diamond
#  rules, made generic. A build reaches a library once through each repository that pins it, so one configure can
#  add two checkouts of it; at different commits they would compile and link quietly into one program. Included by
#  SnichollsTooling.cmake.
#
#  In a library's CMakeLists.txt, after project() and before it defines its target:
#
#      snicholls_library_begin(<name> <version> <target>)
#
#    records <name>@<version> and where it came from (rule 3). If <target> is already defined, another copy was
#    added first and won (rule 1): it says so - a warning naming both versions when they differ - and returns from
#    the calling CMakeLists.txt, so nothing after it runs for this copy. It is a macro so that its return() leaves
#    the caller's directory scope, as core's own `if(TARGET snicholls::core) ... return() endif()` does; call it at
#    the CMakeLists.txt's top level, never inside a function (there return() would leave only the function).
#
#  In every consumer, after the library is added:
#
#      snicholls_require(<name> <minimum>)
#
#    fails configure when the copy that won is older than <minimum>, or when <name> was never added (rule 2).
#
#  The last line of a top-level project:
#
#      snicholls_assert_single_versions()
#
#    fails configure when any library was reached at more than one version, listing each version and the
#    directory of every copy (CMAKE_CURRENT_LIST_DIR). The same version reached twice is fine (rule 3).
#
#  Global properties, readable by any project in the build:
#    SNICHOLLS_LIBRARIES                 every library recorded, by name
#    SNICHOLLS_LIBRARY_VERSIONS_SEEN     every distinct <name>@<version> reached, winner or not
#    SNICHOLLS_LIBRARY_<name>_VERSION    the version of the copy that won
#    SNICHOLLS_LIBRARY_<name>_SOURCE_DIR where that copy lives
#    SNICHOLLS_LIBRARY_<name>_COPIES     every copy reached, as "<version> at <directory>"
#

include_guard(GLOBAL)

function(_snicholls_library_record name version where)
    get_property(_libraries GLOBAL PROPERTY SNICHOLLS_LIBRARIES)
    list(APPEND _libraries "${name}")
    list(REMOVE_DUPLICATES _libraries)
    set_property(GLOBAL PROPERTY SNICHOLLS_LIBRARIES "${_libraries}")

    get_property(_seen GLOBAL PROPERTY SNICHOLLS_LIBRARY_VERSIONS_SEEN)
    list(APPEND _seen "${name}@${version}")
    list(REMOVE_DUPLICATES _seen)
    set_property(GLOBAL PROPERTY SNICHOLLS_LIBRARY_VERSIONS_SEEN "${_seen}")

    set_property(GLOBAL APPEND PROPERTY SNICHOLLS_LIBRARY_${name}_COPIES "${version} at ${where}")
endfunction()

# Sets _snicholls_library_skip in the caller: TRUE when another copy already defined the target
function(_snicholls_library_begin name version target where)
    if(NOT version MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+")
        message(FATAL_ERROR "snicholls_library_begin(${name} ${version} ${target}): the version is not x.y.z")
    endif()
    _snicholls_library_record("${name}" "${version}" "${where}")
    if(NOT TARGET ${target})
        set_property(GLOBAL PROPERTY SNICHOLLS_LIBRARY_${name}_VERSION "${version}")
        set_property(GLOBAL PROPERTY SNICHOLLS_LIBRARY_${name}_SOURCE_DIR "${where}")
        set(_snicholls_library_skip FALSE PARENT_SCOPE)
        return()
    endif()
    get_property(_winner GLOBAL PROPERTY SNICHOLLS_LIBRARY_${name}_VERSION)
    get_property(_winner_dir GLOBAL PROPERTY SNICHOLLS_LIBRARY_${name}_SOURCE_DIR)
    if(NOT _winner)
        set(_winner "an unrecorded version")
        set(_winner_dir "a copy that did not call snicholls_library_begin")
    endif()
    if(_winner VERSION_EQUAL version)
        message(STATUS "${name} ${version}: ${target} is already defined from ${_winner_dir}; "
                       "this copy (${where}) is skipped")
    else()
        message(WARNING "${name} ${version} at ${where} is skipped: ${name} ${_winner} at ${_winner_dir} was added "
                        "first and wins. Pin every dependency that carries ${name} to one release.")
    endif()
    set(_snicholls_library_skip TRUE PARENT_SCOPE)
endfunction()

macro(snicholls_library_begin name version target)
    _snicholls_library_begin("${name}" "${version}" "${target}" "${CMAKE_CURRENT_LIST_DIR}")
    if(_snicholls_library_skip)
        unset(_snicholls_library_skip)
        return()
    endif()
    unset(_snicholls_library_skip)
endmacro()

function(snicholls_require name minimum)
    get_property(_winner GLOBAL PROPERTY SNICHOLLS_LIBRARY_${name}_VERSION)
    if(NOT _winner)
        message(FATAL_ERROR "snicholls_require(${name} ${minimum}) was called before ${name} was added: "
                            "add_subdirectory() its checkout in third_party/ first")
    endif()
    if(_winner VERSION_LESS minimum)
        get_property(_where GLOBAL PROPERTY SNICHOLLS_LIBRARY_${name}_SOURCE_DIR)
        message(FATAL_ERROR "${PROJECT_NAME} needs ${name} ${minimum} or newer, but the copy that won is ${_winner} "
                            "(${_where}). The first copy added to the build wins, so bump the top-level project's pin.")
    endif()
    message(STATUS "${PROJECT_NAME}: ${name} ${_winner} satisfies the required minimum ${minimum}")
endfunction()

function(snicholls_assert_single_versions)
    get_property(_libraries GLOBAL PROPERTY SNICHOLLS_LIBRARIES)
    get_property(_seen GLOBAL PROPERTY SNICHOLLS_LIBRARY_VERSIONS_SEEN)
    set(_report "")
    set(_count 0)
    foreach(_name IN LISTS _libraries)
        set(_versions)
        foreach(_entry IN LISTS _seen)
            if(_entry MATCHES "^(.*)@([^@]*)$" AND CMAKE_MATCH_1 STREQUAL _name)
                list(APPEND _versions "${CMAKE_MATCH_2}")
            endif()
        endforeach()
        list(LENGTH _versions _n)
        math(EXPR _count "${_count} + 1")
        if(_n GREATER 1)
            get_property(_copies GLOBAL PROPERTY SNICHOLLS_LIBRARY_${_name}_COPIES)
            string(REPLACE ";" "\n    " _copies "${_copies}")
            string(REPLACE ";" ", " _versions "${_versions}")
            string(APPEND _report "  ${_name}: ${_versions}\n    ${_copies}\n")
        endif()
    endforeach()
    if(_report)
        message(FATAL_ERROR "More than one version of a library was reached in this build:\n${_report}"
                            "Pin every dependency that carries a library to the same release tag.")
    endif()
    message(STATUS "${PROJECT_NAME}: one version of each library in the build (${_count} reached)")
endfunction()
