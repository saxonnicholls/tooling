#
#  test_cmake.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  cmake/SnichollsTooling.cmake against the fixture repository: snicholls_header_check() builds for the good fixture
#  and fails for each way a header can be wrong; snicholls_tooling_add_checks() adds the checks as passing CTests.
#  Needs CMake and a C++20 compiler; skipped without them.
#
#      python3 -m unittest discover -s tests -v
#

import os
import shutil
import subprocess
import unittest

from test_checks import Fixture, INC, TOOLING

CMAKE = shutil.which("cmake")
GENERATOR = ["-G", "Ninja"] if shutil.which("ninja") else []
TARGET = "snicholls_fixture_header_check"


@unittest.skipUnless(CMAKE, "cmake is not installed")
class HeaderCheckTest(Fixture):
    def setUp(self):
        super().setUp()
        self.build = os.path.join(self.tmp, "build")

    def configure(self):
        return subprocess.run([CMAKE, "-S", self.root, "-B", self.build, *GENERATOR,
                               "-DSNICHOLLS_TOOLING_ROOT=" + TOOLING, "-DSNICHOLLS_FIXTURE_WERROR=ON"],
                              capture_output=True, text=True)

    def compile(self, target=TARGET):
        p = self.configure()
        if p.returncode != 0:
            return p
        return subprocess.run([CMAKE, "--build", self.build, "--target", target], capture_output=True, text=True)

    def compiles(self, target=TARGET):
        p = self.compile(target)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def fails_to_compile(self, message, target=TARGET):
        p = self.compile(target)
        self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn(message, p.stdout + p.stderr)

    def test_every_good_header_compiles_alone_twice(self):
        self.compiles()
        generated = sorted(os.listdir(os.path.join(self.build, TARGET)))
        self.assertEqual(len([f for f in generated if f.endswith(".cpp")]), 6)

    def test_the_checks_are_ctests_that_pass(self):
        self.assertEqual(self.configure().returncode, 0)
        p = subprocess.run(["ctest", "--test-dir", self.build, "-R", "^check\\.", "-L", "boundary"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertRegex(p.stdout, r"100% tests passed(, 0 tests failed)? out of 4")

    def test_a_check_ctest_fails_when_its_rule_does(self):
        self.remove("tests/version_test.cpp")
        self.edit("tests/CMakeLists.txt", "fixture_add_test(version_test version_test.cpp)\n", "")
        self.assertEqual(self.configure().returncode, 0)
        p = subprocess.run(["ctest", "--test-dir", self.build, "-R", "^check\\.mirror$"], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0, p.stdout)

    def test_a_missing_include_fails(self):
        self.edit(INC + "/widget.hpp", "#include <snicholls/fixture/detail/twice.hpp>", "")
        p = self.compile()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("twice", p.stdout + p.stderr)

    def test_a_misnamed_guard_fails(self):
        self.edit(INC + "/widget.hpp", "snicholls_fixture_widget_hpp", "WIDGET_HPP")
        self.fails_to_compile("is not guarded by snicholls_fixture_widget_hpp")

    def test_pragma_once_fails(self):
        self.edit(INC + "/widget.hpp", "#ifndef snicholls_fixture_widget_hpp\n#define snicholls_fixture_widget_hpp",
                  "#pragma once")
        self.edit(INC + "/widget.hpp", "}\n\n#endif", "}\n")
        self.fails_to_compile("never #pragma once")

    def test_no_guard_fails_on_the_second_include(self):
        self.edit(INC + "/detail/twice.hpp",
                  "#ifndef snicholls_fixture_detail_twice_hpp\n#define snicholls_fixture_detail_twice_hpp", "")
        self.edit(INC + "/detail/twice.hpp", "}\n\n#endif", "}\n")
        self.fails_to_compile("twice")

    def test_without_a_guard_prefix_the_guard_name_is_not_checked(self):
        self.edit("tooling.conf", "guard_prefix   = snicholls_fixture_", "")
        self.edit(INC + "/widget.hpp", "snicholls_fixture_widget_hpp", "WIDGET_HPP")
        self.compiles()

    def test_an_excluded_header_is_not_compiled(self):
        self.write(INC + "/backend.hpp", "#error needs a backend that is not configured\n")
        self.fails_to_compile("needs a backend")
        self.edit("CMakeLists.txt", "LINK snicholls::fixture)", "LINK snicholls::fixture EXCLUDE \"/backend\\\\.hpp$\")")
        self.compiles()

    def test_headers_and_a_cxx_standard(self):
        self.edit("CMakeLists.txt", "snicholls_tooling_add_checks()", """snicholls_tooling_add_checks()
snicholls_header_check(cpp17_check HEADERS snicholls/fixture/widget.hpp CXX_STANDARD 17)
snicholls_header_check(cpp17_concepts HEADERS snicholls/fixture/concepts/greeter.hpp CXX_STANDARD 17)""")
        self.compiles("cpp17_check")
        p = self.compile("cpp17_concepts")
        self.assertNotEqual(p.returncode, 0, "a C++20 concept compiled as C++17")

    def test_brackets_and_semicolons_in_a_value_do_not_hide_the_next_lines(self):
        self.edit("tooling.conf", "name           =", "odd = ^v[0-9;\nname           =")
        self.edit(INC + "/widget.hpp", "snicholls_fixture_widget_hpp", "WIDGET_HPP")
        self.fails_to_compile("is not guarded by snicholls_fixture_widget_hpp")

    def test_no_config_fails_configure(self):
        self.remove("tooling.conf")
        p = self.configure()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("tooling.conf", p.stdout + p.stderr)

    def test_a_malformed_config_fails_configure(self):
        self.conf("this is not a setting")
        p = self.configure()
        self.assertNotEqual(p.returncode, 0)
        # CMake wraps a long message across lines on some platforms: compare with the whitespace normalised
        self.assertIn("expected 'key = value'", " ".join((p.stdout + p.stderr).split()))


if __name__ == "__main__":
    unittest.main()
