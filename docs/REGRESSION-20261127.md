# Regression baseline — isolated environment (2026-11-27)

> Status: **pass** (L1 unit/offline only). This report records the Learning
> environment fix and the resulting test evidence. It is not a ROS, simulation
> or hardware validation.

## 1. Root cause

The host interpreter had none of the project runtime dependencies. `pyarrow`
is a required dependency (`pyproject.toml:12`, `pyarrow==24.0.0`), and the
`uv.lock` pins it, but the host Python 3.12 environment did not have it. Five
test modules failed at collection with `ModuleNotFoundError: pyarrow`.

A second, independent pitfall: `uv run pytest` resolved the system `pytest`
executable, so it ran under the host interpreter. The correct invocation is
`uv run --frozen --extra test python -m pytest`, which uses the project
environment.

## 2. Environment

| Item | Value |
|---|---|
| Interpreter | Python 3.12.3 |
| Isolated env | `/tmp/jcheng-learning-venv` (outside the repository) |
| Sync command | `uv sync --frozen --extra test --python 3.12` |
| Test command | `uv run --frozen --extra test --python 3.12 python -m pytest tests -q` |
| Lock | `uv.lock` sha256 `a866bfd19d1750faba90b51dd0d7b93e2ce720d1f78b66617a9deec54ba013e7` |
| pyarrow | 24.0.0 |
| pytest | 8.3.4 |

No `pyproject.toml` or `uv.lock` change; no system-Python install; no sudo;
no dependency upgrade.

## 3. Result

```text
68 passed in 1.83s
Repository gate OK: document set, manifest, no LICENSE, no secrets,
no weights, no recordings, links resolve
```

Gate command: `UV_PROJECT_ENVIRONMENT=/tmp/jcheng-learning-venv bash scripts/check_repo_gate.sh`.

Evidence summary: [`evidence/20261127_regression/summary.txt`](../evidence/20261127_regression/summary.txt).

## 4. What this proves / does not prove

**Proves**

- The locked dependency set installs with `--frozen` on Python 3.12.3.
- The repository's 68 offline tests pass in an isolated environment.
- The repository gate passes when pointed at the isolated environment.

**Does not prove**

- ROS 2 Humble build or runtime behavior (host has Jazzy only).
- Gazebo or any simulation behavior.
- Dataset quality, policy quality or hardware behavior.
- Any real-robot claim. No robot was started and no motion was sent.

## 5. Residual issues

- The CI job must use `python -m pytest` (not the bare `pytest` executable) to
  avoid the interpreter mismatch. The repository gate already does.
- The isolated env is ephemeral (`/tmp`); it is not committed and not a
  reproducible artifact by itself. The lock file is the reproducible input.
- If a future lock update removes a wheel for Python 3.12, the sync will fail
  closed; do not edit the lock to force it.

## Related

- [Dataset contract](m1/04-DATA-CONTRACT.md)
- [Acceptance](../ACCEPTANCE.md)
- [Boundary specification](https://github.com/JCHENG-Robotics/.github/blob/main/docs/repo-boundaries.md)
