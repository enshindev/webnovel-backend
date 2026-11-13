# 业务模块

每个模块只从 `contract.py` 暴露公开接口；跨模块只能 import 这个文件。

## 已有（S1）

| 模块 | 职责 |
| --- | --- |
| `works` | 作品生命周期、归属 |
| `chapters_versions` | 章节、不可变版本、乐观锁 |
| `generation` | 生成任务、状态机、草稿、采纳 |
| `settings` | 应用配置 |

## 后续（按切片生长，不预建）

| 模块 | 切片 | 职责 |
| --- | --- | --- |
| `memory` | S2/S3 | 抽取、变更建议、设定、摘要、向量、业务检索选择、故事状态图 |
| `library` | S5 | 作者私有资料库：上传、解析、检索、引用 |
| `analysis` | S3 | 反向大纲、旧稿结构分析 |
| `style` | S3/S4 | 文风声纹：profile、样本、声纹检查 |
| `quality` | S3 | 机检、审稿、评测运行 |
| `workflow` | S3+ | 多步创作流程编排、阶段与人工卡点 |
| `export` | S3 | 导出任务与下载 |
| `usage` | S4 | token / 成本台账 |

## 内部结构

- 简单模块：`contract.py` + `service.py` + `repository.py` + `models.py` + `http.py`
- 复杂模块：再加 `domain/`（纯逻辑）、`application/`（用例）、`adapters/`（repo/http/models）
- 业务 AI 代码：`ai/` 只放上下文组装；prompt 与黄金集在根 `prompts/`、`evals/`，不要塞进 `llm/`

规则：`domain` 不依赖框架；`application` 只依赖 `domain` + `contract` + ports；`http` 只依赖 `contract`。机制在 `llm/`；`evalkit/` = 代码，`evals/` = 数据；prompt/黄金集在根级，不放进模块。
