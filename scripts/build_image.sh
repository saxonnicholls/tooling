#!/usr/bin/env bash
#
#  build_image.sh
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  Builds one of tooling's standard images locally, if it is not built already, and prints its tag.
#
#      scripts/build_image.sh ubuntu-24.04     # GCC 13, Clang 18 with compiler-rt, CMake, Ninja, Doxygen
#      scripts/build_image.sh ubuntu-26.04     # GCC 15, CMake, Ninja
#
#  The tag is the image's name plus a hash of its Dockerfile, so an edited Dockerfile builds a new image and an
#  unchanged one is reused. A repository's gate calls it through the pinned submodule:
#
#      IMAGE="$(third_party/tooling/scripts/build_image.sh ubuntu-24.04)"
#      docker run --rm -v "$PWD:/src:ro" "$IMAGE" bash -c '...'
#
#  A repository's own image, derived from a standard one (README "Derived images"):
#
#      scripts/build_image.sh ubuntu-24.04 docker/opencl/Dockerfile           build it if need be, print its tag
#      scripts/build_image.sh --check ubuntu-24.04 docker/opencl/Dockerfile   only check it starts FROM the image
#
#  Its Dockerfile starts FROM the standard image, either as `ARG TOOLING_IMAGE` then `FROM ${TOOLING_IMAGE}` (the
#  image this checkout builds, passed in as that build argument) or as a published one,
#  `FROM ghcr.io/saxonnicholls/<image>@sha256:...` (or `:<version>`). Every later FROM names an earlier stage. It is
#  built without a context (it installs what the repository needs; the gate brings the sources), so its tag,
#  snicholls-<image>-derived:<hash>, hashes the Dockerfile and the standard image's tag, and changes with either.
#
#  The released images are also published as ghcr.io/saxonnicholls/<name>:<tooling version>; pin them by digest.
#
set -euo pipefail

CHECK=0
if [ "${1:-}" = --check ]; then CHECK=1; shift; fi
name="${1:?usage: build_image.sh [--check] <ubuntu-24.04|ubuntu-26.04> [<derived Dockerfile>]}"
derived="${2:-}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="$here/docker/$name"
fail() { echo "build_image: $*" >&2; exit 2; }
[ -f "$dir/Dockerfile" ] || fail "no image named '$name' (have: $(cd "$here/docker" && echo */ | tr -d /))"
[ "$CHECK" = 0 ] || [ -n "$derived" ] || fail "--check needs a derived Dockerfile"

sha() { (shasum -a 256 2>/dev/null || sha256sum) | cut -c1-12; }

# from_kind <Dockerfile>: "arg" if it starts FROM ${TOOLING_IMAGE}, "published" if FROM ghcr.io/saxonnicholls/<name>;
# anything else is an error naming the line
from_kind() {
    awk -v name="$name" -v file="$1" '
        function bad(why) { printf "build_image: %s:%d: %s\n", file, NR, why > "/dev/stderr"; failed = 1; exit 2 }
        /^[ \t]*(#|$)/ { next }
        toupper($1) == "FROM" {
            ref = ""
            for (i = 2; i <= NF; i++) if ($i !~ /^--/) { ref = $i; break }
            if (froms == 0) {
                if (ref == "${TOOLING_IMAGE}" || ref == "$TOOLING_IMAGE") kind = "arg"
                else if (ref ~ "^ghcr\\.io/saxonnicholls/" name "([:@]|$)") kind = "published"
                else bad("the first FROM is " ref ", not the " name " image: FROM ${TOOLING_IMAGE} (after ARG TOOLING_IMAGE) or FROM ghcr.io/saxonnicholls/" name "@sha256:...")
            } else if (!(tolower(ref) in stages)) {
                bad("FROM " ref " is neither the " name " image nor an earlier stage")
            }
            if (toupper($(NF - 1)) == "AS") stages[tolower($NF)] = 1
            froms++
        }
        END { if (failed) exit 2; if (!froms) { printf "build_image: %s has no FROM\n", file > "/dev/stderr"; exit 2 } print kind }' "$1"
}

if [ -n "$derived" ]; then
    [ -f "$derived" ] || fail "no Dockerfile $derived"
    kind="$(from_kind "$derived")" || exit 2
    [ "$CHECK" = 0 ] || exit 0
fi

command -v docker >/dev/null || fail "docker is not installed"
docker info >/dev/null 2>&1 || fail "docker is not running"

base="snicholls-$name:$(sha < "$dir/Dockerfile")"
if [ -z "$derived" ] || [ "$kind" = arg ]; then
    if ! docker image inspect "$base" >/dev/null 2>&1; then
        echo "build_image: building $base" >&2
        DOCKER_BUILDKIT=1 docker build -q -t "$base" "$dir" >/dev/null
    fi
fi
[ -n "$derived" ] || { echo "$base"; exit 0; }

tag="snicholls-$name-derived:$( { echo "$base"; cat "$derived"; } | sha)"
if ! docker image inspect "$tag" >/dev/null 2>&1; then
    echo "build_image: building $tag from $derived" >&2
    args=(); [ "$kind" = published ] || args=(--build-arg "TOOLING_IMAGE=$base")
    DOCKER_BUILDKIT=1 docker build -q -t "$tag" "${args[@]}" - < "$derived" >/dev/null
fi
echo "$tag"
