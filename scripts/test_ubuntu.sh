#!/usr/bin/env bash
#
#  test_ubuntu.sh
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  The Ubuntu half of a repository's local gate (STANDARDS section 5): its full CTest suite in tooling's build
#  images, from any machine with Docker. Run from the repository's root:
#
#      third_party/tooling/scripts/test_ubuntu.sh             every configuration
#      third_party/tooling/scripts/test_ubuntu.sh --quick     gcc-release only
#      third_party/tooling/scripts/test_ubuntu.sh --only clang-asan,gcc15-asan
#      third_party/tooling/scripts/test_ubuntu.sh -j 4        at most 4 compiles and tests at once, on 4 CPUs
#      third_party/tooling/scripts/test_ubuntu.sh --plan      print the configurations and stop (no Docker)
#      third_party/tooling/scripts/test_ubuntu.sh --repo <dir>   a repository other than the current one
#
#  Configurations, each a fresh CMake build of everything with -D<option_prefix>WERROR=ON, then every CTest:
#
#      gcc-release     GCC 13     Release        + benchmark smoke runs + documentation   ubuntu-24.04
#      gcc-debug       GCC 13     Debug                                                   ubuntu-24.04
#      clang-release   Clang 18   Release                                                 ubuntu-24.04
#      clang-debug     Clang 18   Debug                                                   ubuntu-24.04
#      clang-asan      Clang 18   ASan+UBSan                                              ubuntu-24.04
#      gcc-asan        GCC 13     ASan+UBSan                                              ubuntu-24.04
#      gcc15-release   GCC 15     Release        + benchmark smoke runs                   ubuntu-26.04
#      gcc15-asan      GCC 15     ASan+UBSan                                              ubuntu-26.04
#
#  The repository's tooling.conf says how (README "tooling.conf"):
#
#      name           = snicholls-core        the name in the report
#      option_prefix  = SNICHOLLS_CORE_       <prefix>WERROR, <prefix>SANITIZE, <prefix>BUILD_DOCS, <prefix>BUILD_BENCHMARKS
#      docs           = yes                   <prefix>BUILD_DOCS=ON in gcc-release (skipped where Doxygen is older
#                                             than 1.18: the ARM64 image)
#      benchmarks     = yes                   <prefix>BUILD_BENCHMARKS=ON in gcc-release and gcc15-release
#      configurations = gcc-release ...       a subset of the eight (default: all)
#      cmake          = -DFOO=ON              more CMake arguments for every configuration
#      cmake.<config> = -DBAR=ON              ... for one configuration
#      extra.<label>  = <image> <cmake args>  a configuration of the repository's own, e.g.
#                                             extra.clang-tsan = ubuntu-24.04 -DCMAKE_CXX_COMPILER=clang++ ...
#      env            = KEY=value ...         environment for the builds and tests
#      setup          = <shell command>       run in each container before the configurations
#
#  Arguments in these lists are separated by whitespace and are not quoted. UBSan halts on its first report
#  (UBSAN_OPTIONS=halt_on_error=1), so undefined behaviour fails the test that hit it; `env` can override that.
#
#  The tracked files (`git ls-files` plus every submodule's) are packed into one tarball before any container
#  starts; it is mounted read-only and unpacked in each container. Nothing untracked is tested, nothing is written
#  back, and an edit made while the gate runs reaches no configuration. Every configuration runs; the exit status is
#  1 if any failed, 2 on a usage or configuration error.
#

set -euo pipefail

TOOLING="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO=""
QUICK=0
PLAN=0
ONLY=""
JOBS=""

usage() { awk 'NR > 7 && /^#/ { sub(/^# ?/, ""); print; next } NR > 7 { exit }' "${BASH_SOURCE[0]}"; }
die() { echo "test_ubuntu: $*" >&2; exit 2; }

while [ $# -gt 0 ]; do
    case "$1" in
        --quick) QUICK=1 ;;
        --plan) PLAN=1 ;;
        --only) shift; ONLY="${1:-}"; [ -n "$ONLY" ] || die "--only needs configuration names" ;;
        --only=*) ONLY="${1#--only=}" ;;
        --repo) shift; REPO="${1:-}"; [ -n "$REPO" ] || die "--repo needs a directory" ;;
        --repo=*) REPO="${1#--repo=}" ;;
        -j) shift; JOBS="${1:-}" ;;
        -j*) JOBS="${1#-j}" ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown argument $1 (--help lists them)" ;;
    esac
    shift
done
set -f   # the lists below are split on whitespace, never globbed
case "$JOBS" in
    "") ;;
    *[!0-9]*|0) die "-j needs a positive number" ;;
esac

if [ -z "$REPO" ]; then
    REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not in a git repository: run from the repository's root or pass --repo"
fi
REPO="$(cd "$REPO" && pwd)"
CONF="$REPO/tooling.conf"
[ -f "$CONF" ] || die "no $CONF: every repository that uses tooling has one (tooling's README)"

# conf <key> [default]: the value of <key> in tooling.conf (the format: scripts/tooling_conf.py)
conf() {
    local value
    if value="$(awk -v key="$1" '
        { line = $0; sub(/(^|[ \t])#.*$/, "", line) }
        line ~ /^[ \t]*[A-Za-z0-9_.+-]+[ \t]*=/ {
            k = line; sub(/[ \t]*=.*$/, "", k); sub(/^[ \t]+/, "", k)
            if (k == key) { v = line; sub(/^[^=]*=[ \t]*/, "", v); sub(/[ \t]+$/, "", v); print v; found = 1; exit }
        }
        END { exit !found }' "$CONF")"; then
        printf '%s\n' "$value"
    else
        printf '%s\n' "${2-}"
    fi
}
# conf_labels <prefix>: the <label> of every <prefix>.<label> key, in file order
conf_labels() {
    awk -v prefix="$1." '
        { line = $0; sub(/(^|[ \t])#.*$/, "", line) }
        line ~ /^[ \t]*[A-Za-z0-9_.+-]+[ \t]*=/ {
            k = line; sub(/[ \t]*=.*$/, "", k); sub(/^[ \t]+/, "", k)
            if (index(k, prefix) == 1) print substr(k, length(prefix) + 1)
        }' "$CONF"
}
flag() {   # flag <key> <default>: 1 or 0
    case "$(conf "$1" "$2" | tr '[:upper:]' '[:lower:]')" in
        yes|on|true|1) echo 1 ;;
        no|off|false|0) echo 0 ;;
        *) die "tooling.conf: $1 must be yes or no" ;;
    esac
}

NAME="$(conf name "$(basename "$REPO")")"
P="$(conf option_prefix)"
[ -n "$P" ] || die "tooling.conf sets no option_prefix (e.g. SNICHOLLS_CORE_ for -DSNICHOLLS_CORE_WERROR=ON)"
DOCS="$(flag docs no)"
BENCH="$(flag benchmarks no)"

words() {   # words <text>: its words, one space apart
    # shellcheck disable=SC2086  # split on purpose; globbing is off
    set -- $1
    echo "$*"
}

# The eight standard configurations: name, image, label, CMake arguments
STANDARD="gcc-release gcc-debug clang-release clang-debug clang-asan gcc-asan gcc15-release gcc15-asan"
SAN="-DCMAKE_BUILD_TYPE=RelWithDebInfo -D${P}SANITIZE=address,undefined"
GCC15="-DCMAKE_C_COMPILER=gcc-15 -DCMAKE_CXX_COMPILER=g++-15"
BENCH_ON=""; [ "$BENCH" = 1 ] && BENCH_ON="-D${P}BUILD_BENCHMARKS=ON"
standard() {   # standard <name>: "image|label|args"
    case "$1" in
        gcc-release)   echo "ubuntu-24.04|gcc Release|-DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Release $BENCH_ON" ;;
        gcc-debug)     echo "ubuntu-24.04|gcc Debug|-DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Debug" ;;
        clang-release) echo "ubuntu-24.04|clang Release|-DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Release" ;;
        clang-debug)   echo "ubuntu-24.04|clang Debug|-DCMAKE_CXX_COMPILER=clang++ -DCMAKE_BUILD_TYPE=Debug" ;;
        clang-asan)    echo "ubuntu-24.04|clang ASan+UBSan|-DCMAKE_CXX_COMPILER=clang++ $SAN" ;;
        gcc-asan)      echo "ubuntu-24.04|gcc ASan+UBSan|-DCMAKE_CXX_COMPILER=g++ $SAN" ;;
        gcc15-release) echo "ubuntu-26.04|gcc15 Release|$GCC15 -DCMAKE_BUILD_TYPE=Release $BENCH_ON" ;;
        gcc15-asan)    echo "ubuntu-26.04|gcc15 ASan+UBSan|$GCC15 $SAN" ;;
        *) return 1 ;;
    esac
}

CONFIGURED="$(conf configurations "$STANDARD")"
for c in $CONFIGURED; do standard "$c" >/dev/null || die "tooling.conf: unknown configuration '$c' (have: $STANDARD)"; done
EXTRAS="$(conf_labels extra)"
for e in $EXTRAS; do
    case " $STANDARD " in *" $e "*) die "tooling.conf: extra.$e has the name of a standard configuration" ;; esac
    img="$(conf "extra.$e" | awk '{print $1}')"
    [ -f "$TOOLING/docker/$img/Dockerfile" ] || die "tooling.conf: extra.$e names no image of tooling's ('$img')"
done

# The configurations this run: --only, else --quick, else every configured one and every extra
if [ -n "$ONLY" ]; then
    SELECTED="$(echo "$ONLY" | tr ',' ' ')"
    for c in $SELECTED; do
        standard "$c" >/dev/null || case " $EXTRAS " in *" $c "*) ;; *) die "--only: no configuration '$c'" ;; esac
    done
elif [ "$QUICK" = 1 ]; then
    SELECTED="$(echo "$CONFIGURED" | awk '{for (i = 1; i <= NF; i++) if ($i == "gcc-release") {print $i; exit}} END {}')"
    [ -n "$SELECTED" ] || SELECTED="$(echo "$CONFIGURED" | awk '{print $1}')"
else
    SELECTED="$(words "$CONFIGURED $EXTRAS")"
fi

# resolve <name>: "image|label|args" with the repository's arguments added
resolve() {
    local spec image label args
    if spec="$(standard "$1")"; then
        image="${spec%%|*}"; spec="${spec#*|}"; label="${spec%%|*}"; args="${spec#*|}"
    else
        spec="$(conf "extra.$1")"; image="${spec%% *}"; label="$1"; args="${spec#"$image"}"
    fi
    args="-D${P}WERROR=ON $args $(conf cmake) $(conf "cmake.$1")"
    echo "$image|$label|$(words "$args")"
}

if [ "$PLAN" = 1 ]; then
    echo "test_ubuntu: $NAME"
    for c in $SELECTED; do
        r="$(resolve "$c")"; image="${r%%|*}"; r="${r#*|}"; args="${r#*|}"
        docs=""; [ "$c" = gcc-release ] && [ "$DOCS" = 1 ] && docs=" -D${P}BUILD_DOCS=ON"
        printf '%s %s %s%s\n' "$c" "$image" "$args" "$docs"
    done
    env_line="$(conf env)"; [ -z "$env_line" ] || echo "env $env_line"
    setup_line="$(conf setup)"; [ -z "$setup_line" ] || echo "setup $setup_line"
    exit 0
fi

command -v docker >/dev/null || die "docker is not installed"
docker info >/dev/null 2>&1 || die "docker is not running"

# The snapshot: tracked files that exist (a file deleted but not yet staged is skipped), no macOS metadata
LIST="$(mktemp)"; OUT="$(mktemp)"; SNAPSHOT="$(mktemp)"
trap 'rm -f "$LIST" "$OUT" "$SNAPSHOT"' EXIT
# shellcheck disable=SC2016  # $displaypath is git submodule foreach's, expanded by it
( cd "$REPO" && { git ls-files && git submodule foreach --quiet --recursive \
    'git ls-files | sed "s|^|$displaypath/|"'; } | while IFS= read -r f; do
        if [ -f "$f" ] || [ -L "$f" ]; then printf '%s\n' "$f"; fi
    done ) > "$LIST"
( cd "$REPO" && COPYFILE_DISABLE=1 tar -cf "$SNAPSHOT" -T "$LIST" )

# The script one container runs, for the configurations given as arguments
container_script() {
    cat <<'HEAD'
set -uo pipefail
mkdir -p /work/src && tar -C /work/src -xf /snapshot.tar && cd /work/src
run() {   # run <label> <cmake args...>
    local label="$1"; shift
    local dir="/work/build-${label//[^A-Za-z0-9+.-]/-}"
    local log="$dir.log"
    printf '  %-28s ' "$label"
    if cmake -S . -B "$dir" -G Ninja "$@" >"$log" 2>&1 &&
       cmake --build "$dir" >>"$log" 2>&1 &&
       ctest --test-dir "$dir" --output-on-failure >>"$log" 2>&1; then
        echo "ok   $(grep -E '^[0-9]+% tests passed' "$log" | tail -1)"
    else
        echo "FAILED"
        grep -m 8 -E ": (error|warning|runtime error): " "$log" | sed "s/^/      /"
        tail -40 "$log" | sed 's/^/      /'
    fi
}
docs_option() {   # the documentation, where the image's Doxygen is the pinned one
    case "$(doxygen --version 2>/dev/null)" in
        1.18.*|1.19.*|1.[2-9][0-9].*|[2-9].*) echo "-D${OPTION_PREFIX}BUILD_DOCS=ON" ;;
        *) echo "  (documentation skipped: Doxygen $(doxygen --version 2>/dev/null || echo absent) is older than 1.18)" >&2
           echo "-D${OPTION_PREFIX}BUILD_DOCS=OFF" ;;
    esac
}
echo "$REPO_NAME on $(. /etc/os-release && echo "$PRETTY_NAME"), $(uname -m)"
for c in g++ clang++ g++-15 doxygen; do
    command -v "$c" >/dev/null && echo "  $c: $("$c" --version | head -1)"
done
if [ -n "${SETUP:-}" ] && ! bash -c "$SETUP" >/work/setup.log 2>&1; then
    for label in "${LABELS[@]}"; do printf '  %-28s FAILED\n' "$label"; done
    echo "      setup failed: $SETUP"; tail -40 /work/setup.log | sed 's/^/      /'
    exit 0
fi
HEAD
}

ENV_ARGS=(-e "UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1")
for kv in $(conf env); do ENV_ARGS+=(-e "$kv"); done
[ -z "$JOBS" ] || ENV_ARGS+=(-e "CMAKE_BUILD_PARALLEL_LEVEL=$JOBS" -e "CTEST_PARALLEL_LEVEL=$JOBS" --cpus "$JOBS")

images=""
for c in $SELECTED; do
    img="$(resolve "$c")"; img="${img%%|*}"
    case " $images " in *" $img "*) ;; *) images="$images $img" ;; esac
done

first=1
for img in $images; do
    tag="$("$TOOLING/scripts/build_image.sh" "$img")" || { echo "  $img image                  FAILED" | tee -a "$OUT"; continue; }
    script="$(container_script)"
    labels=()
    lines=""
    for c in $SELECTED; do
        r="$(resolve "$c")"; [ "${r%%|*}" = "$img" ] || continue
        r="${r#*|}"; label="${r%%|*}"; args="${r#*|}"
        labels+=("$label")
        line="run $(printf '%q' "$label")"
        for a in $args; do line="$line $(printf '%q' "$a")"; done
        if [ "$c" = gcc-release ] && [ "$DOCS" = 1 ]; then line="$line \"\$(docs_option)\""; fi
        lines="$lines$line"$'\n'
    done
    [ "$first" = 1 ] || echo
    first=0
    label_decl="LABELS=($(for l in "${labels[@]}"; do printf '%q ' "$l"; done))"
    printf '%s\n%s\n%s' "$label_decl" "$script" "$lines" | docker run --rm -i \
        -v "$SNAPSHOT:/snapshot.tar:ro" \
        -e REPO_NAME="$NAME" -e OPTION_PREFIX="$P" -e SETUP="$(conf setup)" \
        "${ENV_ARGS[@]}" "$tag" bash -s | tee -a "$OUT" \
        || echo "  $img container              FAILED" | tee -a "$OUT"
done

# Each configuration reported one line, "  <label> ok ..." or "  <label> FAILED"
passed="$(grep -cE '^  [^ ].* ok   ' "$OUT" || true)"
failed="$(grep -E '^  [^ ].* FAILED$' "$OUT" | sed -E 's/^  (.*[^ ]) +FAILED$/\1/' | paste -sd, - || true)"
echo
if [ -z "$failed" ] && [ "$passed" -gt 0 ]; then
    echo "test_ubuntu: all $passed configurations passed"
    exit 0
fi
nfailed="$(grep -cE '^  [^ ].* FAILED$' "$OUT" || true)"
echo "test_ubuntu: $nfailed of $(( passed + nfailed )) configurations FAILED: ${failed//,/, }"
exit 1
