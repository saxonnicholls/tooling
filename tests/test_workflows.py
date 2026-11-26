#
#  test_workflows.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The workflows' static rules (STANDARDS section 6, CI): every action is pinned by its commit SHA, every job holds
#  least privilege, and the reusable library workflow is what the README documents and what tooling's own CI calls.
#  actionlint checks the syntax in CI; the workflows run for real there.
#
#      python3 -m unittest discover -s tests -v
#

import os
import re
import shutil
import subprocess
import tempfile
import unittest

from test_checks import TOOLING

WORKFLOWS = os.path.join(TOOLING, ".github", "workflows")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def blocks(text, key, indent):
    """The children of the top-level-or-nested mapping <key>: at <indent>, as {name: text of its block}."""
    m = re.search(r"^%s%s:\n" % (" " * (indent - 2), re.escape(key)), text, re.M)
    if not m:
        return {}
    out, name, body = {}, None, []
    for line in text[m.end():].splitlines():
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        head = re.match(r"^ {%d}([A-Za-z0-9_-]+):" % indent, line)
        if head:
            if name:
                out[name] = "\n".join(body)
            name, body = head.group(1), []
        else:
            body.append(line)
    if name:
        out[name] = "\n".join(body)
    return out


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.files = {f: read(os.path.join(WORKFLOWS, f)) for f in sorted(os.listdir(WORKFLOWS)) if f.endswith(".yml")}
        self.library = self.files["library.yml"]

    def test_every_action_is_pinned_by_its_commit_sha(self):
        for name, text in self.files.items():
            for ref in re.findall(r"^\s*(?:-\s+)?uses:\s*(\S+)", text, re.M):
                if ref.startswith("./"):
                    continue
                self.assertRegex(ref, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$", "%s: %s is not pinned by SHA" % (name, ref))

    def test_every_workflow_starts_read_only_or_scopes_each_job(self):
        for name, text in self.files.items():
            if re.search(r"^permissions:\n  contents: read$", text, re.M):
                continue
            jobs = blocks(text, "jobs", 2)
            self.assertTrue(jobs, name)
            for job, body in jobs.items():
                if name == "library.yml" and job in ("docs", "single-include"):
                    continue   # the caller's grant: contents: write only where pages or the release asset is wanted
                self.assertIn("\n    permissions:", "\n" + body, "%s: job %s sets no permissions" % (name, job))

    def test_the_library_workflow_is_reusable_with_documented_inputs(self):
        self.assertRegex(self.library, r"(?m)^on:\n  workflow_call:\n")
        inputs = blocks(self.library, "inputs", 6)
        self.assertEqual(set(inputs), {"path", "tooling", "prepare", "linux_arm64", "macos", "msvc",
                                       "msvc_continue_on_error", "benchmarks", "odr_check", "docs", "pages"})
        readme = read(os.path.join(TOOLING, "README.md"))
        for name, body in inputs.items():
            self.assertIn("description:", body, name)
            self.assertIn("| `%s` |" % name, readme, "README documents no input %s" % name)
            self.assertIn("inputs.%s" % name, self.library.replace("${{ inputs.%s }}" % name, "inputs.%s" % name),
                          "input %s is never used" % name)

    def test_the_library_workflow_runs_the_legs(self):
        jobs = blocks(self.library, "jobs", 2)
        self.assertEqual(list(jobs), ["plan", "checks", "linux", "macos", "windows", "odr", "docs", "single-include"])
        self.assertIn("test_ubuntu.sh\" --repo . --only \"$CONFIGURATION\"", jobs["linux"])
        self.assertIn("ubuntu-24.04-arm", jobs["plan"])
        self.assertIn("continue-on-error: ${{ inputs.msvc_continue_on_error }}", jobs["windows"])
        self.assertIn("-DCMAKE_CXX_FLAGS_DEBUG=-O0", jobs["macos"])
        self.assertIn("if: inputs.pages && github.event_name == 'push'", jobs["docs"])
        # the single include: generated from the tagged commit, compiled alone, attached to the release
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", jobs["single-include"])
        self.assertIn("needs: [plan, checks, linux, macos, odr]", jobs["single-include"])
        self.assertIn("gh release upload", jobs["single-include"])
        self.assertIn("single_include.py\" --check", jobs["checks"])
        # one version of each library: the pins, with their tags (a full clone), strict on a release tag
        self.assertIn("check_pins.py\"", jobs["checks"])
        self.assertIn("fetch-depth: 0", jobs["checks"])
        pins_step = jobs["checks"].split("- name: One version of each library")[1]
        self.assertIn("RELEASE_TAG: ${{ startsWith(github.ref, 'refs/tags/v')", pins_step)
        # and the one definition rule, at the link
        self.assertIn("if: inputs.odr_check", jobs["odr"])
        for flag in ("-DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON", "-DCMAKE_CXX_FLAGS=-flto -Wodr -Werror=odr",
                     '"-D${P}WERROR=ON"', "-DCMAKE_CXX_COMPILER=g++", "ctest --test-dir build-odr"):
            self.assertIn(flag, jobs["odr"])

    def test_tooling_calls_it_on_the_fixture(self):
        tools = blocks(self.files["tools.yml"], "jobs", 2)
        self.assertIn("uses: ./.github/workflows/library.yml", tools["library"])
        self.assertIn("prepare: tests/fixture_repo.sh fixture-repo", tools["library"])
        self.assertIn("path: fixture-repo", tools["library"])


def real_gcc():
    gxx = shutil.which("g++")
    if not gxx:
        return None
    p = subprocess.run([gxx, "--version"], capture_output=True, text=True)
    return gxx if "Free Software Foundation" in p.stdout else None   # macOS's g++ is Clang


@unittest.skipUnless(real_gcc(), "no GCC (macOS's g++ is Clang); the Linux leg runs it")
class OdrFlagsTest(unittest.TestCase):
    """The odr job's flags, read from the workflow, fail the link of two definitions of one type, as two versions
    of a library linked into one program are; without them the program links silently."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        flags = re.search(r'"-DCMAKE_CXX_FLAGS=([^"]+)"', read(os.path.join(WORKFLOWS, "library.yml"))).group(1)
        self.flags = flags.split()
        for name, text in (("a.cpp", "struct widget { int a; };\nint use(widget* w) { return w->a; }\n"),
                           ("b.cpp", "struct widget { long a; double b; };\nint use(widget* w);\n"
                                     "int main() { widget w{1, 2}; return use(&w) == 1 ? 0 : 1; }\n")):
            with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as f:
                f.write(text)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def link(self, *flags):
        return subprocess.run([real_gcc(), "-std=c++20", "-O2", *flags, "a.cpp", "b.cpp", "-o", "program"],
                              cwd=self.tmp, capture_output=True, text=True)

    def test_two_definitions_of_one_type_fail_the_link(self):
        p = self.link(*self.flags)
        self.assertNotEqual(p.returncode, 0, p.stderr)
        self.assertIn("violates the C++ One Definition Rule", p.stderr)

    def test_without_lto_they_link_silently(self):
        self.assertEqual(self.link().returncode, 0)


if __name__ == "__main__":
    unittest.main()
