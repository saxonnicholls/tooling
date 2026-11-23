# snicholls-tooling

Shared development and test tooling for the snicholls C++ libraries.

It provides:
- the build images;
- the local Ubuntu gate;
- the repository checks (tests and demos mirror the headers, versions agree, interfaces have both forms);
- reusable GitHub workflows, including documentation published to GitHub Pages;
- Docker test services: a local crypto test network, Postgres, mail and SMS sinks.

[STANDARDS.md](STANDARDS.md) is the standard these tools enforce.

Status: being assembled for v0.1.0.

Licence: MIT ([LICENSE](LICENSE)).
