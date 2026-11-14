# Prompts

这里是**业务内容数据仓库**，不放进 `src/`，也不打进 wheel。机制（版本、label、渲染）在 `src/webnovel/llm/prompts/`。

> 分工一句话：`evalkit/` = 代码，`evals/` = 数据；`llm/prompts/` = 机制，`prompts/` = 内容。

## 目录约定

```text
prompts/
├── generation/
│   ├── continuation/v001.yaml
│   ├── continuation/labels.yaml
│   ├── rewrite/v001.yaml
│   ├── expand/v001.yaml
│   └── outline/v001.yaml
├── memory/
│   ├── summary/v001.yaml
│   └── extraction/v001.yaml
├── quality/
│   └── review/v001.yaml
└── shared/
    └── style/v001.yaml
```

- 一级目录 = 模块名（`generation` / `memory` / `quality` / `shared`）。
- 二级目录 = 任务名；`vNNN.yaml` 只追加、不改已发布版本；`labels.yaml` 是可变指针。
- 跨模块共用（文风、通用指令）放 `shared/`；引用共享片段必须锁版本（`{{> shared/style@v001}}` 或 `includes`）。
- **任务目录用 `labels.yaml` 解析版本；`shared/` 不放 `labels.yaml`，只能被 `@vNNN` 锁定引用**，否则共享片段的锁版本规则会被绕过。
- 根目录由 `PROMPTS_DIR` 配置，默认 `prompts/`；`Settings` 解析为绝对路径并校验存在。
- 版本号连续；`id` 必须等于相对路径（`generation/continuation`）；`variables` 不重复。

## 文件格式

```yaml
id: generation/continuation
version: 1
template: |
  {{> shared/style@v001}}
  你是网文作者...
  {{chapter_outline}}
variables: [chapter_outline, recent_text, instruction]
defaults:
  temperature: 0.8
  max_tokens: 2000
includes:
  - id: shared/style
    version: 1
```

`labels.yaml` 放在任务目录下，是可移动指针：

```yaml
labels:
  production: 1
  staging: 2
```

## 为什么在根目录

- prompt 的发布节奏、label、灰度、回滚与代码不同，放在 `src/` 会和 wheel 发布绑在一起。
- 版本化与评审可以独立进行；代码只引用 label，不引用文件路径。
- 每次生成记录实际解析到的 `version + content_hash`。


## 晋升

label 的变更走 CLI，不手改数据库：

```bash
uv run webnovel prompt-promote generation/continuation 2 --note "开头更稳"
```

命令会先检查该版本最近一次 eval run 是否 gate=`passed`，再改 `labels.yaml`、同步 `prompt_labels` 并写审计。`--force` 可跳过检查，`--dry-run` 只打印变更。
