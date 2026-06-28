# 项目简介

`web3-opportunity-scout` 是一个面向生产环境的 Web3 早期机会发现 skill，目标是从可配置的数据源中稳定产出高价值机会线索。

它当前围绕下面几类能力设计：

- 对话式查询
- 定时推送
- 跨 run 的状态记忆与去重
- 按 source 扩展的数据接入

当前实现重点：

- 项目级 Python 虚拟环境
- 状态初始化与 run-state 跟踪
- 通过 RootData 打通第一个真实数据源
