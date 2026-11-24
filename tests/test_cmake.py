#
#  test_cmake.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  cmake/SnichollsTooling.cmake against the fixture repository: snicholls_header_check() builds for the good fixture
#  and fails for each way a header can be wrong; snicholls_tooling_add_checks() adds the checks as passing CTests.
#  cmake/SnichollsOneVersion.cmake against a scratch top-level project that adds copies of a fake library, as
#  snicholls-core's diamond test does. Needs CMake and a C++20 compiler; skipped without them.
#
#      python3 -m unittest discover -s tests -v
#

import os
import shutil
import subprocess
import tempfile
import textwrap
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


@unittest.skipUnless(CMAKE, "cmake is not installed")
class OneVersionTest(unittest.TestCase):
    """snicholls_library_begin, snicholls_require and snicholls_assert_single_versions, with copies of a fake library
    (its CMakeLists.txt as a library's is written) added to a scratch top-level project."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def library(self, folder, version, name="fake"):
        path = os.path.join(self.tmp, folder)
        os.makedirs(path)
        with open(os.path.join(path, "CMakeLists.txt"), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent("""\
                cmake_minimum_required(VERSION 3.20)
                project(%(name)s VERSION %(version)s LANGUAGES NONE)
                include("%(tooling)s/cmake/SnichollsTooling.cmake")
                snicholls_library_begin(%(name)s ${PROJECT_VERSION} %(name)s::%(name)s)
                message(STATUS "defining %(name)s from ${CMAKE_CURRENT_LIST_DIR}")
                add_library(%(name)s INTERFACE)
                add_library(%(name)s::%(name)s ALIAS %(name)s)
                """ % {"name": name, "version": version, "tooling": TOOLING}))
        return path

    def configure(self, body):
        src = os.path.join(self.tmp, "top")
        os.makedirs(src, exist_ok=True)
        with open(os.path.join(src, "CMakeLists.txt"), "w", encoding="utf-8") as f:
            f.write("cmake_minimum_required(VERSION 3.20)\nproject(top LANGUAGES NONE)\n"
                    'include("%s/cmake/SnichollsTooling.cmake")\n%s\n' % (TOOLING, textwrap.dedent(body)))
        p = subprocess.run([CMAKE, "-S", src, "-B", os.path.join(self.tmp, "build"), *GENERATOR],
                           capture_output=True, text=True)
        return p.returncode, " ".join((p.stdout + p.stderr).split())   # CMake wraps long messages

    def test_the_same_version_twice_is_one_copy_and_passes(self):
        a, b = self.library("a", "1.2.0"), self.library("b", "1.2.0")
        code, out = self.configure("""
            add_subdirectory("%s" a)
            add_subdirectory("%s" b)
            snicholls_require(fake 1.1.0)
            get_property(seen GLOBAL PROPERTY SNICHOLLS_LIBRARY_VERSIONS_SEEN)
            message(STATUS "seen: ${seen}")
            snicholls_assert_single_versions()
            """ % (a, b))
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("defining fake from"), 1, out)   # the second copy returned before its target
        self.assertIn("defining fake from %s" % a, out)
        self.assertIn("fake 1.2.0: fake::fake is already defined from %s; this copy (%s) is skipped" % (a, b), out)
        self.assertIn("seen: fake@1.2.0", out)
        self.assertIn("top: fake 1.2.0 satisfies the required minimum 1.1.0", out)
        self.assertIn("top: one version of each library in the build (1 reached)", out)
        self.assertNotIn("CMake Warning", out)

    def test_two_versions_warn_then_fail_the_assertion_listing_every_copy(self):
        a, b = self.library("a", "1.2.0"), self.library("b", "1.1.0")
        code, out = self.configure("""
            add_subdirectory("%s" a)
            add_subdirectory("%s" b)
            snicholls_assert_single_versions()
            """ % (a, b))
        self.assertNotEqual(code, 0, out)
        self.assertIn("fake 1.1.0 at %s is skipped: fake 1.2.0 at %s was added first and wins" % (b, a), out)
        self.assertIn("More than one version of a library was reached in this build: fake: 1.2.0, 1.1.0 "
                      "1.2.0 at %s 1.1.0 at %s" % (a, b), out)

    def test_without_the_assertion_the_first_copy_wins_with_a_warning(self):
        a, b = self.library("a", "1.2.0"), self.library("b", "1.1.0")
        code, out = self.configure('add_subdirectory("%s" a)\nadd_subdirectory("%s" b)' % (a, b))
        self.assertEqual(code, 0, out)
        self.assertIn("CMake Warning", out)

    def test_every_library_is_asserted_on_its_own(self):
        a, b = self.library("a", "1.0.0"), self.library("b", "2.0.0", name="other")
        c = self.library("c", "2.0.1", name="other")
        code, out = self.configure("""
            add_subdirectory("%s" a)
            add_subdirectory("%s" b)
            add_subdirectory("%s" c)
            snicholls_assert_single_versions()
            """ % (a, b, c))
        self.assertNotEqual(code, 0, out)
        self.assertIn("other: 2.0.0, 2.0.1", out)
        self.assertNotIn("fake: 1.0.0", out)

    def test_a_consumer_requiring_newer_fails(self):
        a = self.library("a", "1.2.0")
        code, out = self.configure('add_subdirectory("%s" a)\nsnicholls_require(fake 1.3.0)' % a)
        self.assertNotEqual(code, 0, out)
        self.assertIn("top needs fake 1.3.0 or newer, but the copy that won is 1.2.0 (%s)" % a, out)

    def test_the_older_copy_added_first_wins_and_a_newer_requirement_fails(self):
        old, new = self.library("old", "1.0.0"), self.library("new", "1.2.0")
        code, out = self.configure('add_subdirectory("%s" old)\nadd_subdirectory("%s" new)\n'
                                   "snicholls_require(fake 1.2.0)" % (old, new))
        self.assertNotEqual(code, 0, out)
        self.assertIn("the copy that won is 1.0.0", out)

    def test_requiring_a_library_never_added_fails(self):
        code, out = self.configure("snicholls_require(fake 1.0.0)")
        self.assertNotEqual(code, 0, out)
        self.assertIn("snicholls_require(fake 1.0.0) was called before fake was added", out)

    def test_a_version_that_is_not_x_y_z_fails(self):
        code, out = self.configure("snicholls_library_begin(fake 1.2 fake::fake)")
        self.assertNotEqual(code, 0, out)
        self.assertIn("the version is not x.y.z", out)


if __name__ == "__main__":
    unittest.main()
