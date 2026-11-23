# snicholls-tooling

The development and test tooling of the snicholls libraries, held once for all of them:
- the build images;
- the local gate (`test_ubuntu.sh`), derived build images, and the standard make targets (`make/tooling.mk`);
- the checks (`check_mirror.py`, `check_version.py`, `check_interfaces.py`, the header-standalone CMake function);
- the reusable CI workflows (the library workflow with documentation to GitHub Pages, images);
- the Docker test services (planned): Postgres, mail, an SMS sink, TURN, a log hub, and later a crypto test network;
- the templates for a new library (`new_library.py`), `SECURITY.md` and threat models;
- Markdown to PDF.

**`STANDARDS.md` is the family standard.** Every repository follows it, and the tools here enforce it. Change a
standard and its check in the same commit.

## What belongs here (MUST)

- **Tooling used by more than one repository.** A test service that only one repository uses stays in that repository
  until a second one needs it.
- **Nothing that a library includes or links.** Repositories pin this one as a test-only submodule
  (`third_party/tooling`), the way they pin GoogleTest.
- **It pins none of the family's libraries,** so it can never create a cycle.
- **Every tool is parameterised, never copied.**
  - A script takes the repository's name, include root, namespace and guard prefix as arguments or from a small config
    file in the calling repository.
  - A repository that needs a variant adds an option here.

## Public (MUST)

This repository is public, so anything committed - files and commit messages - is written for anyone to read:
- no names of private repositories or products;
- no local absolute paths;
- no credentials;
- no personal data: mail services start empty, and the test network uses only the published development keys,
  labelled as such.

## Authorship and commits

Commits are authored by the repository owner and carry **no AI attribution**: no `Co-Authored-By` trailers, no
"Generated with" lines, in commit messages, pull request descriptions, files, README or this file. Every source file
starts with the banner

    #
    #  <name>
    #  snicholls-tooling
    #
    #  Copyright 2010-2026 Saxon Herschel Nicholls
    #

## Tests (MUST)

- **Every tool has a test,** run in CI:
  - each check runs against a fixture repository that passes and one that fails for each rule;
  - every image is built from scratch;
  - every Compose profile starts and passes its smoke test: a transfer and a token deploy on each chain, a query on
    each database, a mail and an SMS sent and captured.
- **The workflows are tested by calling them** from this repository's own CI.

## Versions

- Semantic versioning, a release tag `vX.Y.Z` on a green commit, and `v0.1.0` first.
- Repositories pin a tag and move together, as with every other dependency.
- Base images are referenced by digest, and the digests are published with each release.

## First release (v0.1.0)

Built from the best of the copies the family has today. The base is snicholls-core's:
- `docker/ubuntu` and `docker/ubuntu-26.04`;
- `scripts/test_ubuntu.sh`, `check_mirror.py` and `check_version.py`;
- the header-check CMake.

Each repository's own copy is compared against core's, and whatever it does better is taken in. Then each repository
deletes its copies and pins `v0.1.0`, in one change per repository.
