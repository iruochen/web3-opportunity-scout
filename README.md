# web3-opportunity-scout

`web3-opportunity-scout` is a production-oriented skill skeleton for discovering early Web3 opportunities with a repeatable pipeline instead of one-off prompt output.

The core idea is simple: noisy sources are collected deterministically, normalized into a shared project schema, compressed into compact context, and only then passed into agent judgment for ranking and thesis generation.

Language docs:

- English architecture: [references/architecture.en.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.en.md:1)
- 中文架构文档: [references/architecture.zh.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.zh.md:1)

## Design Goals

- surface early, high-signal projects rather than generic market news
- support stable reruns, partial recovery, and explicit run state
- keep cross-day memory so the same project is not repeatedly treated as new
- make source coverage configurable without rewriting prompts
- separate deterministic preprocessing from model reasoning

## Architecture

The intended architecture mirrors a reliable collection-and-analysis system:

1. Source fetch layer
2. Normalization layer
3. Compact context layer
4. Agent evaluation layer
5. Artifact and state management layer

The full system design, interaction model, scheduling model, and data flow are documented in [references/architecture.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.md:1).

## Repository Layout

```text
web3-opportunity-scout/
├── SKILL.md
├── README.md
├── config.example.yaml
├── sources.example.yaml
├── prompts/
│   ├── project-thesis-template.md
│   └── summary-template.md
├── references/
│   ├── init-flow.md
│   └── scoring-rules.example.md
├── scripts/
│   └── doctor.py
└── tests/
```

More fetch, normalize, merge, score, and state scripts can be added incrementally as the pipeline matures.

## Key Concepts

### Opportunity Schema

All sources should eventually normalize into a shared schema with fields such as:

- `id`
- `source`
- `project_name`
- `url`
- `summary`
- `category`
- `chain`
- `signals`
- `published_at`
- `confidence`
- `status`

### Scoring

The baseline scoring model emphasizes:

- `novelty`: is this meaningfully new to the system or watchlist
- `traction`: is there evidence of real shipping, usage, funding, or builder activity
- `asymmetry`: is the upside high relative to current attention

These should combine into an `opportunity_score` with documented reasoning.

### State

This project should eventually track:

- raw caches per source
- normalized outputs per stage
- run checkpoints
- project entity memory
- watchlist changes over time

## Quick Start

1. Create and activate the project virtual environment
2. Install dependencies from `requirements.txt`
3. Copy `config.example.yaml` to `config.yaml`
4. Copy `sources.example.yaml` to `sources.yaml`
5. Edit preferences and source enablement
6. Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/doctor.py
```

The doctor script validates the skeleton, checks for expected files, and gives setup guidance before fetchers are added.

## Current Status

This repository currently provides:

- the skill contract in `SKILL.md`
- configuration and source templates
- initialization and scoring references
- bilingual architecture docs
- a minimal doctor script
- a project-local Python virtual environment workflow

It does not yet include live source fetchers, normalization pipelines, scoring executables, or persistent state orchestration.

## Next Recommended Additions

- `scripts/init.py`
- `scripts/check-run-state.py`
- `scripts/fetch-github-projects.py`
- `scripts/fetch-defillama.py`
- `scripts/normalize-source.py`
- `scripts/merge-project-entities.py`
- `scripts/score-opportunities.py`
- `scripts/build-summary-context.py`
