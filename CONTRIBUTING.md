# Contributing to MATRiX

Thank you for helping improve MATRiX. This repository contains public
documentation and GitHub Release metadata/assets for the Linux simulator.
The Unreal Engine source project is maintained separately, so open an issue
before starting a change that requires engine-source modifications.

## Before you start

1. Search existing issues and pull requests for related work.
2. Use an issue template for bugs, features, or documentation problems.
3. For a substantial or cross-repository change, agree on scope with a
   maintainer before implementation.
4. Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Development environment

Documentation changes do not require the full simulator. For runtime-related
documentation, verify claims against the v1.0.13 Linux package and its
corresponding source. The simulator requires Linux x86_64 and a working GPU
driver; ROS 2 is optional. Ubuntu 22.04 is required only by the separately
downloaded external motion controller.

Before submitting a documentation pull request, check local Markdown links,
balanced code fences, version strings, Linux paths, and commands copied from
the release tools' `--help` output. Include the validation method in the pull
request.

## Change guidelines

- Keep each pull request focused on one problem.
- Use Linux paths and commands for the public v1.0.13 documentation.
- Treat the root `VERSION` file as the repository release version.
- Keep archive-part names and SHA-256 values synchronized with GitHub Release
  assets.
- Do not document a tool, map, controller, or dependency as bundled unless it
  is present in the published package.
- Add comments for invariants, side effects, non-obvious compatibility logic,
  and cleanup behavior. Do not add comments that merely restate a command.
- Update both English and Chinese documentation when user-facing behavior
  changes.

For changes to repository boundaries or release workflows,
confirm the intended scope and validation plan with a maintainer before coding.

## Pull requests

A pull request should contain:

- the user-visible problem and proposed behavior;
- linked issues, when applicable;
- validation commands and results;
- rollback or compatibility notes for release/runtime changes;
- documentation updates for changed interfaces.

Maintainers may request that large changes be split so review and rollback
remain practical.
