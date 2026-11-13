# Knowledge

`ideation` 的创作方法内容仓库，不放进 `src/`，也不打进 wheel。

```text
knowledge/
├── craft/          # 开篇、钩子、节奏、人物弧光、世界规则
├── genre/          # 题材模式、读者期待、常见雷点
└── sources.yaml    # 来源、许可证、日期
```

- 每条知识带 `source / license / date`；过期内容标「未核实」。
- 不直接复用 `webnovel-full-pipeline` 的 48 份知识库：许可证不明、口径旧。
- 市场/榜单数据只接受作者主动导入或公开可授权数据；不抓番茄。
- 运行时由 `ideation` 的 RAG 检索；`src/` 不得依赖本目录。
