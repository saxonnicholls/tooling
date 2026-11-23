#!/usr/bin/env python3
#
#  check_mirror.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The mirror rule (STANDARDS section 4): tests/, demos/ and benchmarks/ mirror the public headers. For every header
#  <include_root>/<sub>/<name>.hpp:
#
#    tests/<sub>/<name>_test.cpp     exists and is listed in a CMakeLists.txt under tests/
#    demos/<sub>/<name>_demo.cpp     exists and is listed in a CMakeLists.txt under demos/ (not for detail/ headers)
#
#  and the other direction: a test, demo or benchmark with no header is an error, and so is one that exists but is
#  not listed, because a file that never runs looks finished. A benchmark is not required, but one that exists has
#  its header and is listed.
#
#      python3 third_party/tooling/scripts/check_mirror.py [--root <repository>] [--config <tooling.conf>]
#
#  Settings (tooling.conf):
#    include_root           the headers' directory, e.g. include/snicholls/core (required)
#    umbrella               the umbrella header, exempt: it has no behaviour of its own (e.g. core.hpp)
#    tests_dir, demos_dir, benchmarks_dir      default tests, demos, benchmarks
#    detail_needs_test      yes (default): a detail/ header has a test, though no demo; no: neither
#    mirror_ignore          directories under tests/, demos/, benchmarks/ that are not mirrored at all
#                           (default: cmake fixtures data)
#    mirror_listed_only     directories whose tests and demos need no header but must be listed (e.g. parity
#                           support tutorials)
#    mirror_listed_by       path (default): a file is listed when its path relative to the CMakeLists.txt appears in
#                           it; stem: its path without _test.cpp / _demo.cpp is enough, for a registration function
#                           called as my_add_test(<sub>/<name> ...)
#
#  Companion tests, <name>_<aspect>_test.cpp beside <name>_test.cpp, belong to <name>.hpp and must be listed.
#  Exit status 0 when the tree mirrors, 1 when it does not, 2 on a configuration error.
#

import argparse
import os
import posixpath
import re
import sys

sys.dont_write_bytecode = True   # nothing written into a consumer's submodule checkout
import tooling_conf  # noqa: E402

TOOL = "check_mirror"
KINDS = (("tests", "_test.cpp"), ("demos", "_demo.cpp"), ("benchmarks", "_benchmark.cpp"))


def walk(root, suffix, skip=()):
    """Files under root ending in suffix, as posix paths relative to root; top-level directories in skip are not
    entered."""
    for dirpath, dirs, files in os.walk(root):
        if dirpath == root:
            dirs[:] = [d for d in dirs if d not in skip]
        dirs.sort()
        for f in sorted(files):
            if f.endswith(suffix):
                yield os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")


def cmake_tokens(tree):
    """Every word of every CMakeLists.txt under tree, as a path relative to tree, so tests/a/CMakeLists.txt listing
    b_test.cpp lists a/b_test.cpp."""
    tokens = set()
    for dirpath, _, files in os.walk(tree):
        if "CMakeLists.txt" not in files:
            continue
        here = os.path.relpath(dirpath, tree).replace(os.sep, "/")
        with open(os.path.join(dirpath, "CMakeLists.txt"), encoding="utf-8") as f:
            text = re.sub(r"#.*", "", f.read())
        for word in re.split(r"[\s()\"']+", text):
            word = re.sub(r"^\$\{(CMAKE_CURRENT_SOURCE_DIR|CMAKE_CURRENT_LIST_DIR)\}/", "", word)
            if word and "$" not in word:
                tokens.add(posixpath.normpath(posixpath.join(here, word)))
    return tokens


def companion(rel, suffix, known):
    """<name>_<aspect><suffix> is a companion of <name><suffix> when that is a known file."""
    stem = rel[: -len(suffix)]
    while "_" in posixpath.basename(stem):
        stem = stem[: stem.rfind("_")]
        if stem in known:
            return True
    return False


def main():
    ap = argparse.ArgumentParser(description="Check that tests, demos and benchmarks mirror the headers")
    tooling_conf.add_arguments(ap)
    args = ap.parse_args()
    conf = tooling_conf.load_or_exit(args, TOOL)
    try:
        include_root = conf.include_root()
        detail_needs_test = conf.flag("detail_needs_test", True)
        by = conf.get("mirror_listed_by", "path")
        if by not in ("path", "stem"):
            raise tooling_conf.ConfigError("mirror_listed_by must be path or stem, not " + by)
    except tooling_conf.ConfigError as e:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
        return 2

    root = conf.root
    include = os.path.join(root, include_root)
    umbrella = conf.get("umbrella")
    ignore = set(conf.list("mirror_ignore", "cmake fixtures data"))
    listed_only = set(conf.list("mirror_listed_only"))
    dirs = {kind: conf.get(kind + "_dir", kind) for kind, _ in KINDS}
    if not os.path.isdir(include):
        print("%s: no %s (include_root)" % (TOOL, include_root), file=sys.stderr)
        return 2

    errors = []
    stems = set(walk(include, ".hpp"))
    stems = {h[: -len(".hpp")] for h in stems if h != umbrella}

    def listed(tokens, rel, suffix):
        return rel in tokens or (by == "stem" and rel[: -len(suffix)] in tokens)

    counts = {}
    for kind, suffix in KINDS:
        tree = os.path.join(root, dirs[kind])
        if not os.path.isdir(tree):
            if kind != "benchmarks" and stems:
                errors.append("no %s/ directory" % dirs[kind])
            continue
        tokens = cmake_tokens(tree)
        present = set(walk(tree, suffix, ignore))
        counts[kind] = 0

        # Each header has its file, listed
        for stem in sorted(stems):
            is_detail = "detail" in stem.split("/")
            required = (kind == "tests" and (detail_needs_test or not is_detail)) or (kind == "demos" and not is_detail)
            rel = stem + suffix
            if rel in present:
                counts[kind] += 1
                if not listed(tokens, rel, suffix):
                    errors.append("%s/%s exists but is not listed in a CMakeLists.txt under %s/" % (dirs[kind], rel, dirs[kind]))
            elif required:
                errors.append("header %s/%s.hpp has no %s: expected %s/%s"
                              % (include_root, stem, kind[:-1], dirs[kind], rel))

        # The other direction: nothing without a header, nothing unlisted
        known = {s + suffix for s in stems}
        for rel in sorted(present - known):
            top = rel.split("/")[0] if "/" in rel else None
            if top in listed_only or companion(rel, suffix, {s for s in stems}):
                counts[kind] += 1
                if not listed(tokens, rel, suffix):
                    errors.append("%s/%s exists but is not listed in a CMakeLists.txt under %s/" % (dirs[kind], rel, dirs[kind]))
            else:
                errors.append("%s/%s has no header: expected %s/%s.hpp"
                              % (dirs[kind], rel, include_root, rel[: -len(suffix)]))

    if errors:
        for e in errors:
            print("%s: %s" % (TOOL, e), file=sys.stderr)
        print("%s: FAILED - every header has a registered test and demo, and every file has its header" % TOOL,
              file=sys.stderr)
        return 1
    print("%s: ok - %d headers; %d tests, %d demos, %d benchmarks, each registered" % (
        TOOL, len(stems), counts.get("tests", 0), counts.get("demos", 0), counts.get("benchmarks", 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
