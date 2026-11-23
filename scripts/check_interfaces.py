#!/usr/bin/env python3
#
#  check_interfaces.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  A concept and its virtual twin (STANDARDS section 3): neither form exists alone. Under the include root, at any
#  depth <area>/, it fails on
#
#    - a pure virtual interface, <area>/interfaces/<x>.hpp, with no concept twin <area>/concepts/<x>.hpp;
#    - a capability concept, <area>/concepts/<x>.hpp, with no virtual twin <area>/interfaces/<x>.hpp;
#    - concepts/<x>.hpp that declares no concept, or one outside the namespace;
#    - a class with pure virtual functions anywhere else (it belongs in interfaces/ with its concept), or one in
#      interfaces/ outside the namespace;
#    - either form without its unit test: tests/<area>/concepts/<x>_test.cpp and tests/<area>/interfaces/<x>_test.cpp.
#
#  A header in interfaces/ that declares no pure virtual class (the adapters, the reference implementation, the
#  conformance kit beside the interface) is not an interface and needs no twin.
#
#      python3 third_party/tooling/scripts/check_interfaces.py [--root <repository>] [--config <tooling.conf>]
#
#  Settings (tooling.conf):
#    include_root           e.g. include/snicholls/core (required)
#    namespace              e.g. snicholls: the concepts and interfaces are declared in it or in one nested in it
#    tests_dir              default tests
#    interfaces_exempt      class names that may have pure virtual functions outside interfaces/: say why beside it
#
#  Classes under a detail/ directory or in a detail namespace are internals (type erasure) and exempt.
#  Exit status 0 when every capability has both forms and both tests, 1 when not, 2 on a configuration error.
#

import argparse
import os
import re
import sys

sys.dont_write_bytecode = True   # nothing written into a consumer's submodule checkout
import tooling_conf  # noqa: E402

TOOL = "check_interfaces"

_TOKEN = re.compile(r"[A-Za-z_]\w*|\d[\w.']*|::|\S")
_SKIP = re.compile(
    r'//[^\n]*|/\*.*?\*/'                      # comments
    r'|R"([^(\s]*)\(.*?\)\1"'                  # raw strings
    r'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''  # strings and characters
    r'|^[ \t]*#(?:\\\n|[^\n])*', re.S | re.M)  # preprocessor lines, with continuations


def tokens(src):
    """(token, line) pairs, with comments, literals and preprocessor lines blanked but lines kept."""
    blank = _SKIP.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), src)
    out = []
    for n, line in enumerate(blank.split("\n"), 1):
        out.extend((t, n) for t in _TOKEN.findall(line))
    return out


def skip_attributes(toks, j):
    """The index after any [[attributes]] and alignas(...) starting at j."""
    while j < len(toks) and toks[j][0] in ("[", "alignas"):
        close = "]" if toks[j][0] == "[" else ")"
        depth = 0
        while j < len(toks):
            if toks[j][0] in ("[", "("):
                depth += 1
            elif toks[j][0] in ("]", ")"):
                depth -= 1
            j += 1
            if depth == 0 and toks[j - 1][0] == close:
                break
    return j


def scan(src):
    """The classes with pure virtual functions and the concepts a header declares:
    ({class: (line, namespace)}, {concept: (line, namespace)})."""
    toks = tokens(src)
    stack = []                    # (kind, name) per open brace: kind is "ns", "class" or None
    pending = None                # ("ns" | "class", name) waiting for its '{'
    statement = []                # tokens since the last ; { } or access specifier
    abstract, concepts = {}, {}

    def namespace():
        return "::".join(name for kind, name in stack if kind == "ns" and name)

    def in_class():
        return stack and stack[-1][0] == "class"

    i = 0
    while i < len(toks):
        t, line = toks[i]
        prev = toks[i - 1][0] if i else ""
        if t == "namespace":
            name, j = [], i + 1
            while j < len(toks) and (toks[j][0] == "::" or re.match(r"[A-Za-z_]", toks[j][0])) \
                    and toks[j][0] != "inline":
                name.append(toks[j][0])
                j += 1
            if j < len(toks) and toks[j][0] == "{":
                pending = ("ns", "".join(name))
            i = j
            continue
        if t in ("class", "struct", "union") and prev not in ("enum", "<", ",", "(", "friend", "typename", "template"):
            j = skip_attributes(toks, i + 1)
            if j < len(toks) and re.match(r"[A-Za-z_]", toks[j][0]):
                name = toks[j][0]
                while j + 2 < len(toks) and toks[j + 1][0] == "::":
                    j += 2
                    name = toks[j][0]
                pending = ("class", name)
            i = j + 1
            continue
        if t == "concept" and i + 2 < len(toks) and toks[i + 2][0] == "=" and not in_class():
            concepts.setdefault(toks[i + 1][0], (line, namespace()))
        if t == "{":
            stack.append(pending if pending else (None, None))
            pending, statement = None, []
        elif t == "}":
            if stack:
                stack.pop()
            pending, statement = None, []
        elif t == ";":
            if in_class() and len(statement) >= 3 and statement[-2:] == ["=", "0"] and ")" in statement \
                    and ("virtual" in statement or "override" in statement):
                abstract.setdefault(stack[-1][1], (line, namespace()))
            pending, statement = None, []
        elif t == "(" and pending and pending[0] == "class" and ":" not in statement:
            pending = None
        elif t == ":" and prev in ("public", "protected", "private") and in_class():
            statement = []
        else:
            statement.append(t)
        i += 1
    return abstract, concepts


def in_namespace(found, ns):
    return not ns or found == ns or found.startswith(ns + "::")


def main():
    ap = argparse.ArgumentParser(description="Check that every capability has a concept and a virtual twin, tested")
    tooling_conf.add_arguments(ap)
    args = ap.parse_args()
    conf = tooling_conf.load_or_exit(args, TOOL)
    try:
        include_root = conf.include_root()
    except tooling_conf.ConfigError as e:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
        return 2
    ns = conf.get("namespace", "")
    tests = conf.get("tests_dir", "tests")
    exempt = set(conf.list("interfaces_exempt"))
    include = os.path.join(conf.root, include_root)
    if not os.path.isdir(include):
        print("%s: no %s (include_root)" % (TOOL, include_root), file=sys.stderr)
        return 2

    headers = {}
    for dirpath, _, files in os.walk(include):
        for f in files:
            if f.endswith(".hpp"):
                rel = os.path.relpath(os.path.join(dirpath, f), include).replace(os.sep, "/")
                with open(os.path.join(dirpath, f), encoding="utf-8") as h:
                    headers[rel] = scan(h.read())

    errors, pairs = [], 0
    where = lambda rel: "%s/%s" % (include_root, rel)

    def twin(rel, form, other):
        parts = rel.split("/")
        k = len(parts) - 1 - parts[::-1].index(form)
        return "/".join(parts[:k] + [other] + parts[k + 1:])

    for rel in sorted(headers):
        abstract, concepts = headers[rel]
        parts = rel.split("/")
        internal = "detail" in parts[:-1]
        if "concepts" in parts[:-1]:
            other = twin(rel, "concepts", "interfaces")
            if other not in headers:
                errors.append("%s has no virtual twin: expected %s" % (where(rel), where(other)))
            if not concepts:
                errors.append("%s declares no concept" % where(rel))
            for name, (line, found) in sorted(concepts.items()):
                if not in_namespace(found, ns):
                    errors.append("%s:%d: concept %s is in namespace '%s', not in %s"
                                  % (where(rel), line, name, found, ns))
            pairs += 1
            for form in ("concepts", "interfaces"):
                test = "%s/%s_test.cpp" % (tests, twin(rel, "concepts", form)[: -len(".hpp")])
                if not os.path.exists(os.path.join(conf.root, test)):
                    errors.append("%s has no unit test for its %s form: expected %s" % (where(rel), form[:-1], test))
        for name, (line, found) in sorted(abstract.items()):
            if "interfaces" in parts[:-1]:
                other = twin(rel, "interfaces", "concepts")
                if other not in headers:
                    errors.append("%s:%d: interface %s has no concept twin: expected %s"
                                  % (where(rel), line, name, where(other)))
                if not in_namespace(found, ns):
                    errors.append("%s:%d: interface %s is in namespace '%s', not in %s"
                                  % (where(rel), line, name, found, ns))
            elif not internal and name not in exempt and "detail" not in found.split("::"):
                errors.append("%s:%d: class %s has pure virtual functions but no concept twin: declare it in "
                              "interfaces/<capability>.hpp with its concept in concepts/<capability>.hpp"
                              % (where(rel), line, name))

    if errors:
        for e in errors:
            print("%s: %s" % (TOOL, e), file=sys.stderr)
        print("%s: FAILED - every capability is a concept and a virtual twin, each with its test" % TOOL,
              file=sys.stderr)
        return 1
    print("%s: ok - %d capabilit%s, each a concept and a virtual twin with their tests"
          % (TOOL, pairs, "y" if pairs == 1 else "ies"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
