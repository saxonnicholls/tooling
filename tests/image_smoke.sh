#!/usr/bin/env bash
#
#  image_smoke.sh
#  snicholls-tooling
#
#  Copyright 2010-2026 Saxon Herschel Nicholls
#
#  Runs inside a standard image and proves it can do what the gate needs: each compiler builds and runs C++20
#  with warnings as errors, the sanitizers link and run, CMake and Ninja work, and (in the 24.04 image) Doxygen
#  is the pinned version. Exits non-zero on the first failure.
#
#      docker run --rm -v "$PWD/tests:/tests:ro" <image> bash /tests/image_smoke.sh ubuntu-24.04
#
set -euo pipefail
name="${1:?usage: image_smoke.sh <ubuntu-24.04|ubuntu-26.04>}"
work="$(mktemp -d)"; cd "$work"

cat > smoke.cpp <<'CPP'
#include <array>
#include <concepts>
#include <cstdio>
#include <numeric>
#include <span>

template <std::integral T>
constexpr T sum(std::span<const T> xs) { return std::accumulate(xs.begin(), xs.end(), T{}); }

int main()
{
    static constexpr std::array<int, 4> xs{1, 2, 3, 4};
    static_assert(sum(std::span<const int>(xs)) == 10);
    std::printf("ok\n");
    return sum(std::span<const int>(xs)) == 10 ? 0 : 1;
}
CPP

check() {   # check <compiler> <extra flags...>
    local cxx="$1"; shift
    "$cxx" -std=c++20 -Wall -Wextra -Wpedantic -Werror "$@" smoke.cpp -o smoke
    [ "$(./smoke)" = "ok" ] || { echo "image_smoke: $cxx $* runs wrong" >&2; exit 1; }
    echo "  $cxx $*: ok"
}

case "$name" in
  ubuntu-24.04)
    check g++-13 -O2
    check clang++ -O2
    check clang++ -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer   # compiler-rt is present
    check g++-13 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer
    doxygen --version | grep -Eq '^1\.(18|9)\.' || { echo "image_smoke: unexpected Doxygen $(doxygen --version)" >&2; exit 1; }
    echo "  doxygen $(doxygen --version): ok"
    ;;
  ubuntu-26.04)
    check g++-15 -O2
    check g++-15 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer
    ;;
  *) echo "image_smoke: unknown image $name" >&2; exit 2 ;;
esac

mkdir -p proj && cat > proj/CMakeLists.txt <<'CMAKE'
cmake_minimum_required(VERSION 3.20)
project(smoke CXX)
set(CMAKE_CXX_STANDARD 20)
add_executable(smoke ../smoke.cpp)
CMAKE
cmake -S proj -B proj/build -G Ninja -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build proj/build >/dev/null
[ "$(proj/build/smoke)" = "ok" ] && echo "  cmake + ninja: ok"
echo "image_smoke: $name passed"
