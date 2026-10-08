# 代码底层审查与同类项目调研

## Goal
基于当前真实代码链路，找出值得优先改进的底层问题，并用成熟开源项目的做法校验建议；本轮只审查，不修改产品代码。

## Phases
- [complete] 1. 盘点依赖、入口、核心调用链和数据结构
- [complete] 2. 检查状态、题目定位、检索、生成、轨迹与测试边界
- [complete] 3. 调研同类 GitHub 项目的已验证模式
- [complete] 4. 输出按优先级排序的最小改进方案
- [complete] 5. 深读 echo-kaoyan-english-skill，修正 Agentic 判断并与本项目对照
- [complete] 6. 对照现有实现，划分 Agentic 改造中的保留、小改、删除和新增部分
- [complete] 7. 复核 Claude 的反对意见，确定 Agentic 改造时机而非永久取消
- [complete] 8. 复核 DeepSeek 的合并意见，校正测试基线、相对指代与轨迹 schema 决策

## Next Step

下一施工轮：删除改写器及全部遗留接口，用正向契约测试锁住用户原话；对相对移动指令先明确反问；维持 29 项基线并新增测试。之后推进讲解质量、答案闸门和评测。

## Constraints
- 不保留已废弃路径，不设计兼容层。
- 只推荐能解决当前真实问题的最小改动。
- 区分代码证据、测试证据与外部项目经验。

## Errors Encountered
- 初次读取 planning-with-files 技能时路径少了一层目录；已通过搜索定位正确安装路径。
- 当前工作目录不是 Git 根，`git diff` 无法用于校验计划文件；改用直接读取关键行确认写入结果。
- 首次 `rg` 命令使用了 PowerShell 不接受的 `*.md` 路径参数且引用了不存在的 `core/`；已改为 `-g` 过滤并以当前目录为搜索根。
- 沙箱内运行 `.venv` 因 WindowsApps 访问限制误报 Python 不存在；沙箱外复核后 Python 3.11.9 正常，测试为 29 passed、1 warning。先前“虚拟环境损坏”判断已撤回。
