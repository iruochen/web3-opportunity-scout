# Source Onboarding Guide

[中文](source-onboarding.zh.md)

This guide describes how to add a new source to `web3-opportunity-scout` using the current adapter-based structure.

### Goal

A new source integration should be additive and predictable. In the common case, onboarding a source means:

1. add a source entry to `sources.yaml`
2. declare its `adapter`
3. create `scripts/fetch-<adapter>.py`
4. create `scripts/normalize-<adapter>.py`
5. verify `python scripts/cli.py fetch --source <source_id> --dry-run`
6. verify `python scripts/cli.py run --source <source_id>`

### Required Source Config Fields

- `id`
- `enabled`
- `adapter`
- `type`
- `category`
- `label`
- `cadence`
- `notes`

Optional auth fields:

- `auth.kind`
- `auth.env`
- `auth.header`

Optional request fields:

- `request.base_url`
- `request.path`
- `request.method`
- `request.headers`
- `request.query`
- `request.body`

### Adapter Naming

If the adapter is `opennews`, create:

- `scripts/fetch-opennews.py`
- `scripts/normalize-opennews.py`

### Validation Checklist

1. `python -m py_compile scripts/*.py tests/*.py`
2. `python scripts/cli.py doctor`
3. `python scripts/cli.py list-sources`
4. `python scripts/cli.py fetch --source <source_id> --dry-run`
5. live fetch with credentials if available
6. `python scripts/cli.py run --source <source_id> --skip-fetch`
7. `make test`
