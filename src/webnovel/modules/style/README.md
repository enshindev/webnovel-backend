# style（S3/S4）

文风声纹：从作者样章提取 profile，生成时约束，草稿后检查。

- 设计：[docs/backend/VOICE_FINGERPRINT.md](../../../../docs/backend/VOICE_FINGERPRINT.md)
- 表：`style_profiles`、`style_samples`、`style_checks`。
- 先做确定性特征 + 作者确认；LLM 只做定性解释。
- 不提供“模仿某作家”，只学作者自己的样章。
- S3 实现，先占位。
