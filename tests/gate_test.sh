#!/usr/bin/env bash
#
#  gate_test.sh
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  Runs scripts/test_ubuntu.sh for real, in Docker, against the fixture repository (tests/fixtures/good), built as a
#  git repository that pins this checkout as third_party/tooling (tests/fixture_repo.sh):
#
#    1. the fixture passes every configuration, and the run says so and exits 0;
#    2. --quick runs exactly one configuration;
#    3. with undefined behaviour planted in a test, exactly the three ASan+UBSan configurations fail, the others
#       still pass, and the run names the failures and exits 1;
#    4. an untracked file is not in the snapshot: an untracked broken test changes nothing;
#    5. the derived image: gcc-debug runs in the fixture's own image (docker/ci), whose marker its image.derived
#       CTest finds; the image is built once and reused, and rebuilt under a new tag when its Dockerfile changes;
#       without the image the same CTest fails.
#
#      tests/gate_test.sh            all five (the full gate, twice: some minutes)
#      tests/gate_test.sh --quick    2, 4 and 5 without its failing half
#
set -euo pipefail

TOOLING="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUICK=0
[ "${1:-}" = --quick ] && QUICK=1
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
failures=0

fixture() { "$TOOLING/tests/fixture_repo.sh" "$1"; }

expect() {   # expect <description> <command...>: counts a failure instead of stopping
    if "${@:2}"; then echo "gate_test: ok - $1"; else echo "gate_test: FAILED - $1" >&2; failures=$((failures + 1)); fi
}

gate() {   # gate <repo> <args...>: runs the gate, keeps its report and status
    set +e
    "$TOOLING/scripts/test_ubuntu.sh" --repo "$@" > "$WORK/report" 2>&1
    status=$?
    set -e
    cat "$WORK/report"
}

fixture "$WORK/quick"
gate "$WORK/quick" --quick
expect "--quick passes, exit 0" test "$status" = 0
expect "--quick runs one configuration" grep -q '^test_ubuntu: all 1 configurations passed$' "$WORK/report"

# An untracked file never reaches the container: had it, the check.mirror CTest would fail on a test with no header
printf 'int main() { return 1; }\n' > "$WORK/quick/tests/untracked_test.cpp"
gate "$WORK/quick" --quick
expect "untracked files are not tested" test "$status" = 0

# The derived image: gcc-debug names docker/ci/Dockerfile, and its image.derived CTest needs the image's marker
gate "$WORK/quick" --only gcc-debug
expect "the configuration in the derived image passes" test "$status" = 0
first="$("$TOOLING/scripts/build_image.sh" ubuntu-24.04 "$WORK/quick/docker/ci/Dockerfile")"
again="$("$TOOLING/scripts/build_image.sh" ubuntu-24.04 "$WORK/quick/docker/ci/Dockerfile")"
expect "the derived image is tagged snicholls-ubuntu-24.04-derived:<hash>" \
    grep -qE '^snicholls-ubuntu-24\.04-derived:[0-9a-f]{12}$' <<< "$first"
expect "an unchanged derived image is reused" test "$first" = "$again"
echo 'RUN true' >> "$WORK/quick/docker/ci/Dockerfile"
changed="$("$TOOLING/scripts/build_image.sh" ubuntu-24.04 "$WORK/quick/docker/ci/Dockerfile")"
expect "an edited Dockerfile is a new image" test "$first" != "$changed"
docker image rm -f "$changed" >/dev/null

if [ "$QUICK" = 0 ]; then
    fixture "$WORK/good"
    gate "$WORK/good"
    expect "the fixture passes, exit 0" test "$status" = 0
    expect "all eight configurations ran and passed" grep -q '^test_ubuntu: all 8 configurations passed$' "$WORK/report"
    expect "the documentation was built in gcc Release" grep -q 'doxygen' "$WORK/report"

    fixture "$WORK/ub"
    cat > "$WORK/ub/tests/widget_test.cpp" <<'CPP'
#include <snicholls/fixture/widget.hpp>

#include <climits>

int main(int argc, char**)
{
    volatile int big = INT_MAX;
    const int wrapped = big + argc;   // signed overflow: undefined behaviour, which only UBSan reports
    return snicholls::widget(argc) == 3 && wrapped != 0 ? 0 : 1;
}
CPP
    git -C "$WORK/ub" add -A
    gate "$WORK/ub"
    expect "undefined behaviour fails the gate, exit 1" test "$status" = 1
    expect "exactly the sanitizer configurations fail" grep -q \
        '^test_ubuntu: 3 of 8 configurations FAILED: clang ASan+UBSan, gcc ASan+UBSan, gcc15 ASan+UBSan$' "$WORK/report"
    expect "the report quotes UBSan" grep -q 'runtime error' "$WORK/report"

    fixture "$WORK/plain"
    sed -i.bak '/^image\.gcc-debug/d' "$WORK/plain/tooling.conf" && rm "$WORK/plain/tooling.conf.bak"
    git -C "$WORK/plain" add -A
    gate "$WORK/plain" --only gcc-debug
    expect "without the derived image, its CTest fails" test "$status" = 1
    expect "... and it is the image.derived CTest" grep -q 'image.derived' "$WORK/report"
fi

if [ "$failures" -gt 0 ]; then
    echo "gate_test: $failures expectation(s) FAILED" >&2
    exit 1
fi
echo "gate_test: passed"
