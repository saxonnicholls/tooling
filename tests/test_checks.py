#
#  test_checks.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The checks against the fixture repository: tests/fixtures/good passes every one, and for each rule a copy of it
#  with that one rule broken fails, naming the problem.
#
#      python3 -m unittest discover -s tests -v
#

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

TOOLING = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOD = os.path.join(TOOLING, "tests", "fixtures", "good")
sys.path.insert(0, os.path.join(TOOLING, "scripts"))

import tooling_conf  # noqa: E402
import check_interfaces  # noqa: E402

INC = "include/snicholls/fixture"


class Fixture(unittest.TestCase):
    """A fresh copy of the good fixture per test, with helpers to break it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "repo")
        shutil.copytree(GOOD, self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(text))

    def edit(self, rel, old, new):
        with open(self.path(rel), encoding="utf-8") as f:
            text = f.read()
        self.assertIn(old, text, "the fixture changed under the test")
        with open(self.path(rel), "w", encoding="utf-8") as f:
            f.write(text.replace(old, new))

    def remove(self, rel):
        os.remove(self.path(rel))

    def conf(self, line):
        with open(self.path("tooling.conf"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def run_check(self, name, *args):
        p = subprocess.run([sys.executable, os.path.join(TOOLING, "scripts", "check_%s.py" % name), "--root",
                            self.root, *args], capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def passes(self, name, *args):
        code, out = self.run_check(name, *args)
        self.assertEqual(code, 0, out)
        return out

    def fails(self, name, message, *args, code=1):
        got, out = self.run_check(name, *args)
        self.assertEqual(got, code, out)
        self.assertIn(message, out)
        return out


class ConfigTest(unittest.TestCase):
    def test_parses_keys_values_and_comments(self):
        values = tooling_conf.parse("# a comment\n\nname = x  # trailing\nregex = a#b\ncmake = -DA=1 -DB=2\n")
        self.assertEqual(values, {"name": "x", "regex": "a#b", "cmake": "-DA=1 -DB=2"})

    def test_rejects_a_key_set_twice(self):
        with self.assertRaisesRegex(tooling_conf.ConfigError, "set twice"):
            tooling_conf.parse("a = 1\na = 2\n")

    def test_rejects_a_line_that_is_not_key_value(self):
        with self.assertRaisesRegex(tooling_conf.ConfigError, "expected 'key = value'"):
            tooling_conf.parse("just words\n")

    def test_flags_are_yes_or_no(self):
        conf = tooling_conf.Config("/", {"a": "yes", "b": "off", "c": "maybe"}, "tooling.conf")
        self.assertTrue(conf.flag("a", False))
        self.assertFalse(conf.flag("b", True))
        self.assertTrue(conf.flag("missing", True))
        with self.assertRaises(tooling_conf.ConfigError):
            conf.flag("c", True)

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, os.path.join(TOOLING, "scripts", "tooling_conf.py"), "--root", GOOD, *args],
                           capture_output=True, text=True)
        return p.returncode, p.stdout.strip(), p.stderr

    def test_the_command_line_gets_a_value_or_its_default(self):
        self.assertEqual(self.run_cli("get", "option_prefix"), (0, "SNICHOLLS_FIXTURE_", ""))
        self.assertEqual(self.run_cli("get", "missing", "fallback")[:2], (0, "fallback"))
        self.assertEqual(self.run_cli("get", "missing", "")[:2], (0, ""))
        code, _, err = self.run_cli("get", "missing")
        self.assertEqual(code, 1)
        self.assertIn("sets no missing", err)

    def test_the_command_line_reads_flags_as_yes_or_no(self):
        self.assertEqual(self.run_cli("flag", "docs", "no")[:2], (0, "yes"))
        self.assertEqual(self.run_cli("flag", "missing", "off")[:2], (0, "no"))
        code, _, err = self.run_cli("flag", "name", "no")
        self.assertEqual(code, 2)
        self.assertIn("must be yes or no", err)

    def test_include_root_must_be_under_include_dir(self):
        conf = tooling_conf.Config("/", {"include_root": "src/x"}, "tooling.conf")
        with self.assertRaisesRegex(tooling_conf.ConfigError, "not under include_dir"):
            conf.include_root()


class MirrorTest(Fixture):
    def test_the_fixture_mirrors(self):
        self.assertIn("5 headers; 6 tests, 4 demos, 1 benchmarks", self.passes("mirror"))

    def test_no_config_is_a_configuration_error(self):
        self.remove("tooling.conf")
        self.fails("mirror", "no ", code=2)

    def test_a_header_without_a_test_fails(self):
        self.remove("tests/version_test.cpp")
        self.edit("tests/CMakeLists.txt", "fixture_add_test(version_test version_test.cpp)\n", "")
        self.fails("mirror", "header %s/version.hpp has no test: expected tests/version_test.cpp" % INC)

    def test_a_header_without_a_demo_fails(self):
        self.remove("demos/widget_demo.cpp")
        self.edit("demos/CMakeLists.txt", "fixture_add_demo(widget_demo widget_demo.cpp)\n", "")
        self.fails("mirror", "has no demo: expected demos/widget_demo.cpp")

    def test_an_unlisted_test_fails(self):
        self.edit("tests/CMakeLists.txt", "fixture_add_test(widget_test widget_test.cpp)\n", "")
        self.fails("mirror", "tests/widget_test.cpp exists but is not listed")

    def test_an_unlisted_demo_fails(self):
        self.edit("demos/CMakeLists.txt", "concepts/greeter_demo.cpp", "concepts/other_demo.cpp")
        self.fails("mirror", "demos/concepts/greeter_demo.cpp exists but is not listed")

    def test_a_listed_name_inside_a_longer_one_is_not_listed(self):
        self.edit("tests/CMakeLists.txt", "widget_test.cpp)", "xwidget_test.cpp)")
        self.fails("mirror", "tests/widget_test.cpp exists but is not listed")

    def test_a_test_without_a_header_fails(self):
        self.write("tests/gone_test.cpp", "int main() {}\n")
        self.fails("mirror", "tests/gone_test.cpp has no header: expected %s/gone.hpp" % INC)

    def test_a_demo_without_a_header_fails(self):
        self.write("demos/area/gone_demo.cpp", "int main() {}\n")
        self.fails("mirror", "demos/area/gone_demo.cpp has no header")

    def test_a_benchmark_without_a_header_fails(self):
        self.write("benchmarks/gone_benchmark.cpp", "int main() {}\n")
        self.fails("mirror", "benchmarks/gone_benchmark.cpp has no header")

    def test_an_unlisted_benchmark_fails(self):
        self.edit("benchmarks/CMakeLists.txt", "add_executable(widget_benchmark widget_benchmark.cpp)",
                  "add_executable(widget_benchmark)")
        self.fails("mirror", "benchmarks/widget_benchmark.cpp exists but is not listed")

    def test_a_header_needs_no_benchmark(self):
        self.remove("benchmarks/widget_benchmark.cpp")
        self.edit("benchmarks/CMakeLists.txt", "widget_benchmark.cpp", "")
        self.passes("mirror")

    def test_an_unlisted_companion_test_fails(self):
        self.edit("tests/CMakeLists.txt", "fixture_add_test(widget_limits_test widget_limits_test.cpp)\n", "")
        self.fails("mirror", "tests/widget_limits_test.cpp exists but is not listed")

    def test_a_detail_header_needs_a_test_but_no_demo(self):
        self.remove("tests/detail/twice_test.cpp")
        self.fails("mirror", "header %s/detail/twice.hpp has no test" % INC)

    def test_detail_needs_test_no_exempts_detail_headers(self):
        self.remove("tests/detail/twice_test.cpp")
        self.edit("tests/CMakeLists.txt", "fixture_add_test(detail_twice_test detail/twice_test.cpp)\n", "")
        self.conf("detail_needs_test = no")
        self.passes("mirror")

    def test_the_umbrella_header_is_exempt_only_when_named(self):
        self.edit("tooling.conf", "umbrella       = fixture.hpp", "")
        self.fails("mirror", "header %s/fixture.hpp has no test" % INC)

    def test_a_listed_only_directory_needs_listing_not_headers(self):
        self.conf("mirror_listed_only = support")
        self.write("tests/support/harness_test.cpp", "int main() {}\n")
        self.fails("mirror", "tests/support/harness_test.cpp exists but is not listed")
        self.edit("tests/CMakeLists.txt", "fixture_add_test(version_test",
                  "fixture_add_test(harness_test support/harness_test.cpp)\nfixture_add_test(version_test")
        self.passes("mirror")

    def test_an_ignored_directory_is_not_mirrored(self):
        self.write("tests/fixtures/data_test.cpp", "int main() {}\n")
        self.passes("mirror")

    def test_a_listing_in_a_subdirectory_cmakelists_counts(self):
        self.edit("tests/CMakeLists.txt", "fixture_add_test(concepts_greeter_test concepts/greeter_test.cpp)\n",
                  "add_subdirectory(concepts)\n")
        self.write("tests/concepts/CMakeLists.txt", "fixture_add_test(concepts_greeter_test greeter_test.cpp)\n")
        self.passes("mirror")

    def test_listing_by_stem_for_a_registration_function(self):
        self.write("demos/CMakeLists.txt", """\
            my_add_demo(version)
            my_add_demo(widget)
            my_add_demo(concepts/greeter)
            my_add_demo(interfaces/greeter)
            """)
        self.fails("mirror", "demos/version_demo.cpp exists but is not listed")
        self.conf("mirror_listed_by = stem")
        self.passes("mirror")


class VersionTest(Fixture):
    def test_the_fixture_agrees(self):
        self.assertIn("1.2.3 everywhere", self.passes("version"))

    def test_a_matching_tag_passes(self):
        self.passes("version", "--tag", "v1.2.3")

    def test_the_tag_comes_from_the_environment_too(self):
        env = dict(os.environ, RELEASE_TAG="v1.2.4")
        p = subprocess.run([sys.executable, os.path.join(TOOLING, "scripts", "check_version.py"), "--root", self.root],
                           capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)

    def test_a_different_tag_fails(self):
        self.fails("version", "tag v1.2.4 says 1.2.4", "--tag", "v1.2.4")

    def test_a_malformed_tag_fails(self):
        self.fails("version", "is not vX.Y.Z", "--tag", "release-1")

    def test_header_and_cmake_disagreeing_fails(self):
        self.edit("CMakeLists.txt", "VERSION 1.2.3", "VERSION 1.3.0")
        self.fails("version", "CMakeLists.txt says 1.3.0")

    def test_a_missing_macro_fails(self):
        self.edit(INC + "/version.hpp", "#define SNICHOLLS_FIXTURE_VERSION_PATCH 3", "")
        self.fails("version", "SNICHOLLS_FIXTURE_VERSION_PATCH is not defined")

    def test_a_macro_in_a_comment_is_not_the_version(self):
        # The fixture carries "// #define SNICHOLLS_FIXTURE_VERSION_MAJOR 9" above the real one
        self.edit(INC + "/version.hpp", "#define SNICHOLLS_FIXTURE_VERSION_MAJOR 1\n", "")
        self.fails("version", "SNICHOLLS_FIXTURE_VERSION_MAJOR is not defined")

    def test_a_missing_project_version_fails(self):
        self.edit("CMakeLists.txt", "project(snicholls_fixture VERSION 1.2.3", "project(snicholls_fixture")
        self.fails("version", "project(snicholls_fixture VERSION x.y.z) is not in CMakeLists.txt")

    def test_another_projects_version_is_not_ours(self):
        self.edit("CMakeLists.txt", "project(snicholls_fixture VERSION 1.2.3", "project(snicholls_other VERSION 1.2.3")
        self.fails("version", "is not in CMakeLists.txt")

    def test_an_extra_version_file_that_agrees_passes(self):
        self.write("pyproject.toml", 'version = "1.2.3"\n')
        self.conf(r'version_file.pyproject = pyproject.toml ^version\s*=\s*"(\d+\.\d+\.\d+)"')
        self.assertIn("pyproject.toml", self.passes("version"))

    def test_an_extra_version_file_that_disagrees_fails(self):
        self.write("pyproject.toml", 'version = "1.2.0"\n')
        self.conf(r'version_file.pyproject = pyproject.toml ^version\s*=\s*"(\d+\.\d+\.\d+)"')
        self.fails("version", "pyproject.toml says 1.2.0")

    def test_an_extra_version_file_that_is_missing_fails(self):
        self.conf(r'version_file.pyproject = pyproject.toml ^version\s*=\s*"(\d+\.\d+\.\d+)"')
        self.fails("version", "pyproject.toml does not exist")

    def test_a_version_string_in_the_header_by_its_three_parts(self):
        self.edit(INC + "/version.hpp", "#endif", 'inline constexpr const char* version_string = "1.2.4";\n#endif')
        self.conf(r'version_file.string = %s/version.hpp version_string\s*=\s*"(\d+)\.(\d+)\.(\d+)"' % INC)
        self.fails("version", "says 1.2.4")

    def test_missing_settings_are_a_configuration_error(self):
        self.edit("tooling.conf", "macro_prefix   = SNICHOLLS_FIXTURE_", "")
        self.fails("version", "'macro_prefix' is required", code=2)


class InterfacesTest(Fixture):
    def test_the_fixture_has_both_forms(self):
        self.assertIn("1 capability", self.passes("interfaces"))

    def test_an_interface_without_its_concept_fails(self):
        self.remove(INC + "/concepts/greeter.hpp")
        self.edit(INC + "/interfaces/greeter.hpp", "#include <snicholls/fixture/concepts/greeter.hpp>", "")
        self.fails("interfaces", "interface greeter_interface has no concept twin: expected %s/concepts/greeter.hpp"
                   % INC)

    def test_a_concept_without_its_interface_fails(self):
        self.write(INC + "/concepts/counter.hpp", """\
            namespace snicholls { template <class T> concept counter = requires(T t) { t.count(); }; }
            """)
        self.write("tests/concepts/counter_test.cpp", "")
        self.write("tests/interfaces/counter_test.cpp", "")
        self.fails("interfaces", "concepts/counter.hpp has no virtual twin: expected %s/interfaces/counter.hpp" % INC)

    def test_a_concepts_header_without_a_concept_fails(self):
        self.write(INC + "/concepts/greeter.hpp", "namespace snicholls { struct greeter_tag {}; }\n")
        self.fails("interfaces", "concepts/greeter.hpp declares no concept")

    def test_a_pure_virtual_class_outside_interfaces_fails(self):
        self.write(INC + "/sink.hpp", """\
            namespace snicholls {
            class sink {
            public:
                virtual ~sink() = default;
                virtual void write(int level) = 0;
            };
            }
            """)
        self.fails("interfaces", "sink.hpp:5: class sink has pure virtual functions but no concept twin")

    def test_an_exempt_class_passes(self):
        self.write(INC + "/sink.hpp", "namespace snicholls { struct sink { virtual void write() = 0; }; }\n")
        self.conf("interfaces_exempt = sink")
        self.passes("interfaces")

    def test_type_erasure_in_detail_is_exempt(self):
        self.write(INC + "/detail/model.hpp", "namespace snicholls::detail { struct concept_base { virtual int f() const = 0; }; }\n")
        self.write(INC + "/any_thing.hpp", "namespace snicholls { namespace detail { struct base { virtual int f() = 0; }; } }\n")
        self.passes("interfaces")

    def test_a_missing_concept_test_fails(self):
        self.remove("tests/concepts/greeter_test.cpp")
        self.fails("interfaces", "has no unit test for its concept form: expected tests/concepts/greeter_test.cpp")

    def test_a_missing_interface_test_fails(self):
        self.remove("tests/interfaces/greeter_test.cpp")
        self.fails("interfaces", "has no unit test for its interface form: expected tests/interfaces/greeter_test.cpp")

    def test_a_concept_outside_the_namespace_fails(self):
        self.edit(INC + "/concepts/greeter.hpp", "namespace snicholls\n", "namespace elsewhere\n")
        self.fails("interfaces", "concept greeter is in namespace 'elsewhere', not in snicholls")

    def test_an_interface_outside_the_namespace_fails(self):
        self.edit(INC + "/interfaces/greeter.hpp", "namespace snicholls\n", "namespace elsewhere\n")
        self.fails("interfaces", "interface greeter_interface is in namespace 'elsewhere'")

    def test_a_nested_namespace_is_inside(self):
        self.edit(INC + "/concepts/greeter.hpp", "namespace snicholls\n", "namespace snicholls::io\n")
        self.passes("interfaces")

    def test_capabilities_in_an_area_mirror_there(self):
        for form in ("concepts", "interfaces"):
            os.makedirs(self.path(INC + "/io/" + form))
            os.rename(self.path("%s/%s/greeter.hpp" % (INC, form)), self.path("%s/io/%s/greeter.hpp" % (INC, form)))
        self.fails("interfaces", "expected tests/io/concepts/greeter_test.cpp")
        for form in ("concepts", "interfaces"):
            os.makedirs(self.path("tests/io/" + form))
            os.rename(self.path("tests/%s/greeter_test.cpp" % form), self.path("tests/io/%s/greeter_test.cpp" % form))
        self.passes("interfaces")

    def test_a_support_header_in_interfaces_needs_no_twin(self):
        self.write(INC + "/interfaces/greeter_conformance.hpp", "namespace snicholls { inline bool conforms() { return true; } }\n")
        self.passes("interfaces")


class ScannerTest(unittest.TestCase):
    def scan(self, src):
        return check_interfaces.scan(textwrap.dedent(src))

    def test_finds_pure_virtual_functions_with_their_class_and_namespace(self):
        abstract, _ = self.scan("""\
            namespace a { namespace b {
            struct outer {
                struct inner { virtual void f() const noexcept = 0; };
                void g() { int x = 0; (void)x; }
            };
            } }
            """)
        self.assertEqual(abstract, {"inner": (3, "a::b")})

    def test_an_override_can_be_pure(self):
        abstract, _ = self.scan("struct d : base { void f() override = 0; };")
        self.assertIn("d", abstract)

    def test_initialised_members_are_not_pure_virtual(self):
        abstract, _ = self.scan("""\
            struct s {
                int x = 0;
                static constexpr int n = 0;
                virtual ~s() = default;
                virtual int f() { return 0; }
            };
            """)
        self.assertEqual(abstract, {})

    def test_comments_strings_and_the_preprocessor_are_ignored(self):
        abstract, concepts = self.scan("""\
            // struct c { virtual void f() = 0; };
            /* concept fake = true; */
            #define X struct m { virtual void f() = 0; };
            const char* s = "struct q { virtual void f() = 0; };";
            """)
        self.assertEqual((abstract, concepts), ({}, {}))

    def test_template_parameters_and_enum_classes_are_not_classes(self):
        abstract, concepts = self.scan("""\
            namespace n {
            enum class colour { red };
            template <class T, class U = int>
            struct [[nodiscard]] alignas(8) holder : T { virtual void f() = 0; };
            template <class T> concept small = sizeof(T) < 4;
            }
            """)
        self.assertEqual(abstract, {"holder": (4, "n")})
        self.assertEqual(concepts, {"small": (5, "n")})


class GatePlan(Fixture):
    """scripts/test_ubuntu.sh --plan: the configurations the gate would run, without Docker."""

    def plan(self, *args):
        p = subprocess.run(["bash", os.path.join(TOOLING, "scripts", "test_ubuntu.sh"), "--repo", self.root, "--plan",
                            *args], capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def configs(self, *args):
        code, out, err = self.plan(*args)
        self.assertEqual(code, 0, err)
        return {line.split()[0]: line.split()[1:] for line in out.splitlines()[1:]}


class GatePlanTest(GatePlan):

    def test_eight_configurations_in_two_images(self):
        configs = self.configs()
        self.assertEqual(list(configs), ["gcc-release", "gcc-debug", "clang-release", "clang-debug", "clang-asan",
                                         "gcc-asan", "gcc15-release", "gcc15-asan"])
        self.assertEqual({c: v[0].split("+")[0] for c, v in configs.items()},
                         {c: "ubuntu-26.04" if c.startswith("gcc15") else "ubuntu-24.04" for c in configs})
        for args in configs.values():
            self.assertIn("-DSNICHOLLS_FIXTURE_WERROR=ON", args)
        self.assertIn("-DSNICHOLLS_FIXTURE_SANITIZE=address,undefined", configs["clang-asan"])
        self.assertIn("-DCMAKE_CXX_COMPILER=g++-15", configs["gcc15-asan"])
        self.assertIn("-DCMAKE_BUILD_TYPE=Debug", configs["clang-debug"])

    def test_docs_in_gcc_release_and_benchmarks_in_both_releases(self):
        configs = self.configs()
        self.assertIn("-DSNICHOLLS_FIXTURE_BUILD_DOCS=ON", configs["gcc-release"])
        for c in ("gcc-release", "gcc15-release"):
            self.assertIn("-DSNICHOLLS_FIXTURE_BUILD_BENCHMARKS=ON", configs[c])
        others = [a for c, v in configs.items() if c not in ("gcc-release", "gcc15-release") for a in v]
        self.assertFalse([a for a in others if "BUILD_DOCS" in a or "BUILD_BENCHMARKS" in a])

    def test_a_repository_without_docs_or_benchmarks(self):
        self.edit("tooling.conf", "docs           = yes", "docs = no")
        self.edit("tooling.conf", "benchmarks     = yes", "benchmarks = no")
        args = [a for v in self.configs().values() for a in v]
        self.assertFalse([a for a in args if "BUILD_DOCS" in a or "BUILD_BENCHMARKS" in a])

    def test_quick_is_gcc_release_alone(self):
        self.assertEqual(list(self.configs("--quick")), ["gcc-release"])

    def test_only_names_configurations(self):
        self.assertEqual(list(self.configs("--only", "clang-asan,gcc15-release")), ["clang-asan", "gcc15-release"])

    def test_an_unknown_name_is_a_usage_error(self):
        code, _, err = self.plan("--only", "msvc")
        self.assertEqual(code, 2)
        self.assertIn("no configuration 'msvc'", err)

    def test_a_subset_of_configurations(self):
        self.conf("configurations = gcc-release clang-asan")
        self.assertEqual(list(self.configs()), ["gcc-release", "clang-asan"])
        self.assertEqual(list(self.configs("--quick")), ["gcc-release"])

    def test_an_unknown_configured_name_is_a_configuration_error(self):
        self.conf("configurations = gcc-release icc")
        code, _, err = self.plan()
        self.assertEqual(code, 2)
        self.assertIn("unknown configuration 'icc'", err)

    def test_cmake_arguments_for_all_and_for_one(self):
        self.conf("cmake = -DWITH_X=ON  # every configuration")
        self.conf("cmake.clang-debug = -DWITH_Y=ON -DWITH_Z=OFF")
        configs = self.configs()
        for args in configs.values():
            self.assertIn("-DWITH_X=ON", args)
        self.assertEqual(configs["clang-debug"][-2:], ["-DWITH_Y=ON", "-DWITH_Z=OFF"])
        self.assertNotIn("-DWITH_Y=ON", configs["gcc-debug"])

    def test_an_extra_configuration(self):
        self.conf("extra.clang-tsan = ubuntu-24.04 -DCMAKE_CXX_COMPILER=clang++ -DSNICHOLLS_FIXTURE_SANITIZE=thread")
        configs = self.configs()
        self.assertEqual(list(configs)[-1], "clang-tsan")
        self.assertEqual(configs["clang-tsan"], ["ubuntu-24.04", "-DSNICHOLLS_FIXTURE_WERROR=ON",
                                                 "-DCMAKE_CXX_COMPILER=clang++", "-DSNICHOLLS_FIXTURE_SANITIZE=thread"])
        self.assertNotIn("clang-tsan", self.configs("--quick"))

    def test_an_extra_configuration_needs_a_tooling_image(self):
        self.conf("extra.cuda = cuda-12 -DX=1")
        code, _, err = self.plan()
        self.assertEqual(code, 2)
        self.assertIn("names no image of tooling's", err)

    def test_environment_and_setup_are_reported(self):
        self.conf("env = ASAN_OPTIONS=detect_leaks=0 POCL_CACHE_DIR=/work/pocl")
        self.conf("setup = echo ready")
        _, out, _ = self.plan()
        self.assertIn("env ASAN_OPTIONS=detect_leaks=0 POCL_CACHE_DIR=/work/pocl", out)
        self.assertIn("setup echo ready", out)

    def test_no_option_prefix_is_a_configuration_error(self):
        self.edit("tooling.conf", "option_prefix  = SNICHOLLS_FIXTURE_", "")
        code, _, err = self.plan()
        self.assertEqual(code, 2)
        self.assertIn("option_prefix", err)

    def test_list_names_the_configurations_this_run(self):
        def names(*args):
            p = subprocess.run(["bash", os.path.join(TOOLING, "scripts", "test_ubuntu.sh"), "--repo", self.root,
                                "--list", *args], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout.split()
        self.conf("extra.clang-tsan = ubuntu-24.04 -DCMAKE_CXX_COMPILER=clang++")
        self.assertEqual(names(), list(self.configs()))
        self.assertEqual(names()[-1], "clang-tsan")
        self.assertEqual(names("--quick"), ["gcc-release"])
        self.assertEqual(names("--only", "gcc-asan,clang-tsan"), ["gcc-asan", "clang-tsan"])

    def test_image_needs_a_configuration_name(self):
        code, _, err = self.plan("--image", "msvc")
        self.assertEqual(code, 2)
        self.assertIn("--image: no configuration 'msvc'", err)

    def test_no_config_is_a_configuration_error(self):
        self.remove("tooling.conf")
        code, _, err = self.plan()
        self.assertEqual(code, 2)
        self.assertIn("tooling.conf", err)



class DerivedImagePlanTest(GatePlan):
    """image and image.<config>: a configuration runs in the repository's own image, derived from its standard one."""

    DOCKERFILE = "docker/ci/Dockerfile"

    def setUp(self):
        super().setUp()
        self.edit("tooling.conf", "image.gcc-debug = docker/ci/Dockerfile", "")
        self.edit("tooling.conf", "cmake.gcc-debug = -DSNICHOLLS_FIXTURE_IN_DERIVED_IMAGE=ON", "")

    def test_the_fixture_runs_gcc_debug_in_its_own_image(self):
        shutil.rmtree(self.root)
        shutil.copytree(GOOD, self.root)
        configs = self.configs()
        self.assertEqual(configs["gcc-debug"][0], "ubuntu-24.04+" + self.DOCKERFILE)
        self.assertIn("-DSNICHOLLS_FIXTURE_IN_DERIVED_IMAGE=ON", configs["gcc-debug"])
        self.assertEqual([c for c, v in configs.items() if "+" in v[0]], ["gcc-debug"])

    def test_without_image_keys_every_configuration_runs_in_a_standard_image(self):
        self.assertFalse([c for c, v in self.configs().items() if "+" in v[0]])

    def test_image_for_one_configuration(self):
        self.conf("image.clang-asan = " + self.DOCKERFILE)
        configs = self.configs()
        self.assertEqual(configs["clang-asan"][0], "ubuntu-24.04+" + self.DOCKERFILE)
        self.assertEqual(configs["clang-debug"][0], "ubuntu-24.04")

    def test_image_for_every_configuration_on_each_ones_standard_image(self):
        self.conf("image = " + self.DOCKERFILE)
        self.conf("image.gcc15-asan = docker/other/Dockerfile")
        self.write("docker/other/Dockerfile", "FROM ghcr.io/saxonnicholls/ubuntu-26.04@sha256:" + "0" * 64 + "\n")
        configs = self.configs()
        self.assertEqual(configs["gcc-release"][0], "ubuntu-24.04+" + self.DOCKERFILE)
        self.assertEqual(configs["gcc15-release"][0], "ubuntu-26.04+" + self.DOCKERFILE)
        self.assertEqual(configs["gcc15-asan"][0], "ubuntu-26.04+docker/other/Dockerfile")

    def test_image_for_an_extra_configuration(self):
        self.conf("extra.opencl = ubuntu-24.04 -DCMAKE_CXX_COMPILER=clang++")
        self.conf("image.opencl = " + self.DOCKERFILE)
        self.assertEqual(self.configs()["opencl"][0], "ubuntu-24.04+" + self.DOCKERFILE)

    def fails_to_plan(self, message):
        code, _, err = self.plan()
        self.assertEqual(code, 2, err)
        self.assertIn(message, err)

    def test_an_image_for_no_configuration_is_a_configuration_error(self):
        self.conf("image.msvc = " + self.DOCKERFILE)
        self.fails_to_plan("image.msvc names no configuration")

    def test_a_missing_dockerfile_is_a_configuration_error(self):
        self.conf("image.gcc-asan = docker/none/Dockerfile")
        self.fails_to_plan("image.gcc-asan: no Dockerfile docker/none/Dockerfile")

    def test_a_dockerfile_from_another_base_is_refused(self):
        self.edit(self.DOCKERFILE, "FROM ${TOOLING_IMAGE}", "FROM ubuntu:24.04")
        self.conf("image.gcc-asan = " + self.DOCKERFILE)
        self.fails_to_plan("the first FROM is ubuntu:24.04, not the ubuntu-24.04 image")

    def test_a_published_image_of_the_wrong_standard_image_is_refused(self):
        self.edit(self.DOCKERFILE, "FROM ${TOOLING_IMAGE}", "FROM ghcr.io/saxonnicholls/ubuntu-24.04:0.1.0")
        self.conf("image = " + self.DOCKERFILE)
        self.fails_to_plan("the first FROM is ghcr.io/saxonnicholls/ubuntu-24.04:0.1.0, not the ubuntu-26.04 image")

    def test_a_later_stage_from_elsewhere_is_refused(self):
        self.edit(self.DOCKERFILE, "FROM ${TOOLING_IMAGE}", "FROM ${TOOLING_IMAGE} AS build\nFROM debian:12")
        self.conf("image.gcc-asan = " + self.DOCKERFILE)
        self.fails_to_plan("FROM debian:12 is neither the ubuntu-24.04 image nor an earlier stage")

    def test_a_later_stage_from_an_earlier_one_is_allowed(self):
        self.edit(self.DOCKERFILE, "FROM ${TOOLING_IMAGE}", "FROM ${TOOLING_IMAGE} AS build\nFROM build")
        self.conf("image.gcc-asan = " + self.DOCKERFILE)
        self.assertIn("+", self.configs()["gcc-asan"][0])


if __name__ == "__main__":
    unittest.main()
