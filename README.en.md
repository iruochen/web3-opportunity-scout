# web3-opportunity-scout

`web3-opportunity-scout` is a production-oriented skill for discovering early Web3 opportunities from configurable data sources.

The project is built around a repeatable pipeline:

- fetch source data
- cache raw payloads
- normalize project records
- merge repeated entities
- score opportunities
- produce ranked outputs and watchlists

It is designed for both:

- interactive chat queries
- scheduled recurring opportunity digests

Key docs:

- Architecture index: [references/architecture.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.md:1)
- English architecture: [references/architecture.en.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.en.md:1)
- Runtime contracts: [references/contracts.en.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/contracts.en.md:1)
- Source onboarding: [references/source-onboarding.en.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/source-onboarding.en.md:1)

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/cli.py doctor
python scripts/cli.py init
python scripts/cli.py list-sources
python scripts/cli.py run --source rootdata_projects
```

Or use the bundled `Makefile`:

```bash
make venv
make install
make doctor
make list-sources
make pipeline
make test
```

This creates:

- raw cache files under `cache/`
- normalized, merged, and scored artifacts under `output/`
- ranked markdown summaries
- bilingual opportunity briefs
- per-project thesis files
- watchlist and run-state updates under `state/`

## Config

- `config.yaml` controls focus chains, sectors, scoring thresholds, and state directories
- `sources.yaml` controls enabled sources and source-specific request settings
- each source can declare an `adapter`, which maps the source entry to its fetch/normalize implementation
- secrets such as API keys should be provided through environment variables
- `.env.example` shows the expected variable names for local setup
- `scripts/cli.py` automatically loads variables from `.env` when the file exists

## Output

Main user-facing outputs:

- `output/ranked-opportunities.md`
- `output/raw-opportunities.md`
- `output/briefs/latest-brief.en.md`
- `output/briefs/latest-brief.zh.md`
- `output/project-theses/`
- `output/project-dossiers.json`
- `state/watchlist.json`
- `state/project-dossiers.json`
