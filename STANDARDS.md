# The family standards

This is the one copy of the standards that every repository in the snicholls family follows. A repository's
`CLAUDE.md` points here and does not restate them. Where a repository needs an exception, its `CLAUDE.md` names it.
Where this file is silent, snicholls-core's `CLAUDE.md` is the reference.

Each standard is enforced by a check or a reusable workflow in this repository, not by convention. A standard without
a check is a defect in tooling. Every check reads the repository's `tooling.conf`; the README says how to adopt them.

## 0. How we write C++

These are the principles behind every rule below. When a rule is unclear, these decide.

**Decide at compile time whatever can be decided there.**
- Everything that is known before the program runs is computed by the compiler:
  - tables, maps and perfect hashes in `consteval` constructors;
  - sizes as template parameters;
  - shapes, sparsity patterns and dispatch decisions as types.
- Functions are `constexpr` wherever the language allows, and what can be checked is checked with `static_assert`, so a
  misuse is a compile error with a message that names the problem, not a run-time surprise.
- The run-time hot path is what is left: a lookup, a few arithmetic operations, a loop over plain data.

**Strong interfaces, several implementations.**
- **Interfaces.** A capability is an interface first: a concept and its pure virtual twin (section 3), in standard
  types, in the lowest repository that can state it.
- **Implementations.** They are plug-and-play: a reference implementation on the standard library alone, then the fast
  ones (SIMD, GPU with CUDA and OpenCL both, an external library behind an adapter).
- **Choosing.** The caller chooses one by type (`solve<osqp>(problem)`), or at run time through the virtual form.
- **Checking.** Every implementation passes the same conformance kit, and they are benchmarked against each other.
- **Dependence.** Callers depend on the interface, never on an implementation.

**Strong types.**
- **Domain values.** Use vocabulary types, not loose primitives:
  - a UTC instant, not an `int64`;
  - an amount with its currency, not a `double`;
  - an E.164 number, not a string;
  - a 256-bit integer for on-chain amounts.
- **Construction.** It is explicit, and narrowing is rejected.
- **Expected failure is a value:** `result<V, E>`, never a `bool` plus an out-parameter, and exceptions only for the
  unexpected.
- **`noexcept`** is exact: conditional where it depends on the parameters, and never on anything that can allocate.

**Zero overhead.**
- An abstraction costs nothing over the hand-written equivalent, and that is proven, not assumed:
  - layout contracts as `static_assert`s (`sizeof`, `alignof`, triviality);
  - a like-for-like benchmark against the hand-written code, with a fairness check that refuses to run if the two
    disagree.
- No allocation, virtual call or type erasure on a hot path unless the design asks for run-time choice.

**Dispatch on types with overload sets and concepts, never with `if constexpr` chains.**
- Use concept-constrained overloads, `first_match{...}` for ordered cases, and `overloaded{...}` for disjoint ones.
- Use type lists for algorithms over types, and `constexpr_for` for loops over values.

**Ready for accelerators.**
- Compute primitives are pure `constexpr` functions over spans of plain, trivially copyable data, with no allocation in
  the inner loop.
- Partial results that `merge`, so a reduction can run in parallel.
- Randomness by stream or by index, so a seed reproduces on every machine.
- Fixed-size forms (sizes known at compile time, bounded loops, no recursion) where hardware synthesis may want them.

**Clean, idiomatic, short.**
- Modern standard C++ (C++20), header-only where possible, standard library first.
- The shortest correct implementation; readable headers and fast compiles over completeness.
- Each header includes exactly what it uses, the lightest standard header that serves; heavy parts go in their own
  headers.
- No macros where a template or `constexpr` works; no raw `new`; no owning raw pointers; RAII for every resource.
- `const` and value semantics by default; references for parameters that must not be null; `std::span` and
  `std::string_view` for views.
- Names say what a thing is, in lower_snake, as the standard library does.

**Always a demo, tests and a benchmark.**
- Every public entity has:
  - **tests:** the success path, edge cases (empty, nested, boundary values), error paths, and every `constexpr` and
    `noexcept` claim as a `static_assert`;
  - **a demo:** it shows the use, exits non-zero when the result is wrong, and supplies the documentation's examples;
  - **a benchmark:** anything with a run-time footprint has one, with a fairness check, against the hand-written code
    and against the best-known libraries.
- A change without its tests, demo and benchmark is not done.

**Test against known libraries wherever possible.**
- **Independent implementations.** Agreement with an independent implementation is the strongest evidence, so every
  result that one can check is checked against one, for example:
  - OpenSSL, libsecp256k1, libsodium and the Rust and JavaScript stacks for cryptography;
  - Python's `decimal`, `datetime`, NumPy, SciPy and SymPy for numerics and time;
  - CVXPY for optimisation;
  - Stone Soup for tracking;
  - LAPACK and Eigen for linear algebra.
- **Fixtures.** Reference values are generated by a pinned script from the independent implementation, committed as
  fixtures, and checked by a CTest that fails if they drift. They are never generated from our own output.
- **Differential fuzzing** compares us with the reference on random input wherever both can run in one process.

## 1. Code is written once

- Every function, type, script, Dockerfile and workflow exists in exactly one repository.
- **Search first.** Before writing anything, search the family. If the thing exists, use it. If it does not, add it to
  the repository that owns it, with its test and demo, release that repository, and bump the pin.
- **A copy is a defect.** That includes a copy in a demo, a test, a `utils/` folder or a script.
- **When copies are found,** the best one wins: compare correctness, tests, API and measured speed. It takes in what the
  others did better, and the others are deleted in the same change.
- Pins point toward the foundation library, snicholls-core, and never away from it: a repository depends only on
  repositories below it.

## 2. One version of every dependency

- **Tags only.** Each dependency, ours or third-party, is a submodule in `third_party/`, pinned to a release tag over
  HTTPS with `shallow = true`.
- **Never** a branch tip, an untagged commit, a vendored copy, or `FetchContent` of a branch.
- **One version across the family.** Every repository that uses a library pins the same tag.
- **One owner.** A third-party library has one owning repository, normally its adapter; the others reach it through
  that owner.
- **Bumps.** Each bump is a commit of its own: `third_party: bump <name> <old> -> <new>`.
- **Version checks.** Semantic versions are written in three places: the version header, `project(... VERSION)` and
  the tag. `check_version.py` fails if they disagree. It runs as the CTest `check.version`, and with
  `--tag <tag>` before a release is tagged.
- **Releases.** A release is a tag on a commit where every blocking CI leg is green. A repository's first release is
  `v0.1.0`.

## 3. Interfaces: a concept and its virtual twin

- **Two forms.** Every capability is declared twice, with the same operations:
  - a **concept**, for static dispatch, which is the default;
  - a **pure virtual interface**, for choice at run time.
- **Adapters both ways.** A model of the concept is usable through the virtual interface, and an implementation of the
  virtual interface models the concept.
- **Mirrored headers.**
  - Every pure virtual interface in `interfaces/<capability>.hpp` has its concept in `concepts/<capability>.hpp`. The
    adapters sit with the interface.
  - The reference implementation and the conformance kit are headers of their own beside them.
- **Unit tests for both:**
  - `tests/concepts/<capability>_test.cpp` proves at compile time that the reference implementation and the adapters
    model the concept, and that non-conforming types do not;
  - `tests/interfaces/<capability>_test.cpp` runs the conformance kit through both forms.
- **One conformance kit** tests both forms.
- **Neither form exists alone.** `check_interfaces.py` fails on:
  - a class with pure virtual functions that has no concept twin;
  - a capability concept that has no virtual twin.

  It also fails when either form lacks its unit test. It runs as the CTest `check.interfaces`.
- **Standard types only.** Interfaces use standard C++ types. The interface lives in the lowest repository that can
  state it; implementations live where their dependencies are.

## 4. Documentation

- **C++: Doxygen,** with warnings as errors, in this order for each header, class or major function:
  1. `\brief`;
  2. overview;
  3. relationships (`\see`, `\ingroup`);
  4. implementations;
  5. guarantees (thread safety, exception safety, complexity, ownership, invariants);
  6. errors (`\throws`);
  7. examples (`\snippet` from a compiled demo, never hand-copied code);
  8. performance (numbers with platform, build type and date, or "not benchmarked");
  9. tests and demos;
  10. dependencies;
  11. known issues;
  12. status.
- **Files** start with the copyright banner, then `/// \file`, `\brief` and `\ingroup`, and `\ingroup` stands on a line
  of its own.
- **TypeScript: TSDoc,** in the same sections.
- **Published.** The documentation is published to GitHub Pages on every push to `main` and every release tag, by the
  library workflow with `pages: true` (tooling's README, "The library workflow"), and the README links to it.
- **Tests and demos mirror the sources.** `include/<lib>/<area>/<name>.hpp` has `tests/<area>/<name>_test.cpp` and
  `demos/<area>/<name>_demo.cpp`. A demo exits non-zero when its result is not what it documents. `check_mirror.py`
  enforces this, as the CTest `check.mirror`.
- **Exception:** ts-moveables keeps its own documentation approach.

## 5. Docker containers

- **Base images.** Every image starts `FROM` one of this repository's base images, pinned by digest. No repository
  writes a base image of its own. A build image a repository needs is derived from a standard one and named in its
  `tooling.conf`; `build_image.sh --check` refuses any other (tooling's README, "Derived images").
- **The build images** are this repository's Ubuntu 24.04 and 26.04 images:
  - GCC 13 and 15;
  - Clang 18 with compiler-rt, so Clang's sanitizers link;
  - CMake and Ninja;
  - the pinned Doxygen.

  `scripts/build_image.sh <image>` builds them locally, and each release publishes them as
  `ghcr.io/saxonnicholls/<image>:<version>` for amd64 and arm64. A Node image for the web and mobile builds is the
  next to come.
- **Service images:**
  - built in stages;
  - run as a non-root user;
  - a read-only root filesystem where the service allows;
  - no secret in any layer (build secrets through `--secret`);
  - a `HEALTHCHECK`;
  - the OCI labels.
- **CI** produces an SBOM and a vulnerability scan for every image, and builds every image from scratch.
- **Compose:**
  - one file per stack, with services grouped into profiles;
  - a network per stack;
  - names `<repository>-<service>`;
  - every port and secret taken from the environment.
- **The local gate** is macOS plus `test_ubuntu.sh`, which builds each configuration fresh in the build image with
  warnings as errors: GCC and Clang, Release and Debug, and AddressSanitizer with UBSan.
  - It is run as `third_party/tooling/scripts/test_ubuntu.sh`, or with `--quick` for one configuration; `make ubuntu`
    and `make test-werror` come from `make/tooling.mk` (tooling's README, "The make targets").
  - The repository's `tooling.conf` names its CMake options; the README lists the eight configurations.
- **Test services** are Compose profiles in this repository, each with a smoke test in CI:
  - later, a crypto test network: development Ethereum chains with a fixed genesis, Tron, and Bitcoin regtest;
  - Postgres;
  - a catch-all mail server;
  - an SMS sink;
  - TURN;
  - a log hub.

## 6. Security model

- **Secrets live in `.credentials/`, one `.env` file per service:**
  - for example `.credentials/postgres.env` or `.credentials/sms.env`;
  - `.credentials/*` and `*.env` are git-ignored;
  - each file has a committed template, `.credentials/<service>.env.example`, which lists the keys with no values.
- **Configuration** is read from those files in development and from the key store in production.
- **Nothing secret in git:**
  - secret scanning runs in CI and in a pre-commit hook;
  - a leaked secret is rotated, not just removed.
- **Nothing secret in a log:** values that must not be printed are wrapped so that they are masked; format arguments
  are printed as given, so a secret never goes into context text.
- **Keys** are used only through constant-time code from the family's cryptography library, held under custody by a
  KMS or a signer, and never in application code.
- **Authentication:**
  - OAuth 2.1 with PKCE for web and mobile;
  - short-lived access tokens, JWTs signed ES256 or EdDSA;
  - rotating refresh tokens with revocation;
  - JWKS published and rotated.
- **Transport:** TLS everywhere outside a single host.
- **CI** is the library workflow (tooling's README, "The library workflow"), which holds these rules:
  - `permissions:` least privilege per job;
  - third-party actions pinned by commit SHA;
  - no secrets exposed to pull requests from forks.
- **Testing:**
  - sanitizers on every build;
  - libFuzzer on every parser;
  - differential tests against independent reference implementations wherever one exists.
- **Releases:** release tags are signed.
- **Each repository:**
  - has a `SECURITY.md` from `templates/SECURITY.md`, covering how to report, the supported versions and the response
    times;
  - has a threat model per service (`templates/THREAT_MODEL.md`).
- **No personal data** in a repository or a fixture. Test data is synthetic.
- **Development keys are test keys:** the published development mnemonics, never funded on a real chain, and never used
  outside the test network.

## 7. Commits and naming

- Commits are authored by the repository owner and carry no AI attribution: no `Co-Authored-By` trailers and no
  "Generated with" lines, in commits, pull requests or files.
- Naming follows the Boost and standard-library style:
  - lower_snake for types, functions and files;
  - CamelCase template parameters;
  - macros with the library's prefix;
  - named header guards, which `snicholls_header_check()` (`cmake/SnichollsTooling.cmake`) checks as it compiles each
    header on its own, twice.
- Public repositories name nothing private: no private repository, product, person, credential or local path.
