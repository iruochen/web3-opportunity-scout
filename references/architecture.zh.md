# System Architecture

[English](architecture.md)

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
6. 中间产物必须按 source 接力，不能谁最后写文件就读谁。
7. 额度型 API 主要做 enrichment，不应该拿来无差别高频轮询。

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

### Source 分层策略

- `RootData` 负责广义项目发现和基础项目元信息。
- `BlockBeats` 负责更快的中文信号面，适合配合较强的二次筛选。
- `DeFiLlama` 负责免费协议发现和赛道分类。
- `GitHub` 负责 builder 持续交付和 repo 活跃度信号。
- `Surf` 负责高级 enrichment，应该通过 query 上限和较低 cadence 控制额度消耗。
