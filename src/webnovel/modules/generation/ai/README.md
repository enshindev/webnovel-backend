# Generation 的上下文组装代码

这里**只放上下文组装代码**，不放 prompt / 黄金集内容，也不属于 `llm/` 平台机制：

- 具体 prompt 在根 `prompts/generation/`；这里不重复放内容。
- `context.py`：把人物、设定、伏笔、最近原文组装成 `ContextSegment` 的业务逻辑。
- 黄金集在根 `evals/generation/`；这里不重复放数据。

`llm/` 只提供预算、压缩、渲染、gateway、judge 等机制；`ai/` 只放组装逻辑。
