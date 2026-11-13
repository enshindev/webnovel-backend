# 跨模块评测

一条用例同时覆盖多个模块时放这里，例如：

- `retrieval_generation/`：memory 检索到的片段是否让 generation 写出正确设定。
- `extraction_writeback/`：抽取建议 → 确认 → 后续生成是否带上新设定。
- `workflow_review/`：多步流程的交付物是否通过质量闸门。

约定：用例的 `input` 写明涉及的模块与版本；`expected` 写跨模块的可观察结果，不写内部实现。
