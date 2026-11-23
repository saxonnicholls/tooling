#!/usr/bin/env bash
#
#  fixture_repo.sh
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  Makes the fixture repository (tests/fixtures/good) a git repository of its own at <dir>, with this checkout's
#  tools (cmake/, docker/, make/, scripts/, uncommitted changes included) vendored as third_party/tooling, the way a
#  repository pins tooling. The gate test and tooling's own CI (the library workflow, exercised) start from it.
#
#      tests/fixture_repo.sh <dir>      <dir> must not exist or be empty
#
set -euo pipefail

TOOLING="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${1:?usage: fixture_repo.sh <dir>}"
if [ -e "$dest" ] && [ -n "$(ls -A "$dest")" ]; then
    echo "fixture_repo: $dest is not empty" >&2
    exit 2
fi
mkdir -p "$dest/third_party/tooling"
cp -R "$TOOLING/tests/fixtures/good/." "$dest/"
( cd "$TOOLING" && git ls-files --cached --others --exclude-standard -- cmake docker make scripts |
    while IFS= read -r f; do if [ -f "$f" ]; then printf '%s\n' "$f"; fi; done |
    tar -cf - -T - ) | tar -C "$dest/third_party/tooling" -xf -
git -C "$dest" init -q
git -C "$dest" add -A
