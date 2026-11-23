# snicholls-tooling

Shared development and test tooling for the snicholls C++ libraries.

It provides:
- the build images: `docker/ubuntu-24.04` (GCC 13, Clang 18 with compiler-rt, CMake, Ninja, Doxygen) and
  `docker/ubuntu-26.04` (GCC 15), built with `scripts/build_image.sh <image>` and published to
  `ghcr.io/saxonnicholls/<image>`, and a repository's own images derived from them;
- the local Ubuntu gate, `scripts/test_ubuntu.sh`, and the standard make targets, `make/tooling.mk`;
- the repository checks: `scripts/check_mirror.py` (tests and demos mirror the headers), `scripts/check_version.py`
  (versions agree), `scripts/check_interfaces.py` (interfaces have both forms), and `cmake/SnichollsTooling.cmake`
  (every header compiles on its own, behind its named guard);
- the reusable library workflow, `.github/workflows/library.yml`: a library's whole CI, documentation published to
  GitHub Pages included;
- Docker test services (planned): Postgres, mail and SMS sinks, and later a local crypto test network.

[STANDARDS.md](STANDARDS.md) is the standard these tools enforce. Every tool is parameterised by one file in the
calling repository, `tooling.conf`; none is copied.

Status: being assembled for v0.1.0.

Licence: MIT ([LICENSE](LICENSE)).

## Adopting it

1. Pin tooling as a test-only submodule at a release tag:

       git submodule add https://github.com/saxonnicholls/tooling.git third_party/tooling
       git -C third_party/tooling checkout vX.Y.Z

2. Copy [`templates/tooling.conf`](templates/tooling.conf) to the repository's root and fill it in.

3. In the top-level `CMakeLists.txt`, where the tests are configured:

   ```cmake
   include(third_party/tooling/cmake/SnichollsTooling.cmake)
   snicholls_header_check(my_lib_header_check LINK my::lib)   # then apply your warning options to it
   snicholls_tooling_add_checks()                             # CTests check.mirror, check.version, check.interfaces
   ```

   The CMake options the tools set are `<option_prefix>WERROR`, `SANITIZE` (e.g. `address,undefined`),
   `BUILD_DOCS` (a `docs` target), `BUILD_BENCHMARKS` and, if the repository has it, `BUILD_TESTS`.

4. The `Makefile` is one line, plus any targets of the repository's own
   ([make/tooling.mk](#the-make-targets-maketoolingmk)):

   ```make
   include third_party/tooling/make/tooling.mk
   ```

5. `.github/workflows/ci.yml` calls the library workflow at the tag the submodule pins
   ([The library workflow](#the-library-workflow-githubworkflowslibraryyml)):

   ```yaml
   name: CI
   on:
     push:
       branches: [main]
       tags: ["v*"]
     pull_request:
     workflow_dispatch:
   permissions:
     contents: read
   jobs:
     ci:
       uses: saxonnicholls/tooling/.github/workflows/library.yml@vX.Y.Z
       permissions:
         contents: write   # only for pages: true, to push gh-pages
       with:
         pages: true
   ```

6. If the builds need a library the standard images lack, a Dockerfile `FROM` the standard image and one line of
   `tooling.conf` ([Derived images](#derived-images)):

       image = docker/ci/Dockerfile

The local gate is then `make test-werror` on the Mac plus `make ubuntu`. Delete the repository's own copies of these
scripts, its `docker/` build images, its `header_check.cpp.in`, its Makefile's recipes and its CI's jobs.

## tooling.conf

One `key = value` per line. `#` at the start of a line or after a space begins a comment. Lists are separated by
spaces and are not quoted. Flags are `yes` or `no`. A key appears once. Python, bash and CMake read it the same way.

| Key | Used by | Meaning |
|---|---|---|
| `name` | gate, workflow | the repository's name in the report and the documentation site (default: its directory) |
| `include_dir` | all | the include directory (default `include`) |
| `include_root` | all | the public headers, e.g. `include/snicholls/core` (required) |
| `namespace` | interfaces | concepts and interfaces are declared in it, or in one nested in it |
| `guard_prefix` | header check | each header's guard is `<guard_prefix><path under include_root>` as an identifier, e.g. `snicholls_core_meta_concepts_hpp` |
| `macro_prefix` | version | `<macro_prefix>VERSION_MAJOR`, `_MINOR` and `_PATCH` (required) |
| `cmake_project` | version | `project(<cmake_project> VERSION x.y.z)` (required) |
| `option_prefix` | gate, make, workflow | the CMake options `<prefix>WERROR`, `<prefix>SANITIZE`, `<prefix>BUILD_DOCS`, `<prefix>BUILD_BENCHMARKS` (required) |
| `umbrella` | mirror | the umbrella header, which needs no test or demo |
| `docs`, `benchmarks` | gate, make, workflow | whether the repository has them (default `no`) |
| `docs_html` | workflow | the HTML under the documentation's build directory, published to Pages (default `docs/html`) |
| `configurations` | gate, workflow | a subset of the eight configurations (default: all) |
| `cmake` | gate, make, workflow | more CMake arguments for every build |
| `cmake.<config>` | gate, workflow | more CMake arguments for one configuration |
| `extra.<label>` | gate, workflow | `<image> <cmake arguments>`: a configuration of the repository's own |
| `image` | gate, workflow | a Dockerfile, derived from a standard image, that every configuration runs in ([Derived images](#derived-images)) |
| `image.<config>` | gate, workflow | ... that one configuration runs in, standard or extra |
| `env` | gate, workflow | `KEY=value` pairs for the builds and the tests |
| `setup` | gate, workflow | a shell command run in each container before the configurations |
| `make.demos`, `make.benchmarks` | make | a command that replaces the default run of `make demos` or `make benchmarks` |
| `tests_dir`, `demos_dir`, `benchmarks_dir` | mirror, interfaces | default `tests`, `demos`, `benchmarks` |
| `detail_needs_test` | mirror | a `detail/` header has a test (default `yes`); never a demo |
| `mirror_ignore` | mirror | directories under tests, demos and benchmarks that are not mirrored (default `cmake fixtures data`) |
| `mirror_listed_only` | mirror | directories whose files need no header but must be listed (e.g. `support parity tutorials`) |
| `mirror_listed_by` | mirror | `path` (default) or `stem`, for registrations such as `my_add_test(<sub>/<name>)` |
| `version_header` | version | default `<include_root>/version.hpp` |
| `version_file.<label>` | version | `<path> <regex>`: one more copy of the version; the regex's groups, joined with `.` |
| `interfaces_exempt` | interfaces | class names allowed pure virtual functions outside `interfaces/` |

## The gate: `scripts/test_ubuntu.sh`

    third_party/tooling/scripts/test_ubuntu.sh                 all configurations
    third_party/tooling/scripts/test_ubuntu.sh --quick         gcc-release only
    third_party/tooling/scripts/test_ubuntu.sh --only clang-asan,gcc15-asan
    third_party/tooling/scripts/test_ubuntu.sh -j 4            at most 4 jobs, on 4 CPUs
    third_party/tooling/scripts/test_ubuntu.sh --plan          print the configurations, without Docker
    third_party/tooling/scripts/test_ubuntu.sh --list          print their names, one per line
    third_party/tooling/scripts/test_ubuntu.sh --image gcc-release   build that configuration's image, print its tag

| Configuration | Image | Compiler | Build |
|---|---|---|---|
| `gcc-release` | ubuntu-24.04 | GCC 13 | Release, the benchmark smoke runs and the documentation |
| `gcc-debug` | ubuntu-24.04 | GCC 13 | Debug |
| `clang-release` | ubuntu-24.04 | Clang 18 | Release |
| `clang-debug` | ubuntu-24.04 | Clang 18 | Debug |
| `clang-asan` | ubuntu-24.04 | Clang 18 | AddressSanitizer and UBSan |
| `gcc-asan` | ubuntu-24.04 | GCC 13 | AddressSanitizer and UBSan |
| `gcc15-release` | ubuntu-26.04 | GCC 15 | Release and the benchmark smoke runs |
| `gcc15-asan` | ubuntu-26.04 | GCC 15 | AddressSanitizer and UBSan |

- **Each configuration** is a fresh CMake build with `<prefix>WERROR=ON`, then every CTest.
- **UBSan halts on its first report**, so undefined behaviour fails the test that reached it.
- **The documentation is skipped** where the image's Doxygen is older than 1.18 (the ARM64 image), and the report
  says so.
- **The snapshot.** The tracked files, the submodules' included, are packed into one tarball, which is mounted
  read-only and unpacked in each container. Nothing untracked is tested, nothing is written back, and an edit made
  during the run reaches no configuration.
- **Every configuration runs.** The report has one line per configuration, then the failures by name. The exit
  status is 1 if any failed and 2 on a usage or configuration error.
- **Each image's containers** run its configurations one after another; a configuration in a derived image runs in
  that image instead of its standard one.

## Derived images

A repository whose builds need more than the standard images hold (OpenCL with PoCL, a database client) writes one
Dockerfile that starts `FROM` a standard image, and names it in `tooling.conf`:

    image          = docker/ci/Dockerfile     every configuration runs in it
    image.gcc-asan = docker/asan/Dockerfile   this configuration runs in another (image.<config> wins over image)

```dockerfile
ARG TOOLING_IMAGE
FROM ${TOOLING_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends pocl-opencl-icd ocl-icd-opencl-dev \
    && rm -rf /var/lib/apt/lists/*
```

- **The base.** The derived image is built on the standard image of each configuration that names it, so one
  Dockerfile serves `ubuntu-24.04` and `ubuntu-26.04`. `FROM ${TOOLING_IMAGE}` is the image the pinned tooling
  checkout builds, so the gate, CI and the pin agree. A published image works too, by digest or tag,
  `FROM ghcr.io/saxonnicholls/ubuntu-24.04@sha256:...`, if it is the configuration's own standard image.
- **Every image starts from tooling's** (STANDARDS section 5): `scripts/build_image.sh --check` refuses a first
  `FROM` that is not the standard image, and a later `FROM` that is not an earlier stage. The gate checks every
  derived image before anything runs, and the problem is a configuration error.
- **The tag** is `snicholls-<standard image>-derived:<hash>`, the hash of the Dockerfile and of the standard image's
  tag: an unchanged image is reused, and an edit to either builds a new one. By hand:
  `third_party/tooling/scripts/build_image.sh ubuntu-24.04 docker/ci/Dockerfile`.
- **No build context.** The image installs what the builds need; the gate brings the sources. A Dockerfile that
  `COPY`s from the repository is not supported.

## The make targets: `make/tooling.mk`

`include third_party/tooling/make/tooling.mk` gives a repository the standard targets, from its `tooling.conf`:

| Target | What it runs |
|---|---|
| `make test` | `make check`, then configure, build and every CTest in `build` |
| `make test-werror` | the same in `build-werror` with `<prefix>WERROR=ON`: the Mac half of the local gate |
| `make asan` | `build-asan`, RelWithDebInfo, `<prefix>SANITIZE=address,undefined`, warnings as errors; UBSan halts on its first report |
| `make docs` | `build-docs` with `<prefix>BUILD_DOCS=ON` (and `BUILD_TESTS=OFF`), target `docs`; an error if `docs = no` |
| `make check` | `check_version.py`, `check_mirror.py`, `check_interfaces.py` |
| `make ubuntu` | `scripts/test_ubuntu.sh`, the Ubuntu half of the gate; `UBUNTU="--quick"` passes its arguments |
| `make demos` | build in `build` and run the CTests labelled `demo` with their output; or `make.demos` |
| `make benchmarks` | `build-bench`, Release, `<prefix>BUILD_BENCHMARKS=ON`, the CTests labelled `benchmark`; or `make.benchmarks`; an error if `benchmarks = no` |
| `make clean` | removes every build directory above |

- **Variables:** `CXX` (default `c++`), `BUILD` (`build`), `CONFIG` (`Release`), `CMAKE_FLAGS` (added to every
  configure, after `tooling.conf`'s `cmake`), `JOBS` (the CPUs), `UBUNTU`.
- **The repository's own runs.** `make.demos` and `make.benchmarks` are commands, run with `BUILD`, `CONFIG` and `CXX`
  in their environment, e.g. `make.benchmarks = python3 scripts/benchmarks_md.py --build build-bench`.
- **More targets** go in the repository's `Makefile` after the `include`.

## The library workflow: `.github/workflows/library.yml`

A reusable workflow (`on: workflow_call`) that is a library's whole CI. Every leg blocks except Windows.

| Job | Runner | What it runs |
|---|---|---|
| `plan` | Ubuntu | reads `tooling.conf`: the configurations (`test_ubuntu.sh --list`), the option prefix, `docs`, `benchmarks`, `cmake`, `env` |
| `checks` | Ubuntu | `check_version.py` (against the tag, on a tag push), `check_mirror.py`, `check_interfaces.py` |
| `linux` | x86-64 and ARM64 | each configuration of the gate in a job of its own, `test_ubuntu.sh --only <config>`, in its image (derived ones included), 4 jobs on x86-64 and 3 on ARM64 |
| `macos` | ARM64 and x86-64 | Apple Clang: Release with `<prefix>WERROR=ON` and the benchmark smoke runs, then Debug at `-O0` with asserts live |
| `windows` | Windows | MSVC Release with `<prefix>WERROR=ON` and the benchmark smoke runs; `continue-on-error` unless `msvc_continue_on_error: false` |
| `docs` | Ubuntu | the documentation in the `gcc-release` image, with the pinned Doxygen; with `pages`, published to GitHub Pages |

| Input | Default | Meaning |
|---|---|---|
| `path` | `.` | the repository, relative to the checkout's root |
| `tooling` | `third_party/tooling` | tooling's checkout, relative to `path` |
| `prepare` | none | a bash command run from the checkout's root in every job, after the checkout |
| `linux_arm64` | `true` | the Linux configurations on ARM64 as well as x86-64 |
| `macos` | `true` | the macOS legs |
| `msvc` | `true` | the Windows leg |
| `msvc_continue_on_error` | `true` | a Windows failure is reported, not gated on |
| `benchmarks` | `true` | the benchmark smoke runs on macOS and Windows, when `benchmarks = yes`; the Linux configurations follow `tooling.conf` |
| `docs` | `true` | the documentation job, when `docs = yes` |
| `pages` | `false` | publish the documentation: `main` to `/main/`, each release tag to `/vX.Y.Z/`, the site's root to the newest release |

- **Its tag.** Call it at the tag the submodule pins: the workflow runs the scripts of the submodule, and the two
  move together, in the same bump commit.
- **Permissions.** Every job holds `contents: read`, except `docs`, which has what the calling job grants it. Grant
  `contents: write` on the calling job only with `pages: true`, so it can push `gh-pages`.
- **Linux runs in the images, not on the runner.** The configurations are the gate's, from the same `tooling.conf`,
  so CI and `make ubuntu` agree, and `image`, `setup` and `env` apply to both. macOS and Windows build natively,
  with `cmake` and `env` from `tooling.conf`.
- **Submodules** are checked out recursively in every job; the actions are pinned by commit SHA.

## The checks

Each check reads `tooling.conf` from `--root` (default: the current directory). It exits 0 when the rule holds, 1
with one line per problem when it does not, and 2 on a configuration error. `snicholls_tooling_add_checks()` runs
them as CTests with the label `boundary`.

    python3 third_party/tooling/scripts/check_mirror.py
    python3 third_party/tooling/scripts/check_version.py [--tag vX.Y.Z]   # or RELEASE_TAG in the environment
    python3 third_party/tooling/scripts/check_interfaces.py

- **`check_mirror.py`** (STANDARDS section 4):
  - every header has its test, and every public header its demo;
  - each is listed in a `CMakeLists.txt` under `tests/` or `demos/`;
  - no test, demo or benchmark is without a header or unlisted;
  - companion tests (`<name>_<aspect>_test.cpp`) belong to `<name>.hpp` and must be listed.
- **`check_version.py`** (section 2): the version header, `project(... VERSION)`, every `version_file.<label>` and
  the tag agree.
- **`check_interfaces.py`** (section 3), under `include_root`, at any depth:
  - `interfaces/<x>.hpp` with a pure virtual class has `concepts/<x>.hpp`, and the reverse;
  - both are in `namespace`;
  - each has `tests/<area>/concepts/<x>_test.cpp` and `tests/<area>/interfaces/<x>_test.cpp`;
  - no class with pure virtual functions lives elsewhere (`detail/` and `interfaces_exempt` excepted);
  - a header in `interfaces/` with no pure virtual class (an adapter, the reference implementation, the conformance
    kit) is support and needs no twin.

## The header check: `cmake/SnichollsTooling.cmake`

    snicholls_header_check(<target> [LINK <library>...] [COMPILE_OPTIONS <option>...] [EXCLUDE <regex>...]
                           [HEADERS <header>...] [CXX_STANDARD <n>] [CONFIG <tooling.conf>])

This defines an OBJECT library with one translation unit per header under `include_root`. Each one:
1. includes the header;
2. fails with `#error` unless the header's named guard (`guard_prefix` plus its path) is defined, so `#pragma once`
   and misnamed guards fail;
3. includes the header again.

- `EXCLUDE` leaves out headers that are built elsewhere, such as an optional backend that is not configured.
- `HEADERS` with `CXX_STANDARD 17` keeps a chosen header C++17-clean.

## Tests

    python3 -m unittest discover -s tests -v    # the checks, the CMake module, the gate's plan and its derived
                                                # images, make/tooling.mk, the workflows' static rules
                                                # (CMake, make, a C++20 compiler)
    tests/gate_test.sh                          # the gate in Docker: the fixture passes all eight, planted UB fails
                                                # exactly the three sanitizer configurations, gcc-debug runs in the
                                                # fixture's derived image (--quick: a shorter run)
    tests/image_smoke.sh                        # inside an image: what the gate needs is there

`tests/fixtures/good` is a small repository that passes every check, with a derived image (`docker/ci`) that its
`gcc-debug` configuration names. Each test breaks one rule in a copy of it; `tests/fixture_repo.sh <dir>` makes it a
git repository with this checkout vendored as `third_party/tooling`. CI (`.github/workflows/tools.yml`) runs all of
them on Linux and macOS, shellcheck over every script, actionlint over every workflow, and calls the library
workflow on the fixture as a repository's `ci.yml` does.
