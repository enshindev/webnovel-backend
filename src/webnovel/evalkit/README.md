# evalkit

**离线**评测工具包：judge、指标、闸门、报告。运行时代码**禁止** import 本包。

> 分工一句话：`evalkit/` = 代码，`evals/` = 数据。

- 输入：根级 `evals/` 的黄金集（`evals/<module>/<task>/cases.jsonl`，跨模块 `evals/cross/...`）；用例 schema 在 `schema.py`（`EvalCaseSpec`，`extra=forbid`）。
- 输出：`eval_runs` / `eval_case_results` + 版本化报告。
- 只允许 `entrypoints.cli` 与 CI 调用；`api` / `worker` / `modules` / `llm` / `infra` 不得依赖。

这样 gateway / context / guardrails 等运行时代码不会把 judge、黄金集、评测依赖带进生产路径。
