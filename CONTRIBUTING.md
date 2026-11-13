# 贡献指南

## 开发流程

1. `uv sync --all-extras`
2. `docker compose up -d postgres redis`
3. `cp .env.example .env`，填模型配置；`cp config/pricing.example.yaml config/pricing.yaml`
4. `uv run alembic upgrade head`
5. `make dev` / `make worker`

## 提交前

```bash
make fmt
make lint
make test
```

## 架构约束

- `entrypoints` 是唯一组合根；业务模块不 import FastAPI / arq。
- `kernel` 只依赖标准库；`llm` 不依赖 `modules`；`infra` 不依赖 `modules`。
- 跨模块只能 import 对方的 `contract.py`。
- 业务模块内部：`domain` 纯逻辑，`application` 用例，`adapters` 框架/IO。
- 较大的架构或接口变更请先开 Issue 讨论。

## 代码风格

- Python 3.12，类型标注；Ruff + mypy strict。
- 公共接口用 `Protocol`；只在「至少两个 adapter」时建端口。
- 错误用领域异常，HTTP 层映射为 RFC 9457 Problem。
- ORM：Mapped、DTO 分离、Repository 返回领域对象、显式 join。
- 不在日志/trace 里落正文。
