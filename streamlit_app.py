"""六级真题讲解助手的最小 Streamlit 界面。"""
import streamlit as st


st.set_page_config(
    page_title="六级真题讲解助手",
    page_icon=":material/school:",
    layout="centered",
)

st.title("六级真题讲解助手")
st.caption(
    "目前支持段落匹配（第 36～45 题）和仔细阅读（第 46～55 题）的讲解，"
    "选词填空（第 26～35 题）的查答案，以及翻译参考译文和逐句解析。"
)

with st.expander("怎么提问才能得到完整讲解？"):
    st.markdown(
        """
**第一次提问要写清年份、月份、套数和题号：**

- `2024年12月第1套第43题为什么这样选？`
- `2024年12月第1套第43题为什么不选A？`
- `2020年7月第1套第49题为什么不选D？`
- `2024年12月第1套翻译解析`

**当前会话已经定位到题目后，可以直接追问：**

- `这题怎么选？`
- `为什么不选B？`
- `那27题呢？`

> 短问法只适用于当前会话已经定位成功；刷新页面后请重新提供完整定位。

段落匹配题和仔细阅读题只问“选什么”会得到简短答案；使用“为什么”“解析”“怎么选”等问法，
会得到包含题目陷阱、原文、翻译、题干分析、错误答案对比和复盘的八节讲解。

选词填空（第 26～35 题）目前**只能查答案**：问“第26题填什么”会直接给答案，
问“为什么填这个词”会说明暂时不支持讲解。

仔细阅读（第 46～55 题）问“第49题选什么”会得到答案字母和选项内容；
问“为什么不选D”会结合原文比较选项并给出八节讲解。

翻译需要写清**年份、月份和套数**，无需题号。问“翻译怎么写”会展示中文原文和练习参考译文；
问“翻译解析”“翻译思路”或“逐句说明”会附上缓存的逐句解析。练习参考译文**非官方答案**；标为**待核**的卷暂不展示译文或解析。
"""
    )

if "service" not in st.session_state:
    # 业务模块首次加载较慢；先画出页面，再为当前浏览器会话创建一次服务。
    from config import ragconfig
    from retrieval.service import Service

    st.session_state.service = Service(ragconfig())
if "messages" not in st.session_state:
    st.session_state.messages = []
st.session_state.setdefault("practice_item", None)
st.session_state.setdefault("practice_result", None)
st.session_state.setdefault("practice_feedback", None)
st.session_state.setdefault("practice_encouragement", False)
st.session_state.setdefault("practice_question_revision", 0)

with st.expander("逐题练习", expanded=False):
    st.caption("本次练习进度只在当前会话有效；刷新或重新打开页面后不会恢复。")
    with st.form("practice_locator"):
        year = st.number_input("年份", min_value=2000, max_value=2100, value=2024, step=1)
        month = st.selectbox("月份", [3, 6, 7, 9, 12], index=4)
        exam_set = st.number_input("套数", min_value=1, max_value=9, value=1, step=1)
        question_number = st.number_input("阅读题号", min_value=26, max_value=55, value=36, step=1)
        load_question = st.form_submit_button("出题")

    if load_question:
        st.session_state.practice_question_revision += 1
        st.session_state.practice_item = st.session_state.service.practice_question(
            year, month, exam_set, question_number,
        )
        st.session_state.practice_result = None
        st.session_state.practice_feedback = None
        st.session_state.practice_encouragement = False
        st.session_state.practice_target = (year, month, exam_set, question_number)

    item = st.session_state.practice_item
    if load_question and item is None:
        st.warning("该套阅读题暂不能练习，或这道题暂无可判分的缓存；请换一道已收录的题。")
    if item is not None:
        is_cloze = "practice_text" in item
        is_choice = "options" in item
        if is_cloze:
            st.markdown(f"**第 {item['question_number']} 空所在原文**")
            st.markdown(item["practice_text"])
            st.markdown("**A–O 词库**")
            for letter, word in item["words"].items():
                st.write(f"{letter}. {word}")
        elif is_choice:
            st.markdown(f"**第 {item['question_number']} 题原文**")
            st.markdown(item["passage_text"])
            st.markdown(f"**第 {item['question_number']} 题**：{item['stem']}")
            for letter, option in item["options"].items():
                st.write(f"{letter}. {option}")
        else:
            st.markdown(f"**第 {item['question_number']} 题**：{item['stem']}")
            for letter, paragraph in item["paragraphs"].items():
                st.write(f"**段落 {letter}**  {paragraph}")

        if st.session_state.practice_result is None:
            selected = st.selectbox(
                "选择单词" if is_cloze else "选择选项" if is_choice else "选择段落",
                list("ABCDEFGHIJKLMNO" if is_cloze else "ABCD" if is_choice else "ABCDEFGHIJKLMNOPQR"),
                index=None,
                key=f"practice_answer_{st.session_state.practice_question_revision}",
            )
            if st.button("我不会，鼓励我试试"):
                st.session_state.practice_encouragement = True
            if st.session_state.practice_encouragement:
                st.info(
                    "先看看空位前后的语法或搭配，试着选一个词。尝试后才能知道卡在哪里。"
                    if is_cloze else "先从题干找关键词，再回原文核对四个选项。试一试才知道卡在哪里。"
                    if is_choice else "先试着找题干里的关键词，再选一个最接近的段落。尝试后才能知道卡在哪里。"
                )
            if st.button("提交答案", type="primary"):
                if selected is None:
                    st.warning("请先选择一个单词字母。" if is_cloze else "请先选择一个选项。"
                               if is_choice else "请先选择一个段落字母。")
                else:
                    st.session_state.practice_result = st.session_state.service.submit_practice_answer(
                        *st.session_state.practice_target, selected,
                    )
                    if st.session_state.practice_result is None:
                        st.warning("这道题暂时无法判分，请换题重试。")

        result = st.session_state.practice_result
        if result is not None:
            answer_label = f"{result['answer']}（{result['answer_word']}）" if is_cloze else result["answer"]
            if result["correct"]:
                st.success(f"答对了：{result['submitted']}。标准答案：{answer_label}。")
            else:
                st.error(f"你选了 {result['submitted']}；标准答案是 {answer_label}。")
            progress = st.session_state.service.practice_progress()
            st.caption(f"本次已作答 {progress['attempt_count']} 次，正确 {progress['correct_count']} 次。")
            if st.session_state.practice_feedback is None:
                with st.spinner("正在整理解析和下一步建议…"):
                    st.session_state.practice_feedback = st.session_state.service.practice_feedback(result["trace_id"])
            st.markdown(st.session_state.practice_feedback)
            st.caption("想继续练习，请修改题号后点击“出题”；也可以重做同一题。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input(
    "例如：2024年12月第1套第43题为什么不选A",
    max_chars=500,
    submit_mode="disable",
)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("正在分析题目…", show_time=True):
            answer = st.session_state.service.process(question)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
