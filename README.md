# snicholls-tooling

Shared development and test tooling for the snicholls C++ libraries.

It provides:
- the build images: `docker/ubuntu-24.04` (GCC 13, Clang 18 with compiler-rt, CMake, Ninja, Doxygen) and
  `docker/ubuntu-26.04` (GCC 15), built with `scripts/build_image.sh <image>` and published to
  `ghcr.io/saxonnicholls/<image>`;
- the local Ubuntu gate, `scripts/test_ubuntu.sh`;
- the repository checks: `scripts/check_mirror.py` (tests and demos mirror the headers), `scripts/check_version.py`
  (versions agree), `scripts/check_interfaces.py` (interfaces have both forms), and `cmake/SnichollsTooling.cmake`
  (every header compiles on its own, behind its named guard);
- reusable GitHub workflows, including documentation published to GitHub Pages (planned);
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

4. The local gate is `make test-werror` on the Mac plus, from the repository's root:

       third_party/tooling/scripts/test_ubuntu.sh

Then delete the repository's own copies of these scripts, its `docker/` build images and its `header_check.cpp.in`.

## tooling.conf

One `key = value` per line. `#` at the start of a line or after a space begins a comment. Lists are separated by
spaces and are not quoted. Flags are `yes` or `no`. A key appears once. Python, bash and CMake read it the same way.

| Key | Used by | Meaning |
|---|---|---|
| `name` | gate | the repository's name in the report (default: its directory) |
| `include_dir` | all | the include directory (default `include`) |
| `include_root` | all | the public headers, e.g. `include/snicholls/core` (required) |
| `namespace` | interfaces | concepts and interfaces are declared in it, or in one nested in it |
| `guard_prefix` | header check | each header's guard is `<guard_prefix><path under include_root>` as an identifier, e.g. `snicholls_core_meta_concepts_hpp` |
| `macro_prefix` | version | `<macro_prefix>VERSION_MAJOR`, `_MINOR` and `_PATCH` (required) |
| `cmake_project` | version | `project(<cmake_project> VERSION x.y.z)` (required) |
| `option_prefix` | gate | the CMake options `<prefix>WERROR`, `<prefix>SANITIZE`, `<prefix>BUILD_DOCS`, `<prefix>BUILD_BENCHMARKS` (required) |
| `umbrella` | mirror | the umbrella header, which needs no test or demo |
| `docs`, `benchmarks` | gate | whether the repository has them (default `no`) |
| `configurations` | gate | a subset of the eight configurations (default: all) |
| `cmake`, `cmake.<config>` | gate | more CMake arguments for every configuration, or for one |
| `extra.<label>` | gate | `<image> <cmake arguments>`: a configuration of the repository's own |
| `env` | gate | `KEY=value` pairs for the builds and the tests |
| `setup` | gate | a shell command run in each container before the configurations |
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

    python3 -m unittest discover -s tests -v    # the checks, the CMake module and the gate's plan (CMake, a C++20 compiler)
    tests/gate_test.sh                          # the gate in Docker: the fixture passes all eight, planted UB fails
                                                # exactly the three sanitizer configurations
    tests/image_smoke.sh                        # inside an image: what the gate needs is there

`tests/fixtures/good` is a small repository that passes every check. Each test breaks one rule in a copy of it.
CI (`.github/workflows/tools.yml`) runs all of them on Linux and macOS, with shellcheck over every script.
