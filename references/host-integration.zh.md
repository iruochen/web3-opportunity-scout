# Host Integration

[English](host-integration.md)

这份文档定义了 `web3-opportunity-scout` 和 Hermes / OpenClaw 这类宿主运行时之间更合理的边界。

### 推荐分工

- `web3-opportunity-scout` 负责抓取、规范化、评分、记忆层和最终产物生成。
- Hermes 或 OpenClaw 负责调度、宿主级重试、用户路由和消息推送。

### 推荐运行流程

1. 宿主触发 `python scripts/cli.py run --source <source_id>`。
2. Skill 更新 `state/run-state.json` 并写出最新产物。
3. 宿主读取希望投递的产物：
   - `output/briefs/latest-brief.html` 适合富卡片展示
   - `output/briefs/latest-brief.md` 适合 Markdown 或纯文本渠道
4. 宿主使用自己的推送能力完成投递。

### 语言选择

- `reporting.locale: auto`
  先根据 `LC_ALL`、`LC_MESSAGES`、`LANG` 推断语言，再用时区兜底。
- `reporting.locale: en`
  强制英文主产物。
- `reporting.locale: zh`
  强制中文主产物。
- `reporting.locale: bilingual`
  生成中英合并的主 Markdown 产物。

### 为什么把推送放在外部

- 宿主本身更清楚内容要推给谁。
- 宿主通常已经具备更好的重试、鉴权、路由和可观测能力。
- 把 delivery 层留在仓库外部，可以让 skill 更容易复用到不同 agent 和 runtime 中。
