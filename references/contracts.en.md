# Runtime Contracts

This file captures the minimum runtime contracts that the next implementation stages should follow.

## Opportunity Record

Suggested fields:

```text
id
entity_key
source_id
source_type
project_name
project_url
summary
category
chains
tags
signals
published_at
observed_at
confidence
raw_ref
status
```

## Run State

`state/run-state.json` should track:

- run metadata
- source-level fetch status
- stage checkpoints
- last successful outputs

Current bootstrap shape:

```json
{
  "version": 1,
  "updated_at": "2026-06-28T00:00:00Z",
  "active_run": null,
  "last_completed_run": null,
  "runs": [],
  "sources": {}
}
```

## Memory Objects

- `state/event-memory.json`: previously observed projects and signal history
- `state/watchlist.json`: projects that remain worth tracking
- `state/delivery-log.json`: previously delivered push artifacts
- `state/project-dossiers.json`: accumulated project-level evidence
