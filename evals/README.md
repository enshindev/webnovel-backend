# Evals

这里是**业务内容数据仓库**（黄金集与报告），不放进 `src/`，也不打进 wheel。机制（judge、指标、闸门）在 `src/webnovel/evalkit/`。

> 分工一句话：`evalkit/` = 代码，`evals/` = 数据。

## 目录约定

```text
evals/
├── generation/
│   └── continuation/cases.jsonl
├── memory/
│   └── summary/cases.jsonl
├── quality/
│   └── review/cases.jsonl
└── cross/
    └── retrieval_generation/cases.jsonl
```

- 一级目录 = 模块名；二级 = 任务名；`cases.jsonl` 一行一条。
- **跨模块评测放 `cross/`**：一条用例同时覆盖 memory 检索 + generation 输出时，不要硬塞进某一个模块。
- 根目录由 `EVALS_DIR` 配置，默认 `evals/`。

## 一条用例

```json
{"id":"gen-001","input":{...},"expected_facts":[...],"constraints":[...],"rubric":"...","tags":["..."],"must_pass":true}
```

## 规则

- 不使用第三方版权文本；作者自有文本需脱敏。
- smoke（10 条 must-pass）每次改 prompt 跑；full（20–50 条 + judge）晋升前跑。
- 评测结果入 `eval_runs` / `eval_case_results`，报告带版本号。
- `cases.jsonl` **不写死 prompt 版本**；评测运行时由 `evalkit` 传入被测版本，结果记录 `(prompt_version, case_set_hash, model, 指标)`。
- **运行时代码不 import evalkit**；只有 CLI/CI 跑评测。
- 黄金集与 prompt 是独立评审对象：可以只改 eval case、不改 prompt；也可以只改 prompt、复用旧 case。
