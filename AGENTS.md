# AGENTS

This file captures the working rules for contributors and coding agents in this repository.

## Mission

Build `web3-opportunity-scout` as a production-grade, multi-source Web3 opportunity discovery system that is:

- configurable
- extensible
- stateful
- resumable
- usable in both interactive and scheduled workflows

## Core Engineering Rules

1. Deterministic preprocessing comes before model judgment.
   Fetching, parsing, normalization, deduplication, checkpointing, and state persistence should be code-first and repeatable.

2. Source onboarding must stay configuration-driven.
   Adding a source should primarily mean:
   - add a source entry in `sources.yaml`
   - add a source-specific fetch adapter
   - add a source-specific normalizer or mapping rule
   - follow the adapter onboarding guide in `references/source-onboarding.md`

3. Never store secrets in tracked files.
   API keys, tokens, cookies, and credentials must come from environment variables or local untracked overrides.

4. Use the project-local Python environment.
   Prefer `.venv/bin/python` and `.venv/bin/pip` over global Python tooling.

5. State is mandatory.
   New pipeline steps should preserve or extend:
   - `state/run-state.json`
   - `state/event-memory.json`
   - `state/watchlist.json`
   - `state/delivery-log.json`
   - `state/project-dossiers.json`

6. Design for resume and partial success.
   A failed downstream step must not destroy successful upstream artifacts.

7. Keep outputs inspectable.
   Raw payloads, normalized records, scoring outputs, and summaries should be saved in machine-readable forms whenever practical.

8. Make small, meaningful Git commits.
   Do not wait until the end of a long session to commit unrelated work together.

## Documentation Rules

- Keep short docs in both English and Chinese when they are user-facing.
- Prefer single-file bilingual docs with anchor-based switching when practical.
- Use relative Markdown links so docs stay portable on GitHub.
- Prefer:
  - `README.md`
  - `docs/*.md`
  - `references/*.md`

## Code Organization Rules

- Shared script helpers belong in `scripts/common.py`
- Fetchers should be named `scripts/fetch-*.py`
- Normalizers should be named `scripts/normalize-*.py`
- Run-state and initialization helpers should stay scriptable from CLI
- Avoid burying source-specific logic inside general-purpose files

## Quality Bar

Before considering a change ready:

- run `python -m py_compile scripts/*.py` when Python files changed
- run `python scripts/doctor.py`
- run the most relevant script path for the changed component
- prefer dry-run support for source integrations before live execution

## 中文说明

这个文件用于约束本项目里 agent 和开发者的协作方式。

### 核心要求

1. 先做确定性处理，再交给模型判断。
   抓取、解析、规范化、去重、状态落地这些环节必须尽量可重复、可恢复。

2. 来源接入必须可扩展。
   新增 source 时，优先通过 `sources.yaml` + `fetcher` + `normalizer` 的组合扩展，而不是直接改 prompt。

3. 任何 secret 都不能写进版本库。
   API key、token、cookie 一律走环境变量或本地未跟踪文件。

4. 统一使用项目自己的 `.venv`。

5. 状态层不是可选项。
   新功能需要兼容 `run-state`、`event-memory`、`watchlist`、`delivery-log`、`project-dossiers` 这些状态对象。

6. 允许部分成功，支持补跑恢复。
   下游失败不能破坏上游已经成功产生的产物。

7. 输出要可检查。
   raw payload、normalized records、score 结果、summary 最好都能落成可读文件。

8. Git 提交要小步进行。
   不要把完全不同的改动堆到最后一次性提交。
