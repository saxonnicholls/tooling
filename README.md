# snicholls-tooling

Shared development and test tooling for the snicholls C++ libraries.

It provides:
- the build images: `docker/ubuntu-24.04` (GCC 13, Clang 18 with compiler-rt, CMake, Ninja, Doxygen) and
  `docker/ubuntu-26.04` (GCC 15), built with `scripts/build_image.sh <image>` and published to
  `ghcr.io/saxonnicholls/<image>`;
- the local Ubuntu gate;
- the repository checks (tests and demos mirror the headers, versions agree, interfaces have both forms);
- reusable GitHub workflows, including documentation published to GitHub Pages;
- Docker test services: a local crypto test network, Postgres, mail and SMS sinks.

[STANDARDS.md](STANDARDS.md) is the standard these tools enforce.

Status: being assembled for v0.1.0.

Licence: MIT ([LICENSE](LICENSE)).
