# Host Integration

[中文](host-integration.zh.md)

This document defines the recommended boundary between `web3-opportunity-scout` and a host runtime such as Hermes or OpenClaw.

### Recommended Split

- `web3-opportunity-scout` owns collection, normalization, scoring, memory, and final artifact generation.
- Hermes or OpenClaw should own scheduling, retries at the host level, user routing, and push delivery.

### Recommended Runtime Flow

1. Host triggers `python scripts/cli.py run --source <source_id>`.
2. Skill updates `state/run-state.json` and writes the latest artifacts.
3. Host reads the preferred delivery artifact:
   - `output/briefs/latest-brief.html` for rich card-based rendering
   - `output/briefs/latest-brief.md` for markdown or plain text channels
4. Host sends the artifact through its own push surface.

### Language Selection

- `reporting.locale: auto`
  The skill infers locale from `LC_ALL`, `LC_MESSAGES`, `LANG`, then falls back to timezone.
- `reporting.locale: en`
  Force English primary artifacts.
- `reporting.locale: zh`
  Force Chinese primary artifacts.
- `reporting.locale: bilingual`
  Generate a combined markdown primary artifact in both languages.

### Why Delivery Stays Outside

- Hosts already know who should receive a push.
- Hosts usually have stronger retry, auth, routing, and observability primitives.
- Keeping delivery outside the repo makes the skill more portable across agents and runtimes.
