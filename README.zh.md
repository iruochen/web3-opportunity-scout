# web3-opportunity-scout

`web3-opportunity-scout` 是一个面向生产环境的 Web3 早期机会发现 skill 骨架，目标不是一次性资讯摘要，而是可重复运行、可恢复、可扩展的数据流水线。

核心思路是：先对噪音来源做确定性抓取和规范化，再压缩成 compact context，最后才交给 agent 做排序、解释和 thesis 生成。

相关文档：

- 架构导航: [references/architecture.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.md:1)
- 中文架构文档: [references/architecture.zh.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.zh.md:1)
- 运行时 contract: [references/contracts.zh.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/contracts.zh.md:1)

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/doctor.py
python scripts/init.py
python scripts/check-run-state.py
python scripts/fetch-rootdata.py --dry-run
```

## 当前范围

当前仓库已经包含：

- skill 骨架和配置模板
- 中英文架构文档
- 项目级 Python 虚拟环境方案
- 状态初始化与检查脚本
- RootData 抓取器骨架

下一阶段最重要的是在拿到真实 API key 和 endpoint 配置后，先把 RootData 这一个 source 真实跑通，然后继续补 normalize 和 ranking 流水线。
