# Findings

- 既有 Service 提供 draft_question、submit_draft、review_draft、draft_history、reference_material。
- 既有 Skill CLI 只有 ask 和 progress；写作/翻译提交仍被 Skill 指向 Streamlit。
- 当前 Streamlit 是简版聊天/阅读界面，旧 UI 测试含已移出的稿件功能。
- CLI 可以只包装既有 Service：task 不含参考内容；submit 从 UTF-8 文件读稿并保存后评阅；history 显式查原稿/评语；review 重试；reference 需要显式确认。
- `Service.review_draft` 已保证先保存后调 DeepSeek，失败时返回 pending，可重试；`LearningRecord` 以 submission_id 去重，修订用 revision_of 关联。
- 本环境两个项目 `.venv` 的 Python 启动器都指向缺失的基础解释器；已尝试常规路径与 uv 已安装列表，尚无可运行解释器。需在 RED/验证步骤继续寻找，若仍无则如实报告无法运行。
- 通过 Windows Python 注册表找到系统已安装解释器，并临时设置 `PYTHONPATH` 指向现有父虚拟环境的 site-packages；无需安装或修改环境即可测试。
- 旧 Streamlit 测试中的稿件 UI/侧栏聊天测试对应已移出简版页面的功能；服务层已有保存、重试、历史和审核门槛测试，新增 CLI 测试覆盖 Codex 入口。
