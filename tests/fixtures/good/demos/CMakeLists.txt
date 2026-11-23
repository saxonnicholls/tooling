#
#  CMakeLists.txt
#  snicholls-tooling test fixture
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
function(fixture_add_demo name source)
    add_executable(${name} ${source})
    target_link_libraries(${name} PRIVATE snicholls::fixture)
    snicholls_fixture_options(${name})
    add_test(NAME demo.${name} COMMAND ${name})
    set_tests_properties(demo.${name} PROPERTIES LABELS demo)
endfunction()

fixture_add_demo(version_demo version_demo.cpp)
fixture_add_demo(widget_demo widget_demo.cpp)
fixture_add_demo(concepts_greeter_demo concepts/greeter_demo.cpp)
fixture_add_demo(interfaces_greeter_demo interfaces/greeter_demo.cpp)
