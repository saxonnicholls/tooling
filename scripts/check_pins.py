#!/usr/bin/env python3
#
#  check_pins.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  One version of each library (STANDARDS section 2). A repository reaches a library through its own pin and through
#  the pins of its dependencies, at any depth, and the build compiles one copy: the shallowest, which the top-level
#  project adds first (snicholls_library_begin, cmake/SnichollsOneVersion.cmake). This check reads every pin before
#  anything is built:
#
#      python3 third_party/tooling/scripts/check_pins.py [--root <repository>] [--config <tooling.conf>]
#      python3 third_party/tooling/scripts/check_pins.py --release      # every warning is an error ($RELEASE_TAG too)
#
#  The walk. Every submodule at every depth: .gitmodules and the gitlink in the parent's tree (HEAD at the top, the
#  pinned commit below), into each checked-out submodule. A library is known by its remote URL, normalised (scheme,
#  user, port, case and .git dropped, ssh mapped to its host and path), never by the folder it is checked out in:
#  third_party/ts_moveables in one repository and third_party/ts-moveables in another are one library. A pinned
#  commit is named by the release tag (vX.Y.Z) that points at it, from any checkout of that library, else from
#  git ls-remote --tags <url>.
#
#  The copies of a library: the shallowest is built; deeper ones are shadowed, checked out but never compiled.
#
#  Errors (exit 1):
#    - a built pin that is not a release tag;
#    - two copies at the same depth and none shallower, at different commits: whichever is added first wins;
#    - a consumer that requires more than the built copy is (snicholls_require(<name> <minimum>), or
#      snicholls_<x>_require(<minimum>) for project snicholls_<x>, in its CMake files): configure would fail;
#    - a gitlink with no .gitmodules entry, and a copy of the repository itself (a cycle);
#    - reaching a library other than through a direct pin (every library pins what it uses):
#        * a CMake file or Makefile outside third_party/ whose include(), add_subdirectory(), include_directories(),
#          target_include_directories(), -I or make include names third_party/<x>/third_party/, or a ../ path that
#          leaves the repository;
#        * an #include <snicholls/<x>/...> whose include root is neither the repository's own nor in one of its
#          direct pins' include directories.
#  Warnings (exit 0; errors with --release or $RELEASE_TAG): a shadowed copy at another commit than the built one,
#  a checkout that is not at its pin, a submodule added but not committed, a pin whose tag cannot be found.
#  A requirement that cannot be checked (the built copy is untagged, or not checked out) is skipped, and said so.
#
#  Settings (tooling.conf), each a list, the reason in a comment beside it; pins_ignore.<label> and so on give one
#  entry per line, each with its own reason:
#    pins_ignore            URLs or paths (from the root, e.g. third_party/x/third_party/y) not checked or walked
#    pins_allow_untagged    libraries, by URL or by name (the URL's last part), whose pins may be commits: a
#                           third-party library with no releases; one version is still enforced
#    pins_reach_exempt      files (from the root) or include roots (snicholls/x) exempt from the reach rules
#
#  Exit status 0 when every rule holds, 1 when one does not, 2 on a configuration error, 77 when the root is in no
#  git work tree (the gate's snapshot): nothing to read, and the CTest reports it skipped.
#

import argparse
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True   # nothing written into a consumer's submodule checkout
import tooling_conf  # noqa: E402

TOOL = "check_pins"
SKIPPED = 77
RELEASE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
MAX_DEPTH = 16
SOURCES = (".hpp", ".h", ".hh", ".hxx", ".ipp", ".cpp", ".cc", ".cxx", ".c", ".inl", ".tpp")
PRUNE = {".git", "third_party", "node_modules"}


def git(repo, *args, env=None):
    """git's stdout, or None when it fails."""
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0", **(env or {})))
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def normalise(url):
    """A library's identity from any spelling of its remote: host/path in lower case, no scheme, user, port or .git."""
    u = url.strip()
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*)://(.*)$", u)
    if m:
        u = re.sub(r"^[^@/]*@", "", m.group(2))           # user
        u = re.sub(r"^([^/:]*):\d*(?=/|$)", r"\1", u)      # port
    else:
        m = re.match(r"^(?:[^@/:]+@)?([^/:]{2,}):(?!//)(.+)$", u)   # scp-like ssh: [user@]host:path
        if m:
            u = m.group(1) + "/" + m.group(2).lstrip("/")
    u = re.sub(r"/+", "/", u).rstrip("/")
    if u.lower().endswith(".git"):
        u = u[:-4].rstrip("/")
    return u.lower()


def resolve_url(url, base):
    """A .gitmodules URL, relative ones (./x, ../x) resolved against the parent's identity."""
    if not (url.startswith("./") or url.startswith("../")):
        return normalise(url)
    parts = normalise(base).split("/")
    for seg in url.split("/"):
        if seg == "..":
            parts = parts[:-1]
        elif seg and seg != ".":
            parts.append(seg)
    return normalise("/".join(parts))


def name_of(identity):
    return identity.rsplit("/", 1)[-1]


def version_key(tag):
    m = RELEASE.match(tag or "")
    return tuple(int(g) for g in m.groups()) if m else None


class Copy:
    def __init__(self, path, depth, identity, sha, checkout, parent, url):
        self.path, self.depth, self.identity, self.sha, self.url = path, depth, identity, sha, url
        self.checkout = checkout   # its absolute directory, if checked out
        self.parent = parent       # the consumer's directory, absolute
        self.tag = None            # the release tag at sha, if found
        self.resolved = False      # whether "no tag" is known rather than guessed

    @property
    def label(self):
        return self.tag or self.sha[:9]


class Walk:
    def __init__(self, top, conf):
        self.top = top
        self.copies = []
        self.errors, self.warnings, self.notes = [], [], []
        self.ignore = entries(conf, "pins_ignore")
        self.ignore_used = set()
        origin = git(top, "config", "--get", "remote.origin.url")
        self.self_id = normalise(origin.strip()) if origin and origin.strip() else None

    def ignored(self, path, identity):
        for e in self.ignore:
            if e.rstrip("/") == path or normalise(e) == identity:
                self.ignore_used.add(e)
                return True
        return False

    def modules(self, repo, rev):
        """{path: url} from .gitmodules in rev (or the working tree's at the top when rev has none yet)."""
        out = git(repo, "config", "--blob", "%s:.gitmodules" % rev, "--get-regexp", r"^submodule\..*\.(path|url)$")
        if out is None:
            return {}
        by_name = {}
        for line in out.splitlines():
            key, _, value = line.partition(" ")
            name, _, field = key[len("submodule."):].rpartition(".")
            by_name.setdefault(name, {})[field] = value.strip()
        mods = {}
        for name, f in by_name.items():
            if "path" not in f or "url" not in f:
                raise tooling_conf.ConfigError("%s: submodule %s in .gitmodules has no %s"
                                               % (repo, name, "path" if "path" not in f else "url"))
            mods[f["path"].strip("/")] = f["url"]
        return mods

    @staticmethod
    def gitlinks(repo, rev):
        out = git(repo, "ls-tree", "-r", "-z", rev)
        links = {}
        for entry in (out or "").split("\0"):
            meta, _, path = entry.partition("\t")
            fields = meta.split()
            if len(fields) == 3 and fields[0] == "160000":
                links[path] = fields[2]
        return links

    def walk(self, repo, rev, prefix, depth, base, chain):
        mods = self.modules(repo, rev)
        links = self.gitlinks(repo, rev)
        if depth == 1:
            staged = {}
            for line in (git(repo, "ls-files", "-s", "-z") or "").split("\0"):
                meta, _, path = line.partition("\t")
                if meta.startswith("160000 "):
                    staged[path] = meta.split()[1]
            for path in sorted(set(staged) - set(links)):
                self.warnings.append("%s is added but not committed: nothing is pinned there yet" % path)
        for path in sorted(set(links) - set(mods)):
            self.errors.append("%s%s is a submodule with no .gitmodules entry: its library cannot be known"
                               % (prefix, path))
        for path, url in sorted(mods.items()):
            where = prefix + path
            if path not in links:
                if depth > 1 or not os.path.exists(os.path.join(repo, path, ".git")):
                    self.warnings.append(".gitmodules names %s, but no submodule is committed there" % where)
                continue
            identity = resolve_url(url, base)
            if self.ignored(where, identity):
                continue
            abs_path = os.path.join(repo, path)
            checkout = abs_path if os.path.exists(os.path.join(abs_path, ".git")) else None
            copy = Copy(where, depth, identity, links[path], checkout, repo, url)
            if identity == self.self_id or identity in chain:
                self.errors.append("%s: %s is a copy of %s, which pins it: the pins form a cycle"
                                   % (name_of(identity), where, "this repository" if identity == self.self_id
                                      else "a library above it"))
                continue
            self.copies.append(copy)
            if not checkout:
                continue
            head = (git(checkout, "rev-parse", "HEAD") or "").strip()
            if head != copy.sha:
                self.warnings.append("%s is checked out at %s but pinned at %s: git submodule update --recursive"
                                     % (where, head[:9] or "nothing", copy.sha[:9]))
            if depth >= MAX_DEPTH:
                self.errors.append("%s: the submodules nest deeper than %d" % (where, MAX_DEPTH))
                continue
            if git(checkout, "cat-file", "-e", copy.sha + "^{commit}") is None:
                self.warnings.append("%s: the pinned commit %s is not in its checkout, so its own pins are not read"
                                     % (where, copy.sha[:9]))
                continue
            self.walk(checkout, copy.sha, where + "/", depth + 1, identity, chain | {identity})


def entries(conf, key):
    values = conf.list(key)
    for label_value in conf.prefixed(key).values():
        values += label_value.split()
    return values


class Tags:
    """The release tag at a commit, from any checkout of the library, else from its remote."""

    def __init__(self, copies, offline):
        self.checkouts = {}
        for c in copies:
            if c.checkout:
                self.checkouts.setdefault(c.identity, []).append(c.checkout)
        self.remote = {}
        self.offline = offline

    def local(self, identity, sha):
        tags, full = [], False
        for checkout in self.checkouts.get(identity, []):
            tags += (git(checkout, "tag", "--points-at", sha) or "").split()
            full = full or (git(checkout, "rev-parse", "--is-shallow-repository") or "").strip() == "false"
        return tags, full

    def ls_remote(self, identity, urls):
        """{sha: [tags]} from the first of urls that answers, or None when none does (or offline)."""
        if identity not in self.remote:
            refs = None
            for url in ([] if self.offline else urls):
                out = git(self.checkouts.get(identity, ["."])[0], "ls-remote", "--tags", url)
                if out is not None:
                    refs = {}
                    for line in out.splitlines():
                        sha, _, ref = line.partition("\t")
                        refs.setdefault(sha, []).append(ref[len("refs/tags/"):].removesuffix("^{}"))
                    break
            self.remote[identity] = refs
        return self.remote[identity]

    def resolve(self, copy, urls):
        tags, full = self.local(copy.identity, copy.sha)
        releases = sorted({t for t in tags if RELEASE.match(t)}, key=version_key)
        if releases:
            copy.tag, copy.resolved = releases[-1], True
            return
        refs = self.ls_remote(copy.identity, urls)
        if refs is not None:
            releases = sorted({t for t in refs.get(copy.sha, []) if RELEASE.match(t)}, key=version_key)
            copy.tag = releases[-1] if releases else None
            copy.resolved = True
            return
        copy.resolved = full   # a full clone has every tag it was fetched with; a shallow one may not


def cmake_names(checkout):
    """What a library calls itself in CMake: snicholls_library_begin(<name> ...) and project(<name> ...)."""
    path = os.path.join(checkout, "CMakeLists.txt")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8", errors="replace") as f:
        text = re.sub(r"#[^\n]*", "", f.read())
    names = set(re.findall(r"\bsnicholls_library_begin\s*\(\s*([A-Za-z0-9_.+-]+)", text))
    names |= set(re.findall(r"\bproject\s*\(\s*([A-Za-z0-9_.+-]+)", text, re.I))
    return names


def cmake_files(repo, makefiles=False, prune=()):
    for d, dirs, files in os.walk(repo):
        dirs[:] = sorted(x for x in dirs if x not in PRUNE and x not in prune and not x.startswith("build"))
        for f in sorted(files):
            if f == "CMakeLists.txt" or f.endswith(".cmake") or (makefiles and (f in ("Makefile", "GNUmakefile")
                                                                               or f.endswith(".mk"))):
                yield os.path.join(d, f)


def requirements(repo):
    """(file, name, minimum) for each snicholls_require in a consumer's own CMake files, its tests' fixtures not."""
    found = []
    for path in cmake_files(repo, prune=("tests", "test", "fixtures")):
        with open(path, encoding="utf-8", errors="replace") as f:
            text = re.sub(r"#[^\n]*", "", f.read())
        rel = os.path.relpath(path, repo)
        for name, minimum in re.findall(r"\bsnicholls_require\s*\(\s*([A-Za-z0-9_.+-]+)\s+v?(\d+\.\d+\.\d+)\s*\)", text):
            found.append((rel, name, minimum))
        for lib, minimum in re.findall(r"\bsnicholls_([a-z0-9_]+?)_require\s*\(\s*v?(\d+\.\d+\.\d+)\s*\)", text):
            found.append((rel, "snicholls_" + lib, minimum))
    return found


def check_requirements(walk, built):
    """built: {identity: [built copies]}. A consumer that needs more than the built copy fails configure."""
    names = {}
    for c in walk.copies:
        if c.checkout:
            for n in cmake_names(c.checkout):
                names.setdefault(n, c.identity)
    consumers = [(walk.top, "this repository")] + [(c.checkout, c.path) for c in walk.copies if c.checkout]
    seen = set()
    for repo, who in consumers:
        for rel, name, minimum in requirements(repo):
            identity = names.get(name)
            if identity is None or identity not in built or (who, name) in seen:
                continue
            seen.add((who, name))
            copy = built[identity][0]
            where = rel if who == "this repository" else "%s/%s" % (who, rel)
            if version_key(copy.tag) is None:
                walk.notes.append("%s needs %s %s (%s): not checked, the built copy %s is not a release tag"
                                  % (who, name, minimum, where, copy.path))
            elif version_key(copy.tag) < version_key(minimum):
                walk.errors.append("%s: %s needs %s or newer (%s), but the built copy, %s, is %s: configure would "
                                   "fail. Bump the top-level pin" % (name_of(identity), who, minimum, where,
                                                                     copy.path, copy.tag))


def check_libraries(walk, conf, release, offline):
    allow = entries(conf, "pins_allow_untagged")
    allow_ids = {normalise(a) for a in allow} | set(allow)
    tags = Tags(walk.copies, offline)
    by_id = {}
    for c in walk.copies:
        by_id.setdefault(c.identity, []).append(c)
    remotes = remote_urls(walk)
    for c in walk.copies:
        tags.resolve(c, remotes[c.identity])
    built = {}
    for identity, copies in sorted(by_id.items()):
        name = name_of(identity)
        untagged_ok = identity in allow_ids or name in allow_ids
        depth = min(c.depth for c in copies)
        top = sorted((c for c in copies if c.depth == depth), key=lambda c: c.path)
        built[identity] = top
        if len({c.sha for c in top}) > 1:
            walk.errors.append("%s: %d copies at depth %d and none shallower, at different commits (%s): whichever "
                               "is added first wins. Pin %s in this repository's own third_party/"
                               % (name, len(top), depth, ", ".join("%s %s" % (c.path, c.label) for c in top), name))
        for c in top:
            if c.tag or untagged_ok:
                continue
            if c.resolved:
                walk.errors.append("%s: %s is pinned at %s, which is not a release tag (pin a vX.Y.Z tag, or list "
                                   "it in pins_allow_untagged with the reason)" % (name, c.path, c.sha[:9]))
            else:
                walk.warnings.append("%s: cannot tell whether %s's pin %s is a release tag: a shallow checkout "
                                     "without its tags, and git ls-remote failed; fetch its tags" % (name, c.path,
                                                                                                    c.sha[:9]))
        built_shas = {c.sha for c in top}
        for c in sorted(copies, key=lambda c: (c.depth, c.path)):
            if c.depth > depth and c.sha not in built_shas:
                walk.warnings.append("%s: %s is pinned at %s but shadowed by %s at %s, which is what the build "
                                     "compiles: bump it to one version%s"
                                     % (name, c.path, c.label, top[0].path, top[0].label,
                                        "" if release else " before the release"))
    for e in walk.ignore:
        if e not in walk.ignore_used:
            walk.warnings.append("pins_ignore: %s matches no submodule" % e)
    return built


def remote_urls(walk):
    """The URLs git may reach each library at: the .gitmodules spellings, each checkout's origin, https."""
    out = {}
    for c in walk.copies:
        urls = out.setdefault(c.identity, [])
        origin = (git(c.checkout, "config", "--get", "remote.origin.url") or "").strip() if c.checkout else ""
        for url in (c.url, origin):
            if url and not url.startswith(".") and url not in urls:
                urls.append(url)
    for identity, urls in out.items():
        if not identity.startswith("/"):
            urls.append("https://" + identity)
    return out


# The reach rules: every library it uses, the repository pins itself

def strip_cmake_comments(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|#[^\n]*', lambda m: m.group(0) if m.group(0).startswith('"') else "", text)


CMAKE_PATH_COMMANDS = re.compile(
    r"\b(include|add_subdirectory|include_directories|target_include_directories)\s*\(([^)]*)\)", re.I | re.S)
NESTED = re.compile(r"third_party/[^/\s\"')]+/third_party/")
VARS_AT_REPO = re.compile(r"^\$\{(CMAKE_SOURCE_DIR|PROJECT_SOURCE_DIR|CMAKE_CURRENT_SOURCE_DIR|"
                          r"CMAKE_CURRENT_LIST_DIR)\}/?")


def leaves(token, here, root):
    """Whether a path written in a file in directory here climbs out of the repository at root."""
    if "../" not in token and not token.endswith(".."):
        return False
    m = VARS_AT_REPO.match(token)
    if m:
        base = root if m.group(1) in ("CMAKE_SOURCE_DIR", "PROJECT_SOURCE_DIR") else here
        token = token[m.end():]
    elif "${" in token.split("../")[0] or token.startswith("/") or token.startswith("$"):
        return False
    else:
        base = here
    full = os.path.normpath(os.path.join(base, token))
    return os.path.relpath(full, root).split(os.sep)[0] == ".."


def reach_in_build_files(root, exempt, problems):
    for path in cmake_files(root, makefiles=True):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if rel in exempt:
            continue
        here = os.path.dirname(path)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if path.endswith((".txt", ".cmake")):
            code = strip_cmake_comments(text)
            for m in CMAKE_PATH_COMMANDS.finditer(code):
                line = code.count("\n", 0, m.start()) + 1
                for token in re.findall(r'"[^"]*"|[^\s"]+', m.group(2)):
                    token = token.strip('"')
                    check_token(token, m.group(1), rel, line, here, root, problems)
        else:
            for n, raw in enumerate(text.splitlines(), 1):
                line = re.sub(r"(^|\s)#.*$", "", raw)
                for token in re.findall(r"-I\s*(\S+)", line):
                    check_token(token, "-I", rel, n, root, root, problems)
                m = re.match(r"^\s*-?include\s+(.+)$", line)
                if m:
                    for token in m.group(1).split():
                        check_token(token, "include", rel, n, root, root, problems)


def check_token(token, command, rel, line, here, root, problems):
    if NESTED.search(token):
        problems.append("%s:%d: %s %s reaches into another library's third_party/: pin it in this repository's "
                        "own third_party/" % (rel, line, command, token))
    elif leaves(token, here, root):
        problems.append("%s:%d: %s %s reaches out of the repository: pin it in this repository's own third_party/"
                        % (rel, line, command, token))


def include_roots(checkout):
    """The snicholls/<x> roots a checkout's include directory holds: its tooling.conf include_dir, else include."""
    inc = "include"
    try:
        inc = tooling_conf.load(checkout).include_dir()
    except tooling_conf.ConfigError:
        pass
    base = os.path.join(checkout, inc, "snicholls")
    if not os.path.isdir(base):
        return set()
    return {"snicholls/" + d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))}


def reach_in_includes(root, conf, direct, deeper, exempt, problems, notes):
    own = include_roots(root) if os.path.isdir(os.path.join(root, conf.include_dir())) else set()
    provided, unknown = set(own), [c.path for c in direct if not c.checkout]
    for c in direct:
        if c.checkout:
            provided |= include_roots(c.checkout)
    through = {}
    for c in deeper:
        if c.checkout:
            for r in include_roots(c.checkout):
                through.setdefault(r, c.path)
    if unknown:
        notes.append("the #include rule is checked without %s, which is not checked out" % ", ".join(unknown))
    pattern = re.compile(r'^\s*#\s*include\s*[<"](snicholls/[A-Za-z0-9_.-]+)/[^>"]+[>"]', re.M)
    reported = set()
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in PRUNE and not x.startswith("build"))
        for f in sorted(files):
            if not f.endswith(SOURCES):
                continue
            path = os.path.join(d, f)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if rel in exempt:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            for m in pattern.finditer(text):
                inc = m.group(1)
                if inc in provided or inc in exempt or unknown and inc not in through or (rel, inc) in reported:
                    continue
                reported.add((rel, inc))
                line = text.count("\n", 0, m.start()) + 1
                how = ("it is reached only through %s" % through[inc]) if inc in through else "no pin provides it"
                problems.append("%s:%d: #include <%s/...> needs a direct pin of the library that provides %s, and %s"
                                % (rel, line, inc, inc, how))


def main():
    ap = argparse.ArgumentParser(description="Check that every library is pinned at one release, reached directly")
    tooling_conf.add_arguments(ap)
    ap.add_argument("--release", action="store_true", default=bool(os.environ.get("RELEASE_TAG")),
                    help="a release: every warning is an error (default: when $RELEASE_TAG is set)")
    ap.add_argument("--offline", action="store_true", help="never ask a remote for its tags")
    args = ap.parse_args()
    conf = tooling_conf.load_or_exit(args, TOOL)
    top = git(conf.root, "rev-parse", "--show-toplevel")
    if top is None:
        print("%s: skipped - %s is in no git work tree, so there are no pins to read" % (TOOL, conf.root))
        return SKIPPED
    top = os.path.realpath(top.strip())
    walk = Walk(top, conf)
    try:
        if git(top, "rev-parse", "--verify", "-q", "HEAD") is not None:
            walk.walk(top, "HEAD", "", 1, walk.self_id or top, frozenset())
        built = check_libraries(walk, conf, args.release, args.offline)
        check_requirements(walk, built)
        exempt = set(entries(conf, "pins_reach_exempt"))
        reach = []
        reach_in_build_files(conf.root, exempt, reach)
        direct = [c for c in walk.copies if c.depth == 1]
        deeper = [c for c in walk.copies if c.depth > 1]
        reach_in_includes(conf.root, conf, direct, deeper, exempt, reach, walk.notes)
        walk.errors += reach
    except tooling_conf.ConfigError as e:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
        return 2

    if walk.copies:
        rows = sorted(walk.copies, key=lambda c: (name_of(c.identity), c.depth, c.path))
        built_paths = {c.path for cs in built.values() for c in cs}
        width = max(len(c.path) for c in rows)
        for c in rows:
            print("  %-*s  %-12s %s" % (width, c.path, c.label, "built" if c.path in built_paths else "shadowed"),
                  flush=True)
    for n in walk.notes:
        print("%s: note: %s" % (TOOL, n))
    errors = walk.errors + (walk.warnings if args.release else [])
    for w in ([] if args.release else walk.warnings):
        print("%s: warning: %s" % (TOOL, w), file=sys.stderr)
    for e in errors:
        print("%s: %s" % (TOOL, e), file=sys.stderr)
    if errors:
        print("%s: FAILED - one version of each library, each pinned where it is used%s"
              % (TOOL, " (a release: warnings are errors)" if args.release and walk.warnings else ""),
              file=sys.stderr)
        return 1
    n, w = len(built), len(walk.warnings)
    print("%s: ok - %d %s, one version of each in the build%s" % (
        TOOL, n, "library" if n == 1 else "libraries", "" if not w else ", %d warning%s" % (w, "" if w == 1 else "s")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
