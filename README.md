# CET-6 本机学习助手

这是一个源码公开的本机英语六级学习项目。它把题目定位、缓存读取和客观题判分留在 Python 确定性代码中；模型只参与意图判断、讲解和作文/翻译语言评阅。入口包括 Streamlit 页面和仓库内的 Codex Skill（`.agents/skills/cet6-tutor/`）。

## 先运行无需真题的演示

在项目根目录使用 Python 3.11 创建环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.demo_synthetic
.\.venv\Scripts\python.exe -m tools.demo_synthetic --answer B
.\.venv\Scripts\python.exe -m pytest -q
```

演示使用 `examples/synthetic_paper.json` 中完全虚构的短文和题目，**不是六级真题，也不是官方答案**。不提交答案时，练习视图不包含正确选项；提交后由代码读取示例中的答案并判分。测试在没有私有语料时跳过明确标记为 `local_corpus` 的集成检查；其余测试仍会运行。
如果 Windows 终端的中文输出乱码，可先运行 `$env:PYTHONIOENCODING='utf-8'`。

## 使用自己的资料

本仓库**不分发真题 PDF、OCR 产物、试卷正文、整套答案缓存、参考译文或范文**。评测定义中保留了少量用于断言的题号与预期字母，并非可用题库。真实题目需要用户自行取得有权使用的材料，并在本机生成或放入 `parsed_papers/<年>_<月>_<套>.json`。字段说明见 [parsed_papers/README.md](parsed_papers/README.md)。现有解析脚本只能处理部分版式与板块，不能保证从任意 PDF 自动还原完整、已核对的缓存；使用前须人工核对题干、段落和 KEYS。缓存缺失或无法核验时，系统应报告不可用，不会猜答案。

有自己的缓存后，可以运行：

```powershell
.\.venv\Scripts\python.exe -m tools.cet6_skill ask '2024年12月第1套第44题选什么'
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

在 Codex 中打开此仓库，可按 `.agents/skills/cet6-tutor/SKILL.md` 使用 Skill。它调用本项目代码，并不是独立托管的题库服务。需要模型讲解或语言评阅时，在本机设置 `DEEPSEEK_API_KEY`；没有密钥时，离线演示、纯函数测试及可用缓存上的确定性判分不依赖模型。真实 Skill/界面的题目功能仍依赖本机缓存。

## 本机数据与边界

作文和翻译原稿默认保存在当前用户的本机学习档案；可用绝对文件路径环境变量 `EXAM_TUTOR_LEARNING_PATH` 改位置。聊天与测试轨迹也只应留在本机。`.gitignore` 排除了 `databases/`、`parsed_papers/*.json`、`episodes/`、运行评测轨迹、`.env` 与本机规划文件。发布或分享前仍应检查 `git status` / `git ls-files`，不要把个人原稿或有版权的资料加入版本控制。

评测方法与局限见 [eval/CET6_SKILL_EVAL.md](eval/CET6_SKILL_EVAL.md)。仓库不附 LICENSE；源码可阅读，但不因此自动授予复用或再分发权限。
