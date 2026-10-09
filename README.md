# CET-6 本机学习助手

这是一个源码公开的本机英语六级学习项目。它把题目定位、缓存读取和客观题判分留在 Python 确定性代码中；模型只参与意图判断、讲解和作文/翻译语言评阅。入口包括 Streamlit 页面和仓库内的 Codex Skill（`.agents/skills/cet6-tutor/`）。

## 安装与验证

在项目根目录使用 Python 3.11 创建环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.demo_synthetic
.\.venv\Scripts\python.exe -m tools.demo_synthetic --answer B
.\.venv\Scripts\python.exe -m pytest -q
```

仓库另附 `examples/synthetic_paper.json`，它是完全虚构的离线演示，**不是六级真题，也不是官方答案**。不提交答案时，练习视图不包含正确选项；提交后由代码判分。真实题目从仓库附带的 38 套 `parsed_papers/*.json` 缓存读取，不需要 PDF 或 OCR 文件。
如果 Windows 终端的中文输出乱码，可先运行 `$env:PYTHONIOENCODING='utf-8'`。

## 查询与讲解

本仓库附带 38 套人工整理的真题缓存（题干、原文、答案及部分参考内容），但**不附带任何真题或 OCR PDF，也不附带 OCR Markdown/JSON 中间产物**。各套板块覆盖不完全；未收录、待核或数据不完整的题目会按项目降级规则说明，不能保证每套每题都可回答。缓存格式见 [parsed_papers/README.md](parsed_papers/README.md)。现有解析脚本不能保证从任意 PDF 自动还原完整缓存。

安装依赖后，可以查询已收录题目：

```powershell
.\.venv\Scripts\python.exe -m tools.cet6_skill ask '2024年12月第1套第44题选什么'
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

在 Codex 中打开此仓库，可按 `.agents/skills/cet6-tutor/SKILL.md` 使用 Skill。它调用本项目代码，并不是独立托管的题库服务。完整 AI 讲解或语言评阅需要使用者在本机设置自己的 `DEEPSEEK_API_KEY`；没有密钥时，离线演示、纯函数测试和缓存上的确定性判分仍不依赖模型。聊天问答可能退回代码定位，不能把它描述成零配置的完整八节讲解。

## 本机数据与边界

作文和翻译原稿默认保存在当前用户的本机学习档案；可用绝对文件路径环境变量 `EXAM_TUTOR_LEARNING_PATH` 改位置。聊天与测试轨迹也只应留在本机。`.gitignore` 排除了 `databases/`、`episodes/`、运行评测轨迹、`.env` 与本机规划文件，**没有排除真题缓存**。发布前检查 `git status` / `git ls-files`：缓存及其中的参考内容可能涉及第三方权利；请自行确认是否有权公开分发，不要加入个人原稿。

评测方法与局限见 [eval/CET6_SKILL_EVAL.md](eval/CET6_SKILL_EVAL.md)。仓库不附 LICENSE；源码可阅读，但不因此自动授予复用或再分发权限。
