# Initialization Flow

This document describes the intended first-run and resume behavior for `web3-opportunity-scout`.

## First Run

1. Verify Python is available.
2. Run `python3 scripts/doctor.py`.
3. Copy `config.example.yaml` to `config.yaml` if no user config exists.
4. Copy `sources.example.yaml` to `sources.yaml` if no source config exists.
5. Edit preferences:
   - chains
   - sectors
   - timezone
   - risk profile
6. Edit source enablement:
   - disable sources you do not trust
   - disable sources requiring credentials until configured
7. Create working directories if missing:
   - `cache/`
   - `output/`
   - `state/`
8. Run the fetch and normalize pipeline once the source scripts exist.

## Resume Run

The future pipeline should:

1. inspect `state/run-state.json`
2. determine the latest successful checkpoint
3. reuse valid upstream artifacts
4. rerun only downstream or failed stages
5. append new event memory rather than replacing it wholesale

## Force Run

Use a force run when:

- source parsing logic changed
- normalization schema changed
- scoring logic changed
- cached source data is corrupted or stale

Force mode should preserve previous artifacts for audit when practical, but rebuild the active outputs.

## Configuration Priority

Recommended precedence:

1. local runtime flags
2. `config.yaml`
3. `config.example.yaml`

Likewise for source definitions:

1. `sources.yaml`
2. `sources.example.yaml`

## Early Failure Policy

For initial iterations:

- fail loudly on broken repository structure
- warn, rather than fail, when optional configs are missing
- allow disabled or unavailable sources when `skip_unavailable_sources` is true
