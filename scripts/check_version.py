#!/usr/bin/env python3
#
#  check_version.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  One release, one number (STANDARDS section 2). The version is written down in several places - the macros
#  <macro_prefix>VERSION_MAJOR, _MINOR and _PATCH in the version header, project(<cmake_project> VERSION x.y.z) in
#  CMakeLists.txt, the release tag, and any other file the repository names - and the failure mode is not that they
#  disagree loudly: it is a release where find_package() reports one number and the header another. So every copy is
#  compared on every build.
#
#      python3 third_party/tooling/scripts/check_version.py [--root <repository>] [--config <tooling.conf>]
#      python3 third_party/tooling/scripts/check_version.py --tag v1.2.3      # and the tag (or $RELEASE_TAG)
#
#  Settings (tooling.conf):
#    macro_prefix           e.g. SNICHOLLS_CORE_ (required)
#    cmake_project          e.g. snicholls_core (required)
#    version_header         default <include_root>/version.hpp
#    version_file.<label>   <path> <regex>: one more copy, the regex's groups joined with '.', e.g.
#                           version_file.pyproject = pyproject.toml ^version\s*=\s*"(\d+\.\d+\.\d+)"
#
#  A version string in the header is one more copy, named like any other:
#      version_file.string = include/snicholls/core/version.hpp string\s*=\s*"(\d+\.\d+\.\d+)"
#  Exit status 0 when every copy agrees, 1 when one does not, 2 on a configuration error.
#

import argparse
import os
import re
import sys

sys.dont_write_bytecode = True   # nothing written into a consumer's submodule checkout
import tooling_conf  # noqa: E402

TOOL = "check_version"


class Missing(Exception):
    pass


def read(root, rel):
    path = os.path.join(root, rel)
    if not os.path.exists(path):
        raise Missing("%s does not exist" % rel)
    with open(path, encoding="utf-8") as f:
        return f.read()


def strip_comments(src):
    # Comments go, string literals stay (a // inside a string is left alone)
    pattern = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)
    return pattern.sub(lambda m: m.group(0) if m.group(0).startswith('"') else " ", src)


def header_versions(root, rel, prefix):
    src = strip_comments(read(root, rel))
    parts = []
    for field in ("MAJOR", "MINOR", "PATCH"):
        m = re.search(r"^\s*#\s*define\s+%sVERSION_%s\s+(\d+)\s*$" % (re.escape(prefix), field), src, re.M)
        if not m:
            raise Missing("%sVERSION_%s is not defined in %s" % (prefix, field, rel))
        parts.append(str(int(m.group(1))))
    return [(rel, ".".join(parts))]


def cmake_version(root, project):
    src = re.sub(r"#.*", "", read(root, "CMakeLists.txt"))
    # The VERSION belonging to project(), not to cmake_minimum_required()
    m = re.search(r"\bproject\s*\(\s*%s\b[^)]*?\bVERSION\s+(\d+\.\d+\.\d+)" % re.escape(project), src, re.S | re.I)
    if not m:
        raise Missing("project(%s VERSION x.y.z) is not in CMakeLists.txt" % project)
    return m.group(1)


def file_version(root, label, spec):
    try:
        rel, pattern = spec.split(None, 1)
    except ValueError:
        raise tooling_conf.ConfigError("version_file.%s must be '<path> <regex>'" % label)
    m = re.search(pattern, read(root, rel), re.M)
    if not m or not m.groups():
        raise Missing("%s: no version matches %s" % (rel, pattern))
    version = ".".join(m.groups())
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise Missing("%s: %s is not x.y.z" % (rel, version))
    return rel, version


def main():
    ap = argparse.ArgumentParser(description="Check that the version is the same everywhere it is written")
    tooling_conf.add_arguments(ap)
    ap.add_argument("--tag", default=os.environ.get("RELEASE_TAG"),
                    help="a release tag to check too, with or without its leading 'v' (default: $RELEASE_TAG)")
    args = ap.parse_args()
    conf = tooling_conf.load_or_exit(args, TOOL)

    try:
        prefix = conf.require("macro_prefix")
        project = conf.require("cmake_project")
        header = conf.get("version_header") or conf.include_root() + "/version.hpp"
        found = header_versions(conf.root, header, prefix)
        found.append(("CMakeLists.txt", cmake_version(conf.root, project)))
        for label, spec in conf.prefixed("version_file").items():
            found.append(file_version(conf.root, label, spec))
    except tooling_conf.ConfigError as e:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
        return 2
    except Missing as e:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
        print("%s: FAILED - one release, one number" % TOOL, file=sys.stderr)
        return 1
    if args.tag:
        if not re.fullmatch(r"v?\d+\.\d+\.\d+", args.tag):
            print("%s: tag %s is not vX.Y.Z" % (TOOL, args.tag), file=sys.stderr)
            return 1
        found.append(("tag " + args.tag, args.tag.lstrip("v")))

    width = max(len(where) for where, _ in found)
    for where, version in found:
        print("  %-*s  %s" % (width, where, version), flush=True)
    if len({version for _, version in found}) != 1:
        expected = found[0][1]
        for where, version in found[1:]:
            if version != expected:
                print("%s: %s says %s, %s says %s" % (TOOL, where, version, found[0][0], expected), file=sys.stderr)
        print("%s: FAILED - one release, one number" % TOOL, file=sys.stderr)
        return 1
    print("%s: ok - %s everywhere" % (TOOL, found[0][1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
