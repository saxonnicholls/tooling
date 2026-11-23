#!/usr/bin/env python3
#
#  single_include.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  Writes a repository's single-include headers, and proves the committed ones are fresh (STANDARDS section 2,
#  "The single include"). Every library ships single_include/<name>.hpp: its umbrella header with every header of
#  its own, and of the libraries it pins, expanded in place, each exactly once, so the library can be used by copying
#  one file. Everything else (standard and system includes, guards, #if blocks) is copied verbatim: the file is the
#  same code, not a rendering of it.
#
#      python3 third_party/tooling/scripts/single_include.py [--root <repository>] [--config <tooling.conf>]
#      python3 third_party/tooling/scripts/single_include.py --check     # exit 1 if any file is stale or incomplete
#
#  Settings (tooling.conf):
#    single_include.<name>   the umbrella header, as it is included (snicholls/core/core.hpp): writes
#                            <single_include_dir>/<name>.hpp. One line per file; at least one.
#    single_include_dir      default single_include
#    single_include_inline   the include directories whose headers are expanded, relative to the repository (default:
#                            include_dir). A pinned library's include directory belongs here, so the file needs nothing
#                            else: third_party/core/include.
#    single_include_opt_in   headers under include_root left out on purpose (they link a third party, say), relative
#                            to include_root; say why beside it
#    include_dir, include_root   as for the other checks
#
#  --check fails on:
#    - a file that differs from what this writes (stale: run `make single-include` and commit);
#    - a header under include_root that no single include contains and that is not opted in (incomplete: add it to
#      the umbrella), or an opted-in header that one contains anyway;
#    - a file in single_include_dir that no single_include.<name> line writes (an orphan rots in place).
#
#  Exit status 0 when fresh and complete, 1 when not, 2 on a configuration error.
#

import argparse
import os
import re
import sys

sys.dont_write_bytecode = True   # nothing written into a consumer's submodule checkout
import tooling_conf  # noqa: E402

TOOL = "single_include"
_INCLUDE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]')


class Expander:
    """Expands an umbrella header: each header found in an inline directory is written once, by its real path."""

    def __init__(self, roots):
        self.roots = roots
        self.seen = set()
        self.out = []

    def resolve(self, name, quoted, from_dir):
        bases = ([from_dir] if quoted and from_dir else []) + self.roots
        for base in bases:
            p = os.path.realpath(os.path.join(base, name))
            if os.path.isfile(p) and any(p.startswith(r + os.sep) for r in self.roots):
                return p
        return None

    def expand(self, path, stack=()):
        if path in self.seen:
            return
        if path in stack:
            raise tooling_conf.ConfigError("an include cycle: " + " -> ".join(stack + (path,)))
        self.seen.add(path)
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        for line in lines:
            m = _INCLUDE.match(line)
            target = m and self.resolve(m.group(2), m.group(1) == '"', os.path.dirname(path))
            if target:
                self.expand(target, stack + (path,))
            else:
                self.out.append(line)


def render(name, umbrella, roots):
    ex = Expander(roots)
    start = ex.resolve(umbrella, False, None)
    if not start:
        raise tooling_conf.ConfigError("single_include.%s: no header %s in %s" % (name, umbrella, " ".join(roots)))
    ex.expand(start)
    head = [
        "//",
        "//  %s.hpp" % name,
        "//",
        "//  GENERATED from <%s> by tooling's scripts/single_include.py: never edit by hand." % umbrella,
        "//  Regenerate with `make single-include`; CI fails while it is stale.",
        "//",
        "",
    ]
    return "\n".join(head + ex.out) + "\n", ex.seen


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--config")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    try:
        conf = tooling_conf.load(args.root, args.config)
        root = os.path.realpath(conf.root)
        files = conf.prefixed("single_include")
        if not files:
            raise tooling_conf.ConfigError("%s: no single_include.<name> line" % conf.path)
        out_dir = os.path.join(root, conf.get("single_include_dir", "single_include"))
        roots = [os.path.realpath(os.path.join(root, d)) for d in conf.list("single_include_inline", conf.include_dir())]
        for d in roots:
            if not os.path.isdir(d):
                raise tooling_conf.ConfigError("%s: single_include_inline %s is not a directory" % (conf.path, d))
        include_root = os.path.realpath(os.path.join(root, conf.include_root()))
        opt_in = {os.path.realpath(os.path.join(include_root, h)) for h in conf.list("single_include_opt_in")}
        rendered = {name: render(name, umbrella, roots) for name, umbrella in files.items()}
    except (tooling_conf.ConfigError, OSError) as e:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
        return 2

    if not args.check:
        os.makedirs(out_dir, exist_ok=True)
        for name, (text, _seen) in rendered.items():
            path = os.path.join(out_dir, name + ".hpp")
            old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            if old != text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                print("%s: wrote %s" % (TOOL, os.path.relpath(path, root)))
        return 0

    problems = []
    for name, (text, _seen) in rendered.items():
        path = os.path.join(out_dir, name + ".hpp")
        rel = os.path.relpath(path, root)
        if not os.path.exists(path):
            problems.append("%s is missing: run `make single-include` and commit it" % rel)
        elif open(path, encoding="utf-8").read() != text:
            problems.append("%s is stale: run `make single-include` and commit it" % rel)
    contained = set().union(*(seen for _text, seen in rendered.values()))
    for d, _dirs, names in os.walk(include_root):
        for n in sorted(names):
            p = os.path.realpath(os.path.join(d, n))
            if not n.endswith((".hpp", ".h")):
                continue
            rel = os.path.relpath(p, root)
            if p in opt_in and p in contained:
                problems.append("%s is opted out (single_include_opt_in) but a single include contains it" % rel)
            elif p not in opt_in and p not in contained:
                problems.append("%s is in no single include: include it from the umbrella, or opt it out" % rel)
    if os.path.isdir(out_dir):
        written = {name + ".hpp" for name in files}
        for n in sorted(os.listdir(out_dir)):
            if n not in written:
                problems.append("%s is written by no single_include.<name> line: delete it or configure it"
                                % os.path.relpath(os.path.join(out_dir, n), root))
    for p in problems:
        print("%s: %s" % (TOOL, p), file=sys.stderr)
    if problems:
        print("%s: FAILED - the single include must be fresh and complete" % TOOL, file=sys.stderr)
        return 1
    print("%s: ok - %d file(s), fresh and complete" % (TOOL, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
