# Security policy

<!-- From snicholls-tooling's templates/SECURITY.md (STANDARDS section 6). Replace <...> and delete this comment. -->

## Reporting a vulnerability

Please report a vulnerability privately, never in a public issue or pull request:

- through GitHub's **private vulnerability reporting** on this repository (Security, then "Report a vulnerability"), or
- by email to <security contact address>.

Include what you found, how to reproduce it (a minimal input or test case), the version or commit, and its impact as
you understand it. Please give us the time below to fix it before you disclose it.

## Supported versions

| Version | Supported |
|---|---|
| the latest release (`vX.Y.Z`) | yes: fixes are released as a new patch or minor version |
| older releases | no: upgrade to the latest release |
| `main` between releases | best effort |

Every library is pinned by tag across the family, so a fix reaches its consumers as a release and a pin bump.

## What to expect

| Step | Within |
|---|---|
| acknowledgement of your report | 3 working days |
| our assessment (confirmed or not, and its severity) | 10 working days |
| a fix released, for a confirmed high or critical issue | 30 days, sooner where we can |
| public disclosure, coordinated with you, with credit if you want it | after the fix is released |

## Scope

In scope: this repository's code, its build and its released artefacts (including a release's single include).
Out of scope: third-party dependencies (report those upstream; tell us too if this repository is affected), and test
keys and fixtures, which are synthetic by rule and never used outside tests.
