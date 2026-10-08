from pathlib import Path

from streamlit.testing.v1 import AppTest
from memory.session import LocationTable


APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


class FakeService:
    def __init__(self):
        self.questions = []
        self.table = LocationTable()

    def process(self, question: str) -> str:
        self.questions.append(question)
        return f"测试回答：{question}"

    def learning_progress(self, preferred_section=None):
        return {"reading": {"attempt_count": 0, "correct_count": 0},
                "writing_count": 0, "translation_count": 0,
                "latest_feedback_status": "none", "next_action": "选择一道已收录的阅读题。",
                "next_action_target": None, "history_warnings": [], "repetition_groups": []}

class FakePracticeService(FakeService):
    def __init__(self):
        super().__init__()
        self.submissions = []

    def practice_question(self, year, month, exam_set, question_number):
        return {
            "question_number": question_number,
            "stem": f"Question {question_number}",
            "paragraphs": {"A": "Paragraph A", "C": "Paragraph C"},
        }

    def submit_practice_answer(self, year, month, exam_set, question_number, submitted_answer):
        self.submissions.append((question_number, submitted_answer))
        return {
            "submitted": submitted_answer,
            "answer": "C",
            "correct": submitted_answer == "C",
            "trace_id": f"attempt-{len(self.submissions)}",
        }

    def practice_progress(self):
        count = len(self.submissions)
        return {"attempt_count": count, "correct_count": 0, "accuracy": 0.0,
                "recent_accuracy": 0.0, "by_range": {}, "repeated_misses": [],
                "tier": "plan_insufficient_data"}

    def practice_feedback(self, trace_id):
        return f"参考解析：{trace_id}，下题先找同义改写。"


class FakeClozeService(FakePracticeService):
    def practice_question(self, year, month, exam_set, question_number):
        if question_number != 26:
            return None
        return {
            "question_number": 26,
            "practice_text": " ".join(f"context {{{{{n}}}}}" for n in range(26, 36)),
            "words": {letter: f"word{letter.lower()}" for letter in "ABCDEFGHIJKLMNO"},
        }

    def submit_practice_answer(self, year, month, exam_set, question_number, submitted_answer):
        self.submissions.append((year, month, exam_set, question_number, submitted_answer))
        return {"submitted": submitted_answer, "answer": "C", "answer_word": "wordc",
                "correct": submitted_answer == "C", "trace_id": "cloze-1"}


class FakeSectionCService(FakePracticeService):
    def practice_question(self, year, month, exam_set, question_number):
        if question_number not in (46, 51):
            return None
        return {
            "question_number": question_number,
            "passage_text": f"Passage for question {question_number}",
            "stem": f"What does passage {question_number} say?",
            "options": {"A": "Wrong claim", "B": "Memory helps", "C": "Another claim", "D": "Trees cool cities"},
        }

    def submit_practice_answer(self, year, month, exam_set, question_number, submitted_answer):
        self.submissions.append((year, month, exam_set, question_number, submitted_answer))
        answer = "B" if question_number == 46 else "D"
        return {"submitted": submitted_answer, "answer": answer,
                "correct": submitted_answer == answer, "trace_id": "section-c-1"}


def test_section_c_ui_keeps_displayed_question_and_hides_answer_until_submission():
    service = FakeSectionCService()
    app = AppTest.from_file(APP, default_timeout=15)
    app.session_state["service"] = service
    app.session_state["messages"] = []
    app.run()
    next(widget for widget in app.number_input if widget.label == "阅读题号").set_value(46).run()
    next(button for button in app.button if button.label == "出题").click().run()
    assert not app.exception
    before = "\n".join(item.value for item in app.markdown)
    assert "Passage for question 46" in before and "Memory helps" in before
    assert "标准答案" not in before
    assert "answer" not in app.session_state["practice_item"]
    next(button for button in app.button if button.label == "我不会，鼓励我试试").click().run()
    assert service.submissions == []
    next(widget for widget in app.number_input if widget.label == "阅读题号").set_value(51).run()
    next(widget for widget in app.selectbox if widget.label == "选择选项").set_value("A").run()
    next(button for button in app.button if button.label == "提交答案").click().run()
    assert service.submissions == [(2024, 12, 1, 46, "A")]
    assert app.session_state["practice_result"]["answer"] == "B"
    next(button for button in app.button if button.label == "出题").click().run()
    after = "\n".join(item.value for item in app.markdown)
    assert "Passage for question 51" in after and "Passage for question 46" not in after
    assert next(widget for widget in app.selectbox if widget.label == "选择选项").value is None


def test_cloze_ui_hides_answer_and_grades_displayed_question_after_locator_changes():
    service = FakeClozeService()
    app = AppTest.from_file(APP, default_timeout=15)
    app.session_state["service"] = service
    app.session_state["messages"] = []
    app.run()
    next(widget for widget in app.number_input if widget.label == "阅读题号").set_value(26).run()
    next(button for button in app.button if button.label == "出题").click().run()
    assert not app.exception
    assert "{{26}}" in " ".join(item.value for item in app.markdown)
    assert app.session_state["practice_item"]["words"]["O"] == "wordo"
    assert "标准答案" not in " ".join(item.value for item in app.markdown)
    next(button for button in app.button if button.label == "我不会，鼓励我试试").click().run()
    assert service.submissions == []
    next(widget for widget in app.number_input if widget.label == "阅读题号").set_value(27).run()
    next(widget for widget in app.selectbox if widget.label == "选择单词").set_value("B").run()
    next(button for button in app.button if button.label == "提交答案").click().run()
    assert service.submissions == [(2024, 12, 1, 26, "B")]
    assert app.session_state["practice_result"]["answer_word"] == "wordc"
    assert "wordc" in " ".join(item.value for item in app.markdown)


def test_chat_ui_keeps_one_conversation_in_session():
    assert APP.exists(), "缺少 Streamlit 入口文件"

    service = FakeService()
    app = AppTest.from_file(APP, default_timeout=15)
    app.session_state["service"] = service
    app.session_state["messages"] = []
    app.run()

    assert not app.exception
    assert app.title[0].value == "六级真题讲解助手"
    assert "36～45" in app.caption[0].value
    assert "26～35" in app.caption[0].value        # 选词填空查答案也在支持范围内
    assert "46～55" in app.caption[0].value
    assert "翻译" in app.caption[0].value
    assert app.expander[0].label == "怎么提问才能得到完整讲解？"
    tutorial = "\n".join(item.value for item in app.markdown)
    assert "为什么这样选" in tutorial
    assert "为什么不选A" in tutorial
    assert "只问“选什么”会得到简短答案" in tutorial
    assert "短问法只适用于当前会话已经定位成功" in tutorial
    assert "刷新页面后请重新提供完整定位" in tutorial
    assert "第49题选什么" in tutorial
    assert "仔细阅读（第 46～55 题）" in tutorial
    assert "仔细阅读题" in tutorial and "八节讲解" in tutorial
    assert "仔细阅读（第 46～55 题）目前**只能查答案**" not in tutorial
    assert "2024年12月第1套翻译解析" in tutorial
    assert "非官方答案" in tutorial
    assert "待核" in tutorial
    assert len(app.chat_input) == 1

    question = "2024年12月第1套第43题为什么不选A"
    app.chat_input[0].set_value(question).run()

    assert service.questions == [question]
    assert app.session_state["messages"] == [
        {"role": "user", "content": question},
        {"role": "assistant", "content": f"测试回答：{question}"},
    ]
    assert len(app.chat_message) == 2


def test_practice_ui_submits_one_answer_and_keeps_chat_separate():
    service = FakePracticeService()
    app = AppTest.from_file(APP, default_timeout=15)
    app.session_state["service"] = service
    app.session_state["messages"] = []
    app.run()

    assert not app.exception
    assert "7" in next(select for select in app.selectbox if select.label == "月份").options
    assert any("刷新或重新打开页面后不会恢复" in item.value for item in app.caption)
    next(button for button in app.button if button.label == "出题").click().run()
    assert app.session_state["practice_item"]["question_number"] == 36
    assert "answer" not in app.session_state["practice_item"]
    assert service.submissions == []

    next(button for button in app.button if button.label == "我不会，鼓励我试试").click().run()
    assert service.submissions == []
    assert app.session_state["practice_encouragement"] is True

    next(select for select in app.selectbox if select.label == "选择段落").set_value("A").run()
    next(button for button in app.button if button.label == "提交答案").click().run()
    assert service.submissions == [(36, "A")]
    assert app.session_state["practice_result"]["answer"] == "C"
    assert app.session_state["practice_feedback"].startswith("参考解析")
    app.chat_input[0].set_value("第43题为什么选C？").run()
    assert service.questions == ["第43题为什么选C？"]
    assert service.submissions == [(36, "A")]
