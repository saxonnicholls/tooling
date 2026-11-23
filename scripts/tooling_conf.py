#
#  tooling_conf.py
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  Reads a repository's tooling.conf, the one file that parameterises every tool here (README "tooling.conf").
#  The format is deliberately flat, so that bash, CMake and Python read it the same way:
#
#      key = value          one setting per line; the value runs to the end of the line
#      # a comment          '#' at the start of a line or after whitespace starts a comment
#
#  Lists are whitespace-separated, flags are yes/no (on/off, true/false, 1/0). A key appears at most once.
#
#  From the command line, for make and the workflows (exit 2 on a configuration error):
#
#      python3 tooling_conf.py [--root <dir>] [--config <file>] get <key> [<default>]   the value; 1 if absent
#      python3 tooling_conf.py [--root <dir>] [--config <file>] flag <key> <default>    yes or no
#

import argparse
import os
import re
import sys

_LINE = re.compile(r"^\s*([A-Za-z0-9_.+-]+)\s*=\s*(.*?)\s*$")
_COMMENT = re.compile(r"(^|\s)#.*$")


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, root, values, path):
        self.root = root
        self.path = path
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)

    def require(self, key):
        value = self.values.get(key)
        if not value:
            raise ConfigError("%s: '%s' is required" % (self.path, key))
        return value

    def list(self, key, default=""):
        return self.values.get(key, default).split()

    def flag(self, key, default):
        value = self.values.get(key)
        if value is None:
            return default
        low = value.lower()
        if low in ("yes", "on", "true", "1"):
            return True
        if low in ("no", "off", "false", "0"):
            return False
        raise ConfigError("%s: '%s' must be yes or no, not '%s'" % (self.path, key, value))

    def prefixed(self, prefix):
        """Every key prefix.<label>, as {label: value}, in file order."""
        return {k[len(prefix) + 1:]: v for k, v in self.values.items() if k.startswith(prefix + ".")}

    def include_dir(self):
        return self.get("include_dir", "include")

    def include_root(self):
        """The public headers' directory, relative to the repository root, e.g. include/snicholls/core."""
        root = self.require("include_root").rstrip("/")
        inc = self.include_dir().rstrip("/")
        if root != inc and not root.startswith(inc + "/"):
            raise ConfigError("%s: include_root %s is not under include_dir %s" % (self.path, root, inc))
        return root


def parse(text, path="tooling.conf"):
    values = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = _COMMENT.sub("", raw)
        if not line.strip():
            continue
        m = _LINE.match(line)
        if not m:
            raise ConfigError("%s:%d: expected 'key = value', got: %s" % (path, n, raw.strip()))
        key, value = m.group(1), m.group(2)
        if key in values:
            raise ConfigError("%s:%d: '%s' is set twice" % (path, n, key))
        values[key] = value
    return values


def load(root=None, config=None):
    """The configuration of the repository at root (default: the current directory)."""
    root = os.path.abspath(root or os.getcwd())
    path = os.path.abspath(config) if config else os.path.join(root, "tooling.conf")
    if not os.path.exists(path):
        raise ConfigError("no %s: every repository that uses tooling has one (see tooling's README)" % path)
    with open(path, encoding="utf-8") as f:
        return Config(root, parse(f.read(), path), path)


def add_arguments(parser):
    parser.add_argument("--root", help="the repository to check (default: the current directory)")
    parser.add_argument("--config", help="its tooling.conf (default: <root>/tooling.conf)")


def load_or_exit(args, tool):
    try:
        return load(args.root, args.config)
    except ConfigError as e:
        print("%s: %s" % (tool, e), file=sys.stderr)
        sys.exit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reads one setting of a repository's tooling.conf.")
    add_arguments(parser)
    parser.add_argument("command", choices=("get", "flag"))
    parser.add_argument("key")
    parser.add_argument("default", nargs="?")
    args = parser.parse_args(argv)
    config = load_or_exit(args, "tooling_conf")
    try:
        if args.command == "flag":
            if args.default is None:
                parser.error("flag needs a default, yes or no")
            default = Config(None, {"default": args.default}, "the default").flag("default", None)
            print("yes" if config.flag(args.key, default) else "no")
            return 0
    except ConfigError as e:
        print("tooling_conf: %s" % e, file=sys.stderr)
        return 2
    value = config.get(args.key, args.default)
    if value is None:
        print("tooling_conf: %s sets no %s" % (config.path, args.key), file=sys.stderr)
        return 1
    print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
