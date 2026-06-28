# web3-opportunity-scout

`web3-opportunity-scout` 是一个面向生产环境的 Web3 早期机会发现 skill，用来从可配置的数据源中稳定产出高价值项目机会线索。

项目围绕一条可重复运行的流水线构建：

- 抓取来源数据
- 缓存原始 payload
- 规范化项目记录
- 合并重复实体
- 机会评分
- 输出排序结果和 watchlist

它同时服务于：

- 对话式查询
- 定时机会推送

相关文档：

- 架构导航: [references/architecture.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.md:1)
- 中文架构文档: [references/architecture.zh.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/architecture.zh.md:1)
- 运行时 contract: [references/contracts.zh.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/contracts.zh.md:1)
- Source 接入指南: [references/source-onboarding.zh.md](/Users/ruochen/CodexProjects/web3-opportunity-scout/references/source-onboarding.zh.md:1)

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/cli.py doctor
python scripts/cli.py init
python scripts/cli.py list-sources
python scripts/cli.py run --source rootdata_projects
```

也可以直接使用仓库自带的 `Makefile`：

```bash
make venv
make install
make doctor
make list-sources
make pipeline
make test
```

执行后会生成：

- `cache/` 下的原始缓存
- `output/` 下的 normalized / merged / scored 产物
- 排序后的 Markdown 机会清单
- 中英文机会简报
- 项目级 thesis 文件
- `state/` 下的 watchlist 和 run-state

## 配置

- `config.yaml` 控制关注链、赛道、评分阈值和状态目录
- `sources.yaml` 控制启用哪些 source 以及每个 source 的请求配置
- 每个 source 都可以声明一个 `adapter`，用于映射到对应的 fetch / normalize 实现
- API key 等 secret 通过环境变量提供，不写入仓库
- `.env.example` 展示了本地运行时需要配置的环境变量名称
- 当 `.env` 存在时，`scripts/cli.py` 会自动加载其中的环境变量

## 用户输出

主要用户可读产物包括：

- `output/ranked-opportunities.md`
- `output/raw-opportunities.md`
- `output/briefs/latest-brief.en.md`
- `output/briefs/latest-brief.zh.md`
- `output/project-theses/`
- `output/project-dossiers.json`
- `state/watchlist.json`
- `state/project-dossiers.json`
