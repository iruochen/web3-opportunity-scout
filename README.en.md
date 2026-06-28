# web3-opportunity-scout

`web3-opportunity-scout` is a production-oriented skill skeleton for discovering early Web3 opportunities with a repeatable pipeline instead of one-off prompt output.

The core idea is simple: noisy sources are collected deterministically, normalized into a shared project schema, compressed into compact context, and only then passed into agent judgment for ranking and thesis generation.

Architecture docs:

- Architecture index: [references/architecture.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.md:1)
- English architecture: [references/architecture.en.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.en.md:1)
- Runtime contracts: [references/contracts.en.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/contracts.en.md:1)

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/doctor.py
python scripts/init.py
python scripts/check-run-state.py
python scripts/fetch-rootdata.py --dry-run
```

## Current Scope

This repository currently includes:

- skill skeleton and configuration templates
- bilingual architecture docs
- project-local Python virtual environment workflow
- runtime state bootstrap scripts
- RootData fetcher scaffold

The next implementation stage is to validate a live RootData source with a real API key and endpoint configuration, then add normalization and ranking stages.
