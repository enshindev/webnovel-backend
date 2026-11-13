# LLM 机制层

`llm/` 只放**可复用的机制**，不放网文特有的内容。

> 分工一句话：`evalkit/` = 代码，`evals/` = 数据；`llm/prompts/` = 机制，`prompts/` = 内容。

| 子包 | 职责 |
| --- | --- |
| `gateway/` | `ModelClient` 门面、provider adapter、路由、错误归一化 |
| `context/` | 预算、压缩、渲染、manifest；定义 `ContextSource` 端口 |
| `prompts/` | prompt 版本、label、渲染机制；`resolve` + `load_includes`（include 锁版本） |
| `retrieval/` | 通用检索机制：RRF、向量/BM25/重排（不决定取哪些人物/伏笔） |
| `guardrails/` | profile 框架、注入检测、审核策略 |
| `telemetry/` | `gen_ai.*` span；基于 `infra.observability` 的 tracer，不另起一套 |

边界：

- `llm/` **不 import `modules/`**；`ContextSource` 由 memory 模块实现。
- **机制 vs 内容**：具体「续写/大纲/润色」提示词与黄金集放在根 `prompts/`、`evals/`，按模块分子目录；上下文组装代码放在 `modules/<name>/ai/`。都不放这里。
- **离线 vs 运行时**：judge、指标、评测闸门在 `evalkit/`；黄金集数据在 `evals/` 或 `modules/<name>/ai/evals/`；运行时代码不 import `evalkit/`。
- 语音 / 多模态（ASR/TTS/封面）不进 `llm/`，留在 `experiments/`；以后若成核心能力，再加 `speech/` 等兄弟目录。
- provider 只依赖 `kernel` 与第三方库；配置由 entrypoint 注入。
