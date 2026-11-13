# quality（S3）

机检 + 审稿 + 评测运行：

- 确定性机检（字数、缺章、格式、AI 味）。
- LLM 审稿（八维评分、P0/P1/P2）。
- 评测运行：调用 `evalkit` 只能发生在 CLI/CI；运行时质量检查走 `llm.gateway` 与规则，不 import `evalkit`。

目录先占位，S3 落代码。
