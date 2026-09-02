# Contributing to MATRiX

Thank you for helping improve MATRiX. This repository contains the public
runtime, launch tooling, configuration, and documentation for the simulator.
The Unreal Engine source project is maintained separately, so please open an
issue before starting a change that requires engine-source modifications.

## Before you start

1. Search existing issues and pull requests for related work.
2. Use an issue template for bugs, features, or documentation problems.
3. For a substantial or cross-repository change, agree on scope with a
   maintainer before implementation.
4. Report vulnerabilities privately according to [SECURITY.md](SECURITY.md).

By participating, you agree to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Development environment

The supported runtime environment is Ubuntu 22.04 with ROS 2 Humble. A full
simulation run additionally requires the GPU and release assets documented in
the README. Documentation, configuration, and most script checks can be run
without installing the full simulator.

Run the lightweight checks before submitting a pull request:

```bash
find scripts src -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
python3 -m py_compile scripts/validate_xml_contract.py scripts/ci/check_repo.py
python3 scripts/ci/check_repo.py
```

For runtime-affecting changes, also run the relevant environment check and
include the command and result in the pull request:

```bash
bash scripts/check_env.sh runtime
bash scripts/check_env.sh custom --custom-urdf /path/to/robot.urdf
```

## Change guidelines

- Keep each pull request focused on one problem.
- Preserve `set -euo pipefail` in strict Bash entry points unless there is a
  documented compatibility reason not to.
- Quote paths and user-provided values. Avoid broad process matching or
  recursive filesystem operations when tracked PIDs or exact paths suffice.
- Put reusable release helpers in `scripts/release_manager/common.sh`.
- Treat the root `VERSION` file as the only default release version. A future
  release may be tested with an explicit version argument, but must not add a
  second hard-coded default.
- Add comments for invariants, side effects, non-obvious compatibility logic,
  and cleanup behavior. Do not add comments that merely restate a command.
- Update both English and Chinese documentation when user-facing behavior
  changes.

For changes to repository boundaries, script ownership, or release workflows,
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
