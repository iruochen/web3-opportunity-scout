# Source Onboarding Guide

This guide describes how to add a new source to `web3-opportunity-scout` using the current adapter-based structure.

## Goal

A new source integration should be additive and predictable. In the common case, onboarding a source means:

1. add a source entry to `sources.yaml`
2. declare its `adapter`
3. create `scripts/fetch-<adapter>.py`
4. create `scripts/normalize-<adapter>.py`
5. verify `python scripts/cli.py fetch --source <source_id> --dry-run`
6. verify `python scripts/cli.py run --source <source_id>`

## Required Source Config Fields

Every source entry should include:

- `id`
- `enabled`
- `adapter`
- `type`
- `category`
- `label`
- `cadence`
- `notes`

When the source requires auth, include:

- `auth.kind`
- `auth.env`
- `auth.header`

When the source is fetched over HTTP, include a `request` block with:

- `base_url`
- `path`
- `method`
- optional `headers`
- optional `query`
- optional `body`

## Adapter Naming

If the source uses adapter `opennews`, the project should contain:

- `scripts/fetch-opennews.py`
- `scripts/normalize-opennews.py`

The runtime entrypoints route through the adapter:

- `python scripts/cli.py fetch --source opennews_projects`
- `python scripts/cli.py run --source opennews_projects`

## Fetcher Expectations

The fetcher should:

- load `.env` automatically through shared helpers
- read the source entry from `sources.yaml`
- support `--source-id`
- support `--dry-run`
- store raw payloads under `cache/<adapter>/...`
- update `state/run-state.json`

## Normalizer Expectations

The normalizer should:

- support `--source-id`
- read the latest cache or an explicit `--input`
- emit unified opportunity records
- write outputs under `output/normalized/`

## Validation Checklist

Before merging a new source:

1. `python -m py_compile scripts/*.py tests/*.py`
2. `python scripts/cli.py doctor`
3. `python scripts/cli.py list-sources`
4. `python scripts/cli.py fetch --source <source_id> --dry-run`
5. live fetch with credentials if available
6. `python scripts/cli.py run --source <source_id> --skip-fetch`
7. `make test`

## Notes

- Prefer source-specific code over giant conditional branches
- Preserve raw source traces
- Keep the public README product-facing; put implementation notes in `internal/`
