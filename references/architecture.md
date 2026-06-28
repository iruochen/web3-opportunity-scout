# System Architecture

[English](#english) | [中文](#zh)

<a id="english"></a>
## English

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

---

<a id="zh"></a>
## 中文

这份文档定义了 `web3-opportunity-scout` 的目标架构：一个面向生产环境、支持多数据源、带持久状态的 Web3 早期机会发现 skill。

### 目标

- 支持临时对话式查询
- 支持围绕融资、参与角度、意义的继续追问
- 支持定时推送
- 支持用户通过配置扩展 source
- 支持部分失败、补跑恢复
- 支持持久记忆和去重

### 设计原则

1. 确定性数据处理和模型判断分层。
2. 模型输入保持紧凑和结构化。
3. 每条机会线索都可追溯。
4. pull 和 push 共享同一套流水线。
5. 状态层是产品能力，不是附属实现。

### 系统总览

```mermaid
flowchart LR
    U["用户 / 调度器"] --> O["Orchestrator"]
    O --> C["配置加载层"]
    C --> S["Source Registry"]
    S --> F["抓取层"]
    F --> R["原始缓存层"]
    R --> N["规范化层"]
    N --> E["实体合并与去重"]
    E --> M["记忆与状态存储"]
    E --> X["Compact Context 构建层"]
    M --> X
    X --> J["Agent 判断层"]
    J --> A["产物层"]
    J --> Q["回答 / 推送输出"]
    M --> O
    A --> M
```

### 核心分层

- `Source Registry`：声明式 source 定义
- `抓取层`：source-specific collector
- `原始缓存层`：不可变 source payload
- `规范化层`：统一 opportunity schema
- `实体合并层`：canonical project identity
- `记忆与状态层`：去重、watchlist、delivery history
- `Compact Context`：模型可消费的证据包
- `Agent 判断层`：排序、解释、thesis
