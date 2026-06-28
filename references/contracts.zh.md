# 运行时 Contract

这份文件定义了下一阶段实现应该遵循的最小运行时 contract。

## Opportunity Record

建议字段：

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

`state/run-state.json` 建议至少记录：

- run 级元数据
- source 级抓取状态
- stage checkpoint
- 最近一次成功产物的位置
- active run 的生命周期

当前 bootstrap 结构：

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

当前 pipeline run 至少应该记录这些字段：

- `run_id`
- `status`
- `source_id`
- `started_at`
- `finished_at`
- `current_stage`
- `completed_stages`
- `error`

## Memory Objects

- `state/event-memory.json`：历史观测到的项目和信号
- `state/watchlist.json`：仍然值得持续跟踪的项目
- `state/delivery-log.json`：已经推送过的结果
- `state/project-dossiers.json`：项目级累计证据
