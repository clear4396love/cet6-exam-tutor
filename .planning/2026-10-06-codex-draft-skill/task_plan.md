# Codex 作文/翻译练习入口

## Goal

将现有的作文、翻译出题、保存、评阅、修订和历史能力接入 cet6-tutor Skill 的本地 CLI；不引入 MCP，不改确定性阅读内核。让 Streamlit 测试与当前简版演示界面一致。

## Current Phase

1. 研究现有接口、数据安全边界与测试 — complete
2. 测试先行实现 CLI 闭环 — complete
3. 更新并验证 Skill 指令 — complete
4. 对齐简版 Streamlit 测试并跑全量验证 — complete

## Next Step

完成；交付命令入口、Skill 路由和验证结果。

## Constraints

- 所有写入测试使用临时学习档案，真实本机记录不可改变。
- 不自动展示参考范文/译文；用户明确确认后才使用参考材料入口。
- Codex 聊天记录是交互体验，本机学习档案才是稿件与评阅事实来源。
- 不添加 MCP 或新的存储层。
