#
#  CMakeLists.txt
#  snicholls-tooling test fixture
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  A minimal library in the family's shape, for testing snicholls-tooling: the options the gate sets, the header
#  check and the repository checks from tooling's CMake module, tests, demos and benchmarks as CTests.

cmake_minimum_required(VERSION 3.20)
project(snicholls_fixture VERSION 1.2.3 LANGUAGES CXX)

set(SNICHOLLS_TOOLING_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/third_party/tooling" CACHE PATH "snicholls-tooling's checkout")
include(${SNICHOLLS_TOOLING_ROOT}/cmake/SnichollsTooling.cmake)

option(SNICHOLLS_FIXTURE_WERROR "Warnings are errors" OFF)
option(SNICHOLLS_FIXTURE_BUILD_DOCS "Build the documentation" OFF)
option(SNICHOLLS_FIXTURE_BUILD_BENCHMARKS "Build the benchmarks" OFF)
set(SNICHOLLS_FIXTURE_SANITIZE "" CACHE STRING "Sanitizers, e.g. address,undefined")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(snicholls_fixture INTERFACE)
add_library(snicholls::fixture ALIAS snicholls_fixture)
target_include_directories(snicholls_fixture INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/include)

function(snicholls_fixture_options target)
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
    if(SNICHOLLS_FIXTURE_WERROR)
        target_compile_options(${target} PRIVATE -Werror)
    endif()
    if(SNICHOLLS_FIXTURE_SANITIZE)
        target_compile_options(${target} PRIVATE -fsanitize=${SNICHOLLS_FIXTURE_SANITIZE} -fno-omit-frame-pointer)
        target_link_options(${target} PRIVATE -fsanitize=${SNICHOLLS_FIXTURE_SANITIZE})
    endif()
endfunction()

enable_testing()
snicholls_header_check(snicholls_fixture_header_check LINK snicholls::fixture)
snicholls_fixture_options(snicholls_fixture_header_check)
snicholls_tooling_add_checks()

add_subdirectory(tests)
add_subdirectory(demos)
if(SNICHOLLS_FIXTURE_BUILD_BENCHMARKS)
    add_subdirectory(benchmarks)
endif()
if(SNICHOLLS_FIXTURE_BUILD_DOCS)
    find_package(Doxygen REQUIRED)
    configure_file(docs/Doxyfile.in ${CMAKE_CURRENT_BINARY_DIR}/Doxyfile @ONLY)
    add_custom_target(docs ALL COMMAND Doxygen::doxygen ${CMAKE_CURRENT_BINARY_DIR}/Doxyfile
                      WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR} VERBATIM)
endif()
