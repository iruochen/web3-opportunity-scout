# Source 接入指南

这份文档说明如何基于当前 adapter 结构，为 `web3-opportunity-scout` 新增一个数据源。

## 目标

一个新 source 的接入应该是可预期、可复制的。通常来说，新增 source 主要包括：

1. 在 `sources.yaml` 里增加一条 source entry
2. 声明它的 `adapter`
3. 创建 `scripts/fetch-<adapter>.py`
4. 创建 `scripts/normalize-<adapter>.py`
5. 验证 `python scripts/cli.py fetch --source <source_id> --dry-run`
6. 验证 `python scripts/cli.py run --source <source_id>`

## Source 配置的必要字段

每个 source entry 至少应包含：

- `id`
- `enabled`
- `adapter`
- `type`
- `category`
- `label`
- `cadence`
- `notes`

如果来源需要鉴权，应补充：

- `auth.kind`
- `auth.env`
- `auth.header`

如果来源通过 HTTP 获取，应补充 `request`：

- `base_url`
- `path`
- `method`
- 可选 `headers`
- 可选 `query`
- 可选 `body`

## Adapter 命名规则

如果 source 的 adapter 是 `opennews`，那么项目里应包含：

- `scripts/fetch-opennews.py`
- `scripts/normalize-opennews.py`

运行入口会通过 adapter 分发：

- `python scripts/cli.py fetch --source opennews_projects`
- `python scripts/cli.py run --source opennews_projects`

## Fetcher 要求

Fetcher 应该：

- 通过共享 helper 自动读取 `.env`
- 从 `sources.yaml` 读取 source entry
- 支持 `--source-id`
- 支持 `--dry-run`
- 把 raw payload 存到 `cache/<adapter>/...`
- 更新 `state/run-state.json`

## Normalizer 要求

Normalizer 应该：

- 支持 `--source-id`
- 读取最新 cache 或显式的 `--input`
- 输出统一的 opportunity record
- 把结果写到 `output/normalized/`

## 验证清单

新增 source 之后，至少应验证：

1. `python -m py_compile scripts/*.py tests/*.py`
2. `python scripts/cli.py doctor`
3. `python scripts/cli.py list-sources`
4. `python scripts/cli.py fetch --source <source_id> --dry-run`
5. 有真实 key 时做 live fetch
6. `python scripts/cli.py run --source <source_id> --skip-fetch`
7. `make test`

## 补充说明

- 优先写 source-specific 脚本，不要把所有逻辑塞进巨大条件分支
- 保留 raw source trace
- README 保持产品导向；实现细节和进展放到 `internal/`
