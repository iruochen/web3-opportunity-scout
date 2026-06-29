# 贡献指南

[English](CONTRIBUTING.md)

感谢你一起完善 `web3-opportunity-scout`。

## 基本原则

- 先做确定性预处理，再交给模型判断。
- 优先走配置驱动的 source 接入方式。
- 不要提交任何 secret。
- 统一使用项目自己的 `.venv`。
- Git 提交尽量小步、聚焦。

## 常规流程

1. 创建并激活 `.venv`。
2. 用 `pip install -r requirements.txt` 安装依赖。
3. 运行 `.venv/bin/python scripts/doctor.py`。
4. 尽量用最小改动解决一个明确问题。
5. 运行最相关的验证命令。
6. 提交 PR 时写清楚摘要、风险和测试说明。

## 验证命令

```bash
.venv/bin/python -m py_compile scripts/*.py tests/*.py
make test
.venv/bin/python scripts/doctor.py
```

如果改了 adapter、抓取逻辑或评分逻辑，还要补跑最相关的 fetch / normalize / pipeline 命令。

## Source 接入

新增 source 时，建议至少完成以下内容：

- 在 `sources.example.yaml` 里补 source 定义
- 仅在本地测试需要时修改 `sources.yaml`
- 实现 `scripts/fetch-<adapter>.py`
- 实现 `scripts/normalize-<adapter>.py`
- 保证 raw cache 和 normalized records 可检查
- 如果行为变化影响用户，记得同步更新文档
