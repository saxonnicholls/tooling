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
#  The released images are also published as ghcr.io/saxonnicholls/<name>:<tooling version>; pin them by digest.
#
set -euo pipefail

name="${1:?usage: build_image.sh <ubuntu-24.04|ubuntu-26.04>}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="$here/docker/$name"
[ -f "$dir/Dockerfile" ] || { echo "build_image: no image named '$name' (have: $(cd "$here/docker" && echo */ | tr -d /))" >&2; exit 2; }
command -v docker >/dev/null || { echo "build_image: docker is not installed" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "build_image: docker is not running" >&2; exit 2; }

hash="$( (shasum -a 256 "$dir/Dockerfile" 2>/dev/null || sha256sum "$dir/Dockerfile") | cut -c1-12)"
tag="snicholls-$name:$hash"
if ! docker image inspect "$tag" >/dev/null 2>&1; then
    echo "build_image: building $tag" >&2
    DOCKER_BUILDKIT=1 docker build -q -t "$tag" "$dir" >/dev/null
fi
echo "$tag"
