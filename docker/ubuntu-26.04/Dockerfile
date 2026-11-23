# syntax=docker/dockerfile:1.6
#
# snicholls-tooling - the standard Ubuntu 26.04 build and test image (GCC 15).
#
# GitHub's ubuntu-latest compiles with GCC 15, which warns where GCC 13 does
# not (a false -Warray-bounds, for one), so the gate runs its GCC 15
# configurations in this image, beside the Ubuntu 24.04 one.
#
# Ubuntu 26.04 LTS ships GCC 15 in its own archive: no PPA, no compiler built
# from source. The base image is pinned by its release, the compiler by its
# major version. Compilers and build tools only; the documentation is built in
# the 24.04 image.

FROM ubuntu:26.04

LABEL org.opencontainers.image.title="snicholls Ubuntu 26.04 GCC 15 builder" \
      org.opencontainers.image.description="Ubuntu 26.04: GCC 15, CMake, Ninja"

ENV DEBIAN_FRONTEND=noninteractive

RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential gcc-15 g++-15 \
      cmake ninja-build \
      python3-minimal git ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    g++-15 --version | head -1

# Sources are mounted read-only by the gate and copied in, so a build inside
# the container never writes into the checkout.
WORKDIR /work
CMD ["bash"]
