# Contributing

[中文](CONTRIBUTING.zh.md)

Thanks for helping improve `web3-opportunity-scout`.

## Principles

- Keep deterministic preprocessing ahead of model judgment.
- Prefer configuration-driven source onboarding.
- Do not commit secrets.
- Use the project-local `.venv`.
- Keep commits small and focused.

## Typical Flow

1. Create and activate `.venv`.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `.venv/bin/python scripts/doctor.py`.
4. Make the smallest change that cleanly solves one problem.
5. Run the most relevant validation steps.
6. Open a pull request with a short summary, risks, and test notes.

## Validation

```bash
.venv/bin/python -m py_compile scripts/*.py tests/*.py
make test
.venv/bin/python scripts/doctor.py
```

Run the most relevant source-specific fetch / normalize / pipeline command when changing adapters or scoring logic.

## Source Contributions

When adding a new source:

- add the source to `sources.example.yaml`
- add the local version to `sources.yaml` only when needed for local testing
- implement `scripts/fetch-<adapter>.py`
- implement `scripts/normalize-<adapter>.py`
- keep raw caches and normalized records inspectable
- update user-facing docs when behavior changes
