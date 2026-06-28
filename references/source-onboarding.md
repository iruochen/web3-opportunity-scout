# Source Onboarding Guide

[English](#english) | [中文](#zh)

<a id="english"></a>
## English

This guide describes how to add a new source to `web3-opportunity-scout` using the current adapter-based structure.

### Goal

A new source integration should be additive and predictable. In the common case, onboarding a source means:

1. add a source entry to `sources.yaml`
2. declare its `adapter`
3. create `scripts/fetch-<adapter>.py`
4. create `scripts/normalize-<adapter>.py`
5. verify `python scripts/cli.py fetch --source <source_id> --dry-run`
6. verify `python scripts/cli.py run --source <source_id>`

### Required Source Config Fields

- `id`
- `enabled`
- `adapter`
- `type`
- `category`
- `label`
- `cadence`
- `notes`

Optional auth fields:

- `auth.kind`
- `auth.env`
- `auth.header`

Optional request fields:

- `request.base_url`
- `request.path`
- `request.method`
- `request.headers`
- `request.query`
- `request.body`

### Adapter Naming

If the adapter is `opennews`, create:

- `scripts/fetch-opennews.py`
- `scripts/normalize-opennews.py`

### Validation Checklist

1. `python -m py_compile scripts/*.py tests/*.py`
2. `python scripts/cli.py doctor`
3. `python scripts/cli.py list-sources`
4. `python scripts/cli.py fetch --source <source_id> --dry-run`
5. live fetch with credentials if available
6. `python scripts/cli.py run --source <source_id> --skip-fetch`
7. `make test`

---

<a id="zh"></a>
## 中文

这份文档说明如何基于当前 adapter 结构，为 `web3-opportunity-scout` 新增一个数据源。

### 目标

一个新 source 的接入应该是可预期、可复制的。通常来说，新增 source 主要包括：

1. 在 `sources.yaml` 里增加一条 source entry
2. 声明它的 `adapter`
3. 创建 `scripts/fetch-<adapter>.py`
4. 创建 `scripts/normalize-<adapter>.py`
5. 验证 `python scripts/cli.py fetch --source <source_id> --dry-run`
6. 验证 `python scripts/cli.py run --source <source_id>`

### Source 配置的必要字段

- `id`
- `enabled`
- `adapter`
- `type`
- `category`
- `label`
- `cadence`
- `notes`

可选鉴权字段：

- `auth.kind`
- `auth.env`
- `auth.header`

可选请求字段：

- `request.base_url`
- `request.path`
- `request.method`
- `request.headers`
- `request.query`
- `request.body`

### Adapter 命名规则

如果 adapter 是 `opennews`，应创建：

- `scripts/fetch-opennews.py`
- `scripts/normalize-opennews.py`

### 验证清单

1. `python -m py_compile scripts/*.py tests/*.py`
2. `python scripts/cli.py doctor`
3. `python scripts/cli.py list-sources`
4. `python scripts/cli.py fetch --source <source_id> --dry-run`
5. 有真实 key 时做 live fetch
6. `python scripts/cli.py run --source <source_id> --skip-fetch`
7. `make test`
