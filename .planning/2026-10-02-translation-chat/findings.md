# Findings

- `translation_audit.md` 有 38 篇试译，其中 5 篇标注待核。
- 现有定位器能识别“年份/月/套 + 翻译”；`load_set_cached_only` 可只读题库缓存。
- Streamlit 已把用户消息交给 `Service.process`，无需新的交互入口。
- 38 份缓存与审计文档逐篇、逐字段对账：译文 38/38 一致，待核 5/5 一致。
- 翻译与阅读连续提问时旧 `section` 会残留；明确给出 26～55 题号时切回阅读，离线多轮测试已覆盖。
- 翻译查询只调用 `load_set_cached_only`，不会为缺缓存的卷重新 OCR 或写盘。
