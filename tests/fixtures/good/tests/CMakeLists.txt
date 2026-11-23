#
#  CMakeLists.txt
#  snicholls-tooling test fixture
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
function(fixture_add_test name source)
    add_executable(${name} ${source})
    target_link_libraries(${name} PRIVATE snicholls::fixture)
    snicholls_fixture_options(${name})
    add_test(NAME ${name} COMMAND ${name})
    set_tests_properties(${name} PROPERTIES LABELS unit)
endfunction()

fixture_add_test(version_test version_test.cpp)
fixture_add_test(widget_test widget_test.cpp)
fixture_add_test(widget_limits_test widget_limits_test.cpp)
fixture_add_test(detail_twice_test detail/twice_test.cpp)
fixture_add_test(concepts_greeter_test concepts/greeter_test.cpp)
fixture_add_test(interfaces_greeter_test interfaces/greeter_test.cpp)
