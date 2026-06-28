# System Architecture

[中文](architecture.zh.md)

This document defines the target architecture for `web3-opportunity-scout` as a production-grade, multi-source, stateful opportunity discovery skill.

### Goals

- ad hoc conversational requests
- follow-up questions about financing, participation, or significance
- scheduled push workflows
- user-extensible source configuration
- recovery from partial runs and source failures
- durable memory and deduplication

### Design Principles

1. Separate deterministic data work from model judgment.
2. Keep model inputs compact and structured.
3. Preserve source traceability.
4. Share one pipeline across pull and push modes.
5. Treat state as a product feature.
6. Pass artifacts source-by-source, not by whichever file was written last.
7. Use premium APIs as enrichment tiers, not indiscriminate polling surfaces.

### System Overview

```mermaid
flowchart LR
    U["User / Scheduler"] --> O["Orchestrator"]
    O --> C["Config Loader"]
    C --> S["Source Registry"]
    S --> F["Fetch Layer"]
    F --> R["Raw Cache"]
    R --> N["Normalization Layer"]
    N --> E["Entity Merge + Dedup"]
    E --> M["Memory + State Store"]
    E --> X["Compact Context Builder"]
    M --> X
    X --> J["Agent Judgment Layer"]
    J --> A["Artifacts"]
    J --> Q["Answer / Push Output"]
    M --> O
    A --> M
```

### Core Layers

- `Source Registry`: declarative source definitions
- `Fetch Layer`: source-specific collectors
- `Raw Cache`: immutable source payloads
- `Normalization Layer`: unified opportunity schema
- `Entity Merge`: canonical project identity
- `Memory + State`: deduplication, watchlists, delivery history
- `Compact Context`: model-ready evidence packets
- `Agent Judgment`: ranking, explanation, thesis

### Source Strategy

- `RootData` acts as broad project discovery and baseline project metadata.
- `BlockBeats` acts as a faster-moving Chinese signal surface that benefits from aggressive second-pass filtering.
- `DeFiLlama` acts as a free protocol/category discovery layer.
- `GitHub` acts as a builder-shipping and repo-activity layer.
- `Surf` acts as a premium enrichment layer and should be budgeted with query caps and lower cadence.
