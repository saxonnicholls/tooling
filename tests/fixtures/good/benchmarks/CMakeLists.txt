#
#  CMakeLists.txt
#  snicholls-tooling test fixture
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
add_executable(widget_benchmark widget_benchmark.cpp)
target_link_libraries(widget_benchmark PRIVATE snicholls::fixture)
snicholls_fixture_options(widget_benchmark)
add_test(NAME benchmark.widget COMMAND widget_benchmark)
set_tests_properties(benchmark.widget PROPERTIES LABELS benchmark)
