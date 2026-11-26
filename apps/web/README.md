# Web Prototype

这是前端原型，不是生产前端。

- `studio.html` / `studio.js` / `studio.css`：覆盖作品、章节、生成候选、故事状态、反向大纲、资料库、导出和用量。
- 启动 API 后打开 `http://<host>:<port>/app/studio.html`。
- 如果只开静态页面，页面会显示“未连接后端”，不会假装有数据。
- `ENABLE_EXPERIMENTS=true` 时资料库、多模态导出等实验接口才可用。

快速启动：

```bash
uv run uvicorn webnovel.entrypoints.api.app:create_app --factory --reload
```
