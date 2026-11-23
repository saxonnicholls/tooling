#
#  test_make.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  make/tooling.mk in the fixture repository, included as a repository includes it (one line, from the vendored
#  third_party/tooling): what each target runs, driven by tooling.conf (make -n), and the targets that build, run for
#  real. Needs make; the builds need CMake and a C++20 compiler, and are skipped without them.
#
#      python3 -m unittest discover -s tests -v
#

import os
import shutil
import subprocess
import tempfile
import unittest

from test_checks import TOOLING

MAKE = shutil.which("make")
CMAKE = shutil.which("cmake")
DOXYGEN = shutil.which("doxygen")


@unittest.skipUnless(MAKE, "make is not installed")
class MakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())   # as make's $(CURDIR) has it: macOS's /var is /private/var
        self.root = os.path.join(self.tmp, "repo")
        subprocess.run([os.path.join(TOOLING, "tests", "fixture_repo.sh"), self.root], check=True)
        with open(os.path.join(self.root, "Makefile"), "w", encoding="utf-8") as f:
            f.write("include third_party/tooling/make/tooling.mk\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conf(self, old, new):
        path = os.path.join(self.root, "tooling.conf")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if old:
            self.assertIn(old, text)
            text = text.replace(old, new)
        else:
            text += new + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def make(self, *args):
        p = subprocess.run([MAKE, "--no-print-directory", *args], cwd=self.root, capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def dry(self, *args):
        code, out, err = self.make("-n", *args)
        self.assertEqual(code, 0, err)
        return out.splitlines()

    def line(self, lines, start):
        found = [line for line in lines if line.startswith(start)]
        self.assertTrue(found, "no line starts %r in:\n%s" % (start, "\n".join(lines)))
        return found[0].split()

    # What each target runs

    def test_check_runs_the_four_checks(self):
        lines = self.dry("check")
        for check in ("version", "mirror", "interfaces"):
            self.assertIn("check_%s.py" % check, " ".join(lines))
        self.assertIn("single_include.py --root", lines[3])
        self.assertTrue(lines[3].endswith("--check"), lines[3])
        self.assertEqual(len(lines), 4)

    def test_test_checks_then_configures_builds_and_runs_every_ctest(self):
        lines = self.dry("test")
        self.assertIn("single_include.py --root", lines[0])   # rewritten first, so a local gate never runs stale
        self.assertFalse(lines[0].endswith("--check"), lines[0])
        self.assertIn("check_version.py", lines[1])
        configure = self.line(lines, "cmake -S . -B build ")
        self.assertIn("-DCMAKE_BUILD_TYPE=Release", configure)
        self.assertIn("-DCMAKE_CXX_COMPILER=c++", configure)
        self.line(lines, "cmake --build build --parallel")
        self.assertEqual(lines[-1], "ctest --test-dir build --output-on-failure")

    def test_test_werror_sets_the_repositorys_werror_option(self):
        configure = self.line(self.dry("test-werror"), "cmake -S . -B build-werror")
        self.assertIn("-DSNICHOLLS_FIXTURE_WERROR=ON", configure)

    def test_asan_is_address_and_undefined_with_warnings_as_errors(self):
        configure = self.line(self.dry("asan"), "cmake -S . -B build-asan")
        self.assertIn("-DCMAKE_BUILD_TYPE=RelWithDebInfo", configure)
        self.assertIn("-DSNICHOLLS_FIXTURE_SANITIZE=address,undefined", configure)
        self.assertIn("-DSNICHOLLS_FIXTURE_WERROR=ON", configure)

    def test_docs_builds_the_docs_target(self):
        lines = self.dry("docs")
        self.assertIn("-DSNICHOLLS_FIXTURE_BUILD_DOCS=ON", self.line(lines, "cmake -S . -B build-docs"))
        self.assertEqual(lines[-1], "cmake --build build-docs --target docs")

    def test_ubuntu_runs_the_gate_with_its_arguments(self):
        gate = self.line(self.dry("ubuntu", "UBUNTU=--quick -j 2"), os.path.join(self.root, "third_party"))
        self.assertTrue(gate[0].endswith("third_party/tooling/scripts/test_ubuntu.sh"))
        self.assertEqual(gate[1:], ["--repo", self.root, "--quick", "-j", "2"])

    def test_demos_and_benchmarks_run_their_ctest_labels(self):
        self.assertEqual(self.dry("demos")[-1], "ctest --test-dir build -L demo --verbose")
        lines = self.dry("benchmarks")
        configure = self.line(lines, "cmake -S . -B build-bench")
        self.assertIn("-DSNICHOLLS_FIXTURE_BUILD_BENCHMARKS=ON", configure)
        self.assertIn("-DCMAKE_BUILD_TYPE=Release", configure)
        self.assertEqual(lines[-1], "ctest --test-dir build-bench -L benchmark --verbose")

    def test_commands_of_the_repositorys_own_replace_the_runs(self):
        self.conf(None, "make.demos = scripts/run_demos.sh --all")
        self.conf(None, "make.benchmarks = python3 scripts/benchmarks_md.py --build build-bench")
        self.assertEqual(self.dry("demos"), ["BUILD=build CONFIG=Release CXX=c++ scripts/run_demos.sh --all"])
        self.assertEqual(self.dry("benchmarks")[-1],
                         "BUILD=build-bench CONFIG=Release CXX=c++ python3 scripts/benchmarks_md.py --build build-bench")

    def test_cmake_arguments_from_the_conf_and_the_command_line(self):
        self.conf(None, "cmake = -DWITH_X=ON -DWITH_Y=OFF")
        for target, build in (("test", "build"), ("asan", "build-asan"), ("docs", "build-docs"),
                              ("benchmarks", "build-bench")):
            configure = self.line(self.dry(target, "CMAKE_FLAGS=-DWITH_Z=1"), "cmake -S . -B " + build)
            self.assertIn("-DWITH_X=ON", configure, target)
            self.assertIn("-DWITH_Y=OFF", configure, target)
            self.assertEqual(configure[-1], "-DWITH_Z=1", target)

    def test_compiler_build_directory_and_type(self):
        lines = self.dry("test", "CXX=clang++", "BUILD=build-x", "CONFIG=Debug")
        configure = self.line(lines, "cmake -S . -B build-x")
        self.assertIn("-DCMAKE_CXX_COMPILER=clang++", configure)
        self.assertIn("-DCMAKE_BUILD_TYPE=Debug", configure)

    def test_clean_removes_every_build_directory(self):
        self.assertEqual(self.dry("clean"), ["rm -rf build build-werror build-asan build-docs build-bench"])

    # What tooling.conf rules out

    def test_without_docs_make_docs_fails_and_says_why(self):
        self.conf("docs           = yes", "docs = no")
        code, _, err = self.make("docs")
        self.assertNotEqual(code, 0)
        self.assertIn("no documentation to build (tooling.conf: docs = no)", err)

    def test_without_benchmarks_make_benchmarks_fails_and_says_why(self):
        self.conf("benchmarks     = yes", "benchmarks = no")
        code, _, err = self.make("benchmarks")
        self.assertNotEqual(code, 0)
        self.assertIn("no benchmarks to build (tooling.conf: benchmarks = no)", err)

    def test_without_an_option_prefix_every_target_fails(self):
        self.conf("option_prefix  = SNICHOLLS_FIXTURE_", "")
        code, _, err = self.make("-n", "test")
        self.assertNotEqual(code, 0)
        self.assertIn("sets no option_prefix", err)

    def test_a_malformed_conf_fails(self):
        self.conf(None, "docs_extra = 1\nthis is not a setting")
        code, _, err = self.make("-n", "check")
        self.assertNotEqual(code, 0)
        self.assertIn("expected 'key = value'", err)

    # The targets, run

    def test_check_passes_and_fails_with_its_rules(self):
        code, out, err = self.make("check")
        self.assertEqual(code, 0, out + err)
        os.remove(os.path.join(self.root, "tests", "widget_test.cpp"))
        code, out, err = self.make("check")
        self.assertNotEqual(code, 0)
        self.assertIn("widget", out + err)

    @unittest.skipUnless(CMAKE, "cmake is not installed")
    def test_test_werror_demos_and_benchmarks_run(self):
        for target, expect in (("test-werror", "100% tests passed"), ("demos", "demo.widget_demo"),
                               ("benchmarks", "benchmark.widget")):
            code, out, err = self.make(target, "JOBS=4")
            self.assertEqual(code, 0, out + err)
            self.assertIn(expect, out, target)

    @unittest.skipUnless(CMAKE and DOXYGEN, "cmake or doxygen is not installed")
    def test_docs_builds_the_html(self):
        code, out, err = self.make("docs")
        self.assertEqual(code, 0, out + err)
        self.assertTrue(os.path.exists(os.path.join(self.root, "build-docs", "docs", "html", "index.html")))

    @unittest.skipUnless(CMAKE, "cmake is not installed")
    def test_a_failing_test_fails_make_test(self):
        with open(os.path.join(self.root, "tests", "widget_test.cpp"), "w", encoding="utf-8") as f:
            f.write("int main() { return 1; }\n")
        code, out, _ = self.make("test", "JOBS=4")
        self.assertNotEqual(code, 0)
        self.assertIn("widget_test", out)


if __name__ == "__main__":
    unittest.main()
