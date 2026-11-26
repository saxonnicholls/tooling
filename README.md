# snicholls-tooling

Shared development and test tooling for the snicholls C++ libraries.

It provides:
- the build images: `docker/ubuntu-24.04` (GCC 13, Clang 18 with compiler-rt, CMake, Ninja, Doxygen) and
  `docker/ubuntu-26.04` (GCC 15), built with `scripts/build_image.sh <image>` and published to
  `ghcr.io/saxonnicholls/<image>`, and a repository's own images derived from them;
- the local Ubuntu gate, `scripts/test_ubuntu.sh`, and the standard make targets, `make/tooling.mk`;
- the machine's share for builds and gates, `scripts/resources.sh`: how many jobs, one gate at a time, a memory cap;
- the repository checks: `scripts/check_mirror.py` (tests and demos mirror the headers), `scripts/check_version.py`
  (versions agree), `scripts/check_interfaces.py` (interfaces have both forms), `scripts/check_pins.py` (one version
  of each library, each pinned where it is used), and `cmake/SnichollsTooling.cmake` (every header compiles on its
  own, behind its named guard);
- one version of each library in a build, at configure (`cmake/SnichollsOneVersion.cmake`), compile (the version
  header's two-versions check) and link time (the workflow's `odr` job);
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

3. Pin every library the repository uses directly, ours or third-party, as a submodule in its own `third_party/`,
   at a release tag, even when another dependency already pins it. Never reach one through another library's
   `third_party/`, a sibling checkout (`../<repo>`) or a system install: `check_pins.py` fails on it
   ([One version of each library](#one-version-of-each-library)).

4. In the top-level `CMakeLists.txt`:

   ```cmake
   project(my_lib VERSION 1.2.3 LANGUAGES CXX)
   include(third_party/tooling/cmake/SnichollsTooling.cmake)
   snicholls_library_begin(my_lib ${PROJECT_VERSION} my::lib)  # a second copy of my_lib in a build stops here
   # ... add_library(my_lib ...), add_library(my::lib ALIAS my_lib), the pins' add_subdirectory and
   #     snicholls_require calls

   # where the tests are configured:
   snicholls_header_check(my_lib_header_check LINK my::lib)   # then apply your warning options to it
   snicholls_single_include_check(my_lib_single_include)      # generated in the build tree, compiled alone
   snicholls_tooling_add_checks()   # CTests check.mirror, check.version, check.interfaces, check.pins,
                                    # check.single_include

   # the last line:
   if(CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)
       snicholls_assert_single_versions()
   endif()
   ```

   The version header starts with the two-versions check, before its guard
   ([templates/version.hpp](templates/version.hpp), [The version header](#the-version-header)).

   The single include needs a `single_include.<name>` line in `tooling.conf`. It is never committed: add
   `/single_include/*.hpp` to `.gitignore` and a `single_include/README.md` saying where to download it (the
   release) and how to build it (`make single-include`).

   The CMake options the tools set are `<option_prefix>WERROR`, `SANITIZE` (e.g. `address,undefined`),
   `BUILD_DOCS` (a `docs` target), `BUILD_BENCHMARKS` and, if the repository has it, `BUILD_TESTS`.

5. The `Makefile` is one line, plus any targets of the repository's own
   ([make/tooling.mk](#the-make-targets-maketoolingmk)):

   ```make
   include third_party/tooling/make/tooling.mk
   ```

6. `.github/workflows/ci.yml` calls the library workflow at the tag the submodule pins
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

7. If the builds need a library the standard images lack, a Dockerfile `FROM` the standard image and one line of
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
| `mirror_listed_by` | mirror | `path` (default); `stem`, for registrations such as `my_add_test(<sub>/<name>)`; or `name`, for `my_add_test(<sub>/<name>_test)` |
| `version_header` | version | default `<include_root>/version.hpp` |
| `version_file.<label>` | version | `<path> <regex>`: one more copy of the version; the regex's groups, joined with `.` |
| `interfaces_exempt` | interfaces | class names allowed pure virtual functions outside `interfaces/` |
| `pins_ignore`, `pins_ignore.<label>` | pins | submodules, by URL or by path from the root, neither checked nor walked; say why beside each |
| `pins_allow_untagged`, `pins_allow_untagged.<label>` | pins | libraries, by URL or by name (the URL's last part), whose pins may be commits: a third party with no releases; one version is still enforced |
| `pins_reach_exempt`, `pins_reach_exempt.<label>` | pins | files (from the root) or include roots (`snicholls/x`) exempt from the rule that every library is reached through a direct pin |
| `single_include.<name>` | single include | the umbrella header as it is included (`snicholls/core/core.hpp`), flattened into `<name>.hpp`; at least one (required) |
| `single_include_dir` | single include | where `make single-include` writes, default `single_include` (git-ignored but for its README) |
| `single_include_inline` | single include | the include directories whose headers are expanded (default `include_dir`); add each pinned library's, e.g. `include third_party/core/include` |
| `single_include_opt_in` | single include | headers under `include_root` left out on purpose, e.g. one that links a third party |

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

## Resources: `scripts/resources.sh`

A machine is shared by every repository and session on it, so builds and gates take a share of it, never all of it
(STANDARDS section 5, "Resources").

    scripts/resources.sh jobs          compiles at once: a quarter of the cores, at most one per 16 GB, at least 1
    scripts/resources.sh gate-memory   the memory cap of one gate container
    scripts/resources.sh gate-slots    how many gates may run at once on this machine
    scripts/resources.sh status        who holds the gate slots now, and since when

- **Jobs.** `make/tooling.mk`'s `JOBS` and the gate's `-j` default to `resources.sh jobs`. On a CI runner (`CI=true`)
  it is every core: the runner is the job's own.
- **One gate at a time.** Before its containers start, `test_ubuntu.sh` takes a gate slot, a directory made with
  `mkdir` (atomic) under the lock directory, which holds its pid, what it runs and since when. A second gate waits,
  says who holds the slot, and looks again every few seconds. The slot is released when the gate exits, however it
  exits; one whose holder was killed is taken back by the next gate that wants it.
- **A memory cap.** Each gate container runs with `--memory` and `--memory-swap` at the gate memory, and with
  `--cpus` at the jobs (no more than Docker has).

| Variable | Default | What |
|---|---|---|
| `SNICHOLLS_JOBS` | a quarter of the cores, at most one per 16 GB, at least 1 | compiles and tests at once |
| `SNICHOLLS_GATE_SLOTS` | `1` | gates at once on this machine; every session must agree |
| `SNICHOLLS_GATE_MEMORY` | `24g` | the memory cap of one gate container, swap included (Docker's syntax) |
| `SNICHOLLS_GATE_POLL` | `10` | seconds between a waiting gate's looks at the slots |
| `SNICHOLLS_LOCK_DIR` | `/tmp/snicholls-gates` | the slots' directory, the same for every session on the machine |

**A repository with a gate script of its own** (one that runs containers or a long build outside `test_ubuntu.sh`)
sources `resources.sh` from its tooling pin, takes a slot before its containers start, releases it on exit, and caps
its containers the same way:

```bash
. third_party/tooling/scripts/resources.sh
trap 'rm -f "$TMP"; snicholls_gate_release' EXIT   # chained into the script's own trap, set before the slot is taken
snicholls_gate_acquire "my-library: full gate"     # waits for the slot
JOBS="${JOBS:-$(snicholls_jobs)}"
docker run --rm --memory "$(snicholls_gate_memory)" --memory-swap "$(snicholls_gate_memory)" --cpus "$JOBS" ...
```

The functions work under `set -euo pipefail`, and in bash 3.2 (macOS) as in bash 5. snicholls-core, crypto and
ts-moveables have gate scripts of their own and take the slot this way.

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
| `make check` | `check_version.py`, `check_mirror.py`, `check_interfaces.py`, `single_include.py --check`, `check_pins.py` |
| `make ubuntu` | `scripts/test_ubuntu.sh`, the Ubuntu half of the gate; `UBUNTU="--quick"` passes its arguments |
| `make demos` | build in `build` and run the CTests labelled `demo` with their output; or `make.demos` |
| `make benchmarks` | `build-bench`, Release, `<prefix>BUILD_BENCHMARKS=ON`, the CTests labelled `benchmark`; or `make.benchmarks`; an error if `benchmarks = no` |
| `make clean` | removes every build directory above |

- **Variables:** `CXX` (default `c++`), `BUILD` (`build`), `CONFIG` (`Release`), `CMAKE_FLAGS` (added to every
  configure, after `tooling.conf`'s `cmake`), `JOBS` (the machine's share, `scripts/resources.sh jobs`), `UBUNTU`.
- **The repository's own runs.** `make.demos` and `make.benchmarks` are commands, run with `BUILD`, `CONFIG` and `CXX`
  in their environment, e.g. `make.benchmarks = python3 scripts/benchmarks_md.py --build build-bench`.
- **More targets** go in the repository's `Makefile` after the `include`.

## The library workflow: `.github/workflows/library.yml`

A reusable workflow (`on: workflow_call`) that is a library's whole CI. Every leg blocks except Windows.

| Job | Runner | What it runs |
|---|---|---|
| `plan` | Ubuntu | reads `tooling.conf`: the configurations (`test_ubuntu.sh --list`), the option prefix, `docs`, `benchmarks`, `cmake`, `env` |
| `checks` | Ubuntu | `check_version.py` (against the tag, on a tag push), `check_mirror.py`, `check_interfaces.py`, `single_include.py --check`, `check_pins.py` (on a tag push every warning is an error); the submodules are full clones, so their tags are there |
| `linux` | x86-64 and ARM64 | each configuration of the gate in a job of its own, `test_ubuntu.sh --only <config>`, in its image (derived ones included), 4 jobs on x86-64 and 3 on ARM64 |
| `macos` | ARM64 and x86-64 | Apple Clang: Release with `<prefix>WERROR=ON` and the benchmark smoke runs, then Debug at `-O0` with asserts live |
| `windows` | Windows | MSVC Release with `<prefix>WERROR=ON` and the benchmark smoke runs; `continue-on-error` unless `msvc_continue_on_error: false` |
| `odr` | Ubuntu | GCC in the `gcc-release` image: Release with `<prefix>WERROR=ON`, `CMAKE_INTERPROCEDURAL_OPTIMIZATION=ON` and `CMAKE_CXX_FLAGS=-flto -Wodr -Werror=odr -Werror=lto-type-mismatch`, then every CTest; two definitions of one entity that differ fail the link |
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
| `odr_check` | `true` | the `odr` job: GCC with link-time optimisation and `-Wodr` as an error |
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
    python3 third_party/tooling/scripts/check_pins.py [--release] [--offline]   # --release: or RELEASE_TAG
    python3 third_party/tooling/scripts/single_include.py [--check]

- **`check_mirror.py`** (STANDARDS section 4):
  - every header has its test, and every public header its demo;
  - each is listed in a `CMakeLists.txt` under `tests/` or `demos/`;
  - no test, demo or benchmark is without a header or unlisted;
  - companion tests (`<name>_<aspect>_test.cpp`) belong to `<name>.hpp` and must be listed.
- **`check_version.py`** (section 2): the version header, `project(... VERSION)`, every `version_file.<label>` and
  the tag agree, and the version header starts with its two-versions check, whose literals (and the version in its
  `#error` text) are one more copy of the number ([The version header](#the-version-header)).
- **`check_pins.py`** (section 2): one version of each library, each pinned where it is used
  ([One version of each library](#one-version-of-each-library)). It also exits 77 when the root is in no git work
  tree, as in the gate's snapshot, and the CTest `check.pins` reports that as skipped.
- **`check_interfaces.py`** (section 3), under `include_root`, at any depth:
  - `interfaces/<x>.hpp` with a pure virtual class has `concepts/<x>.hpp`, and the reverse;
  - both are in `namespace`;
  - each has `tests/<area>/concepts/<x>_test.cpp` and `tests/<area>/interfaces/<x>_test.cpp`;
  - no class with pure virtual functions lives elsewhere (`detail/` and `interfaces_exempt` excepted);
  - a header in `interfaces/` with no pure virtual class (an adapter, the reference implementation, the conformance
    kit) is support and needs no twin.

- **`single_include.py`** (section 2): without `--check` it writes every `single_include.<name>` file, into
  `single_include_dir` or `--out <dir>`. With `--check` it writes nothing and fails when a header under
  `include_root` is in no single include and not opted out, or when an opted-out header is included anyway. Headers
  found in `single_include_inline` are expanded where they are first included unconditionally, once each, by real
  path; a header first reached inside an `#if` is written there too, and again at its next unconditional include,
  so that no platform loses it (its guard compiles it once). Every other include is kept as written.

## One version of each library

A build has one version of each library (STANDARDS section 2). A repository reaches a library through its own pin
and through its dependencies' pins, so one checkout can hold several copies; the build compiles the shallowest, which
the top-level project adds first, and the deeper ones are shadowed.

| What | When | Strictness |
|---|---|---|
| Two versions of a library in the build (configure, compile, link) | always | hard error |
| A consumer requiring a newer version than the one that won | always | hard error |
| A stale nested pin that is checked out but never compiled | ordinary commits | warning naming it |
| The same stale nested pin | on a release tag | hard error |

### The pins: `scripts/check_pins.py`

- **The walk.** Every submodule at every depth: `.gitmodules` and the gitlink in the parent's tree (`HEAD` at the
  top, the pinned commit below), into each checked-out submodule.
- **A library is its URL.** The remote, normalised: scheme, user, port, case and `.git` dropped, `git@host:path`
  read as `host/path`. `third_party/ts_moveables` in one repository and `third_party/ts-moveables` in another are one
  library when their URLs are.
- **A pin is its tag.** The release tag (`vX.Y.Z`) at the pinned commit, from any checkout of the library, else from
  `git ls-remote --tags` (a shallow checkout may lack its tags; `--offline` never asks).
- **Errors:** a built pin that is not a release tag (unless `pins_allow_untagged`); two copies at the same depth and
  none shallower at different commits (whichever is added first wins); a consumer whose CMake files say
  `snicholls_require(<name> <minimum>)` (or core's `snicholls_core_require(<minimum>)`) for more than the built copy
  is, which configure would refuse (its `tests/` are not read: they hold fixtures); a gitlink with no `.gitmodules`
  entry; a copy of the repository itself, a cycle.
- **Every library is reached through a direct pin.** A CMake file or Makefile outside `third_party/` whose
  `include()`, `add_subdirectory()`, `include_directories()`, `target_include_directories()`, `-I` or make `include`
  names `third_party/<x>/third_party/`, or a `../` path out of the repository, is an error. So is an
  `#include <snicholls/<x>/...>` in any source outside `third_party/` whose include root is neither the
  repository's own nor in a direct pin's include directory (`<pin>/include/snicholls/<x>`, or the pin's
  `include_dir`). `pins_reach_exempt` names an exception.
- **Warnings**, errors with `--release` or `RELEASE_TAG`: a shadowed copy at another commit than the built one, a
  checkout away from its pin, a submodule added but not committed, a pin whose tag cannot be found, an unused
  `pins_ignore` entry. A requirement that cannot be checked (the built copy has no tag) is noted, not failed.

```text
  third_party/core                       v0.5.0       built
  third_party/ts/third_party/core        v0.4.0       shadowed
check_pins: warning: core: third_party/ts/third_party/core is pinned at v0.4.0 but shadowed by third_party/core at
v0.5.0, which is what the build compiles: bump it to one version before the release
check_pins: ok - 1 library, one version of each in the build, 1 warning
```

### Configure: `cmake/SnichollsOneVersion.cmake`

Included by `SnichollsTooling.cmake`; the generic form of snicholls-core's three diamond rules.

    snicholls_library_begin(<name> <version> <target>)   in the library, after project(), before its target
    snicholls_require(<name> <minimum>)                  in every consumer, after the library is added
    snicholls_assert_single_versions()                   the last line of a top-level project

- **`snicholls_library_begin`** records `<name>@<version>` and the copy's directory. If `<target>` is already
  defined, another copy was added first and won: it says so, with a warning naming both versions when they differ,
  and returns from the calling `CMakeLists.txt`. It is a macro, so its `return()` is the caller's, exactly as
  core's `if(TARGET snicholls::core) ... return() endif()`; call it at the file's top level, never inside a
  function.
- **`snicholls_require`** fails configure when the winning copy is older than `<minimum>`, or was never added.
- **`snicholls_assert_single_versions`** fails configure when any library was reached at two versions, listing each
  copy's version and directory; the same version twice is fine.
- Global properties: `SNICHOLLS_LIBRARIES`, `SNICHOLLS_LIBRARY_VERSIONS_SEEN` (`<name>@<version>`), and per library
  `SNICHOLLS_LIBRARY_<name>_VERSION`, `_SOURCE_DIR` (the winner) and `_COPIES`.

A middle library, `snicholls-widgets`, uses core and is used by an application:

```cmake
# widgets/CMakeLists.txt
cmake_minimum_required(VERSION 3.20)
project(snicholls_widgets VERSION 0.4.0 LANGUAGES CXX)
include(${CMAKE_CURRENT_SOURCE_DIR}/third_party/tooling/cmake/SnichollsTooling.cmake)
snicholls_library_begin(snicholls_widgets ${PROJECT_VERSION} snicholls::widgets)   # a second copy returns here

add_subdirectory(third_party/core EXCLUDE_FROM_ALL)   # its own pin: skipped when the top level added core first
snicholls_require(snicholls_core 0.5.0)               # what widgets uses, never a forced pin

add_library(snicholls_widgets INTERFACE)
add_library(snicholls::widgets ALIAS snicholls_widgets)
target_link_libraries(snicholls_widgets INTERFACE snicholls::core)
# ... its tests, demos and checks when it is the top level
if(CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR)
    snicholls_assert_single_versions()
endif()
```

```cmake
# app/CMakeLists.txt: the top level pins core and widgets itself, and adds core first, so its pin wins
cmake_minimum_required(VERSION 3.20)
project(app VERSION 1.0.0 LANGUAGES CXX)
include(third_party/tooling/cmake/SnichollsTooling.cmake)
add_subdirectory(third_party/core EXCLUDE_FROM_ALL)
add_subdirectory(third_party/widgets EXCLUDE_FROM_ALL)   # widgets' third_party/core is skipped
snicholls_require(snicholls_core 0.5.0)
snicholls_require(snicholls_widgets 0.4.0)
add_executable(app main.cpp)
target_link_libraries(app PRIVATE snicholls::widgets snicholls::core)
snicholls_assert_single_versions()   # the last line
```

With widgets' core at 0.4.0 and the application's at 0.5.0, configure fails:

```text
CMake Warning: snicholls_core 0.4.0 at .../third_party/widgets/third_party/core is skipped: snicholls_core 0.5.0
at .../third_party/core was added first and wins. Pin every dependency that carries snicholls_core to one release.
CMake Error: More than one version of a library was reached in this build:
  snicholls_core: 0.5.0, 0.4.0
    0.5.0 at .../third_party/core
    0.4.0 at .../third_party/widgets/third_party/core
Pin every dependency that carries a library to the same release tag.
```

### The version header

Two copies of a library in one translation unit share the version header's include guard, so the guard skips the
second without a word. The header therefore starts, before the guard, with a check that stops the compile
([templates/version.hpp](templates/version.hpp)):

```cpp
#if defined(SNICHOLLS_EXAMPLE_VERSION_MAJOR) && \
    (SNICHOLLS_EXAMPLE_VERSION_MAJOR != 0 || SNICHOLLS_EXAMPLE_VERSION_MINOR != 1 || SNICHOLLS_EXAMPLE_VERSION_PATCH != 0)
#error "snicholls-example: two versions in one translation unit: 0.1.0 here, and another already included"
#endif

#ifndef snicholls_example_version_hpp
/// \cond
#define snicholls_example_version_hpp   // the guard: Doxygen does not take it for one after the check above
/// \endcond

#define SNICHOLLS_EXAMPLE_VERSION_MAJOR 0
#define SNICHOLLS_EXAMPLE_VERSION_MINOR 1
#define SNICHOLLS_EXAMPLE_VERSION_PATCH 0

#endif
```

- The macros are defined inside the guard, so the version is written out again in the block. `check_version.py`
  requires the block, before the guard, and compares its literals and the version in its `#error` text with the
  rest: a bump that forgets the block fails `check.version`.
- Doxygen no longer recognises the guard once the block stands before it, and would ask for the guard macro to be
  documented: `\cond` and `\endcond` around its `#define` keep it out.

### Link: the `odr` job

Two definitions of one entity that differ between translation units, which two versions of a library linked into
one program produce, are undefined behaviour no compiler sees alone. The library workflow's `odr` job (input
`odr_check`, default `true`) builds with GCC and link-time optimisation, where the linker sees the whole program, and
makes `-Wodr` an error. It is set in `CMAKE_CXX_FLAGS`, which the link line carries, because the warning is raised
at the link, where a target's compile options (`<prefix>WERROR`) do not reach.

## The single-include compile check

    snicholls_single_include_check(<target> [COMPILE_OPTIONS <option>...] [CXX_STANDARD <n>] [CONFIG <tooling.conf>])

It generates every `single_include.<name>` file into the build tree, again whenever a header it is made from changes,
and defines an OBJECT library with one translation unit per file, which includes it with no other include directory:
it proves the single include self-contained, as `--check` proves it complete. On a release tag the library workflow's
`single-include` job generates the files from the tagged commit, compiles each alone and attaches them to the GitHub
release (it needs `contents: write`).

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
