# 检索机制

`llm/retrieval/` 只放**与业务无关的检索机制**：

- `fusion.py`：RRF 融合（纯函数）。
- 以后加 `vector.py`、`bm25.py`、`rerank.py`。

**不放在这里**：人物/设定/伏笔的选取规则、章节 chunk 策略、context 业务组装——这些属于 `modules/memory`（记忆模块）。
