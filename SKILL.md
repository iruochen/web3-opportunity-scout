# Web3 Opportunity Scout

Production-oriented skill for discovering early, high-signal Web3 project opportunities with resilient collection, normalization, scoring, and memory workflows.

## When To Use

Use this skill when the user asks to:

- find early Web3 projects worth tracking today or this week
- refresh opportunities in a specific ecosystem such as Solana, Base, Ethereum, or modular infra
- surface under-the-radar infra, AI x crypto, DePIN, consumer crypto, or developer tooling projects
- update an existing watchlist with new signals instead of generating generic market commentary

Example triggers:

- "Find Web3 projects worth following today"
- "Refresh Solana ecosystem opportunities"
- "Find new infra or AI x crypto projects from this week"
- "Update the watchlist with new early-stage builder signals"

## Outcome

The skill should produce durable opportunity artifacts, not just a one-off summary:

- raw source captures
- normalized project opportunities
- ranked opportunities
- project dossiers
- watchlist updates
- event memory for deduplication and cross-run continuity

## Operating Principles

1. Agent judgment is downstream of deterministic preprocessing.
   Raw or noisy source material must first be cached, normalized, and compressed before the model evaluates opportunity quality.

2. Source traces must be preserved.
   Each opportunity should retain references to the original source URLs, timestamps, and extraction notes.

3. The system must support recovery.
   Runs should distinguish between partial runs, resume runs, and force reruns. Do not assume a file existing means the step is complete.

4. Memory matters.
   Avoid treating the same project as novel every day. Reuse event memory, watchlists, and prior project dossiers to assess novelty correctly.

5. High-value output beats broad coverage.
   Favor fewer, defensible, asymmetric opportunities over generic feed summaries.

## Required Workflow

1. Load user preferences from `config.yaml` when present, otherwise fall back to `config.example.yaml`.
2. Load source definitions from `sources.yaml` when present, otherwise fall back to `sources.example.yaml`.
3. Run `scripts/doctor.py` before a full collection run when:
   - this is the first run
   - the environment changed
   - sources were edited
   - the user reports failures or missing output
4. Fetch source data into raw caches by source family.
5. Normalize each source into a shared opportunity schema.
6. Merge project entities across sources.
7. Build compact context for model evaluation.
8. Score and rank opportunities using deterministic rules plus agent judgment.
9. Update durable memory artifacts and watchlists.

## Recovery Strategy

Treat run state explicitly. A later implementation should support at least:

- `partial`: some stages completed, safe to resume remaining stages
- `resume`: continue from the latest valid checkpoint
- `force`: rerun stages even if prior outputs exist

If outputs disagree across stages, prefer re-running the inconsistent downstream stage instead of deleting all artifacts.

## User Interaction Policy

Ask the user only when the decision materially changes output quality or cost, for example:

- no chain or sector preference is configured and the search space is too broad
- a source requires credentials or manual setup
- the user needs a different risk profile such as conservative versus experimental

Otherwise proceed with defaults, state assumptions, and keep momentum.

## Configuration Contract

- `config.yaml` stores preferences and run policy, never secrets
- `sources.yaml` defines enabled sources by category, cadence, and extraction notes
- secrets, tokens, and cookies should live outside this skill and be injected by the host environment when needed

## Minimum Artifact Contract

The evolving implementation should target these outputs:

- `output/raw-opportunities.md`
- `output/ranked-opportunities.md`
- `output/project-dossiers.json`
- `state/watchlist.json`
- `state/event-memory.json`
- `state/run-state.json`

## Notes For Future Implementations

- Keep fetchers source-specific and composable
- Keep normalizers schema-first
- Prefer append-only raw caches with timestamps
- Record why an opportunity scored highly, not just the final score
