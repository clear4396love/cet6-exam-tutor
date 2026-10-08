import os  # 计算项目根。
import re
import sys  # 补导入路径。
import tempfile  # 每个测试使用隔离轨迹目录。
from unittest.mock import patch  # 替换 service 命名空间中的外部依赖。


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from memory.episode import Episode
from memory.session import LocationTable
from retrieval.intent import state_op_of
import retrieval.service as service_module


# 足够覆盖 40/43/44 的最小内存题库；答案仍是确定性字段。
FAKE_PAPER = {
    "year": 2024,
    "month": 12,
    "exam_set": 1,
    "paragraphs": {
        "A": "Paragraph A evidence.",
        "B": "Paragraph B evidence.",
        "K": "Paragraph K evidence.",
    },
    "questions": {
        "40": {"stem": "Question 40", "answer": "B"},
        "43": {"stem": "Question 43", "answer": "A"},
        "44": {"stem": "Question 44", "answer": "K"},
    },
    # Section A 用:answer_word 必须真等于 words[answer],否则查答案会按“对不上”降级。
    "section_a": {
        "q_from": 26,
        "q_to": 35,
        "text": "Section A passage.",
        "words": {"A": "discouraging", "B": "dividend", "O": "thrifty"},
        "questions": {
            "26": {"answer": "O", "answer_word": "thrifty"},
            "27": {"answer": "A", "answer_word": "discouraging"},
        },
    },
}


class FakeFindIntent:
    """按测试输入返回固定意图；不创建任何 chat client。"""

    def __init__(self, config):
        self.config = config

    def merged(self, user_message, table):
        if user_message == "你好呀":
            return ("NOT_RELATED", {}, False)
        # 故意把“那44题呢”也判 NEW_QUESTION，复现旧 prompt 的真实行为。
        return ("NEW_QUESTION", {}, False)


class FakeAnswerGeneration:
    """讲解分支的离线替身；当前测试不依赖模型输出。"""

    def __init__(self, config, max_tokens=None):
        self.config = config
        self.max_tokens = max_tokens

    def generate_structured(self, question, context):
        answer = re.search(r"\[答案\(KEYS\)\]([A-R])", context).group(1)
        headings = ("题目陷阱分类", "相关原文截取", "中文参考翻译", "完整题目",
                    "题干在问什么", "其他段落为什么不匹配", f"为什么选{answer}", "本题复盘")
        return "\n".join(f"**{name}**\n离线讲解。" for name in headings)

    def generate_section_c(self, question, context):
        assert "为什么" in question
        assert "[题干]" in context
        assert all(f"[选项{letter}]" in context for letter in "ABCD")
        assert "[答案(KEYS)]" in context
        assert "[原文]" in context
        answer = re.search(r"\[答案\(KEYS\)\]([A-D])", context).group(1)
        headings = ("题目陷阱分类", "相关原文截取", "中文参考翻译", "完整题目",
                    "题干在问什么", "其他选项为什么不匹配", f"为什么选{answer}", "本题复盘")
        return "\n".join(f"**{name}**\n离线仔细阅读八节讲解。" for name in headings)


def fake_load_set(year, month, exam_set):
    """只让指定测试卷命中，其他卷返回 None。"""
    if (year, month, exam_set) == (2024, 12, 1):
        return FAKE_PAPER
    return None


def test_state_op_matrix():
    """六个关键判例锁住继承边界。"""
    current = LocationTable()
    current.update(
        {"year": 2024, "month": 12, "exam_set": 1, "question_number": 43}
    )
    assert state_op_of("NEW_QUESTION", {"question_number": 44}, current) == "PATCH"
    assert state_op_of(
        "NEW_QUESTION",
        {"year": 2025, "month": 6, "exam_set": 2, "question_number": 40},
        current,
    ) == "RESET"
    assert state_op_of("NEW_QUESTION", {"section": "writing"}, current) == "RESET"
    assert state_op_of("NOT_RELATED", {}, current) == "NOOP"

    empty = LocationTable()
    assert state_op_of("NEW_QUESTION", {"question_number": 44}, empty) == "RESET"
    assert state_op_of(
        "NEW_QUESTION", {"question_number": 44}, current, degraded=True
    ) == "RESET"


def test_multiturn_state_and_trace():
    """多轮状态、固定 schema、三态答案统计一次验完。"""
    with tempfile.TemporaryDirectory(prefix="trace_test_") as tmp:
        app = service_module.Service(config=None, session_id="offline-session")
        # 替换默认 Episode，确保测试只写临时目录。
        app.episode = Episode("offline-session", out_dir=tmp)

        with (
            patch.object(service_module, "Find_Intent", FakeFindIntent),
            patch.object(service_module, "AnswerGeneration", FakeAnswerGeneration),
            patch.object(service_module, "load_set", side_effect=fake_load_set),
        ):
            # 第一轮完整定位：RESET，普通问答没有提答案字母。
            first = app.process("2024年12月第1套第43题选什么")
            assert "答案:A" in first

            # 第二轮只给题号：即使 intent=NEW_QUESTION，也应继承完整当前卷。
            second = app.process("那44题呢")
            assert "第44题答案:K" in second

            # 第三轮跳作文：必须清掉旧题号，不能继续回答第44题。
            third = app.process("作文怎么提高")
            assert "作文" in third          # 改:不再答非所问地要题号
            assert app.table.get("question_number") is None


            # 闲聊：NOOP，不改变刚才的 writing 状态。
            before_hello = app.table.to_dict()
            assert app.process("你好呀") == "请问英语六级问题"
            assert app.table.to_dict() == before_hello

            # 用户明确报错字母：False；不是普通问答的默认 False。
            wrong = app.process("2024年12月第1套第43题选B")
            assert "答案不是 B,是 A" in wrong

            # 用户明确报对字母：True。
            right = app.process("2024年12月第1套第43题选A")
            assert "是的" in right

        rows = app.episode.lines()
        assert len(rows) == 6
        assert [row["turn"] for row in rows] == [1, 2, 3, 4, 5, 6]
        assert len({row["trace_id"] for row in rows}) == 6
        assert all(set(row) == set(rows[0]) for row in rows)

        # 第一轮没有提字母，两个字段必须都是 None。
        assert rows[0]["answer_mentioned"] is None
        assert rows[0]["answer_agrees"] is None
        assert rows[0]["state_op"] == "RESET"
        assert rows[0]["filters"]["question_number"] == 43
        assert rows[0]["retrieved_doc_ids"] == ["2024_12_1"]

        # 第二轮验证本轮最关键缺陷：PATCH 后继承年月套。
        assert rows[1]["position"] == {"question_number": 44}
        assert rows[1]["state_op"] == "PATCH"
        assert rows[1]["filters"] == {
            "year": 2024,
            "month": 12,
            "exam_set": 1,
            "question_number": 44,
        }

        # 作文轮 RESET 后，实际 filters 不得带旧题号。
        assert rows[2]["state_op"] == "RESET"
        assert rows[2]["filters"] == {"section": "writing"}
        assert rows[3]["state_op"] == "NOOP"

        # answer_agrees 只有用户明确提字母时才是布尔值。
        assert rows[4]["answer_mentioned"] == "B"
        assert rows[4]["answer_agrees"] is False
        assert rows[5]["answer_mentioned"] == "A"
        assert rows[5]["answer_agrees"] is True


def test_exception_still_records_one_line():
    """主链路异常时返回友好提示，并在 finally 中写一条带 error 的轨迹。"""
    with tempfile.TemporaryDirectory(prefix="trace_error_test_") as tmp:
        app = service_module.Service(config=None, session_id="error-session")
        app.episode = Episode("error-session", out_dir=tmp)

        def explode(year, month, exam_set):
            raise RuntimeError("offline boom")

        with (
            patch.object(service_module, "Find_Intent", FakeFindIntent),
            patch.object(service_module, "AnswerGeneration", FakeAnswerGeneration),
            patch.object(service_module, "load_set", side_effect=explode),
        ):
            answer = app.process("2024年12月第1套第43题选什么")

        assert answer == "出错了,请稍后再试"
        rows = app.episode.lines()
        assert len(rows) == 1
        assert "RuntimeError" in rows[0]["error"]

def test_invalid_position_does_not_inherit_old_paper():
    """用户显式给了非法卷级定位时，禁止继承旧卷。

    「月」是 0 时最危险：0 在 Python 里是 falsy，只靠 state_op_of 的真值判断会漏过，
    于是 PATCH 静默继承旧卷，拿旧卷答案回答一个用户明明换了卷的问题。
    """
    with tempfile.TemporaryDirectory(prefix="invalid_pos_test_") as tmp:
        app = service_module.Service(config=None, session_id="invalid-pos")
        app.episode = Episode("invalid-pos", out_dir=tmp)

        with (
            patch.object(service_module, "Find_Intent", FakeFindIntent),
            patch.object(service_module, "AnswerGeneration", FakeAnswerGeneration),
            patch.object(service_module, "load_set", side_effect=fake_load_set),
        ):
            for bad in ("13月第5套第42题", "0月第42题"):
                # 每轮都先把表恢复成一张完整的卷。
                app.table.clear()
                app.table.update(
                    {"year": 2024, "month": 12, "exam_set": 1, "question_number": 43}
                )

                app.process(bad)

                last = app.episode.lines()[-1]
                assert last["state_op"] == "RESET", f"{bad} 应当 RESET"
                for key in ("year", "month", "exam_set"):
                    assert key not in last["filters"], f"{bad}: filters 不该带旧 {key}"


class FollowUpIntent(FakeFindIntent):
    """把明确追问判成 FOLLOW_UP —— 真实 MERGE_PROMPT 就是这么判的。"""

    HINTS = ("为什么不选", "那", "呢")

    def merged(self, user_message, table):
        if any(hint in user_message for hint in self.HINTS):
            return ("FOLLOW_UP", {}, False)
        return super().merged(user_message, table)


def test_explanation_layer_receives_user_message():
    """讲解层必须收到**用户原话**,不能是任何被改写过的句子。

    这是删除改写器的核心回归锁：改写器还在时,它会把模型重写后的句子
    当成"用户问题"传给 wants_explanation / extract_mention_letter / generate_structured。
    """
    captured = {}

    class RecordingAnswerGeneration:
        def __init__(self, config, max_tokens=None):
            self.config = config
            self.max_tokens = max_tokens

        def generate_structured(self, question, context):
            captured["question"] = question
            return "离线讲解"

    with tempfile.TemporaryDirectory(prefix="user_message_test_") as tmp:
        app = service_module.Service(config=None, session_id="user-message")
        app.episode = Episode("user-message", out_dir=tmp)

        with (
            patch.object(service_module, "Find_Intent", FollowUpIntent),
            patch.object(
                service_module, "AnswerGeneration", RecordingAnswerGeneration
            ),
            patch.object(service_module, "load_set", side_effect=fake_load_set),
        ):
            app.process("2024年12月第1套第43题选什么")   # 第一轮：定位并建立当前题
            app.process("为什么不选A")                    # 第二轮：追问，走讲解分支

    assert captured["question"] == "为什么不选A"


def test_follow_up_letter_comes_from_user_words():
    """追问轮抠出的字母必须来自用户原话,且原话一字不改地进轨迹。"""
    with tempfile.TemporaryDirectory(prefix="follow_up_test_") as tmp:
        app = service_module.Service(config=None, session_id="follow-up")
        app.episode = Episode("follow-up", out_dir=tmp)

        with (
            patch.object(service_module, "Find_Intent", FollowUpIntent),
            patch.object(service_module, "AnswerGeneration", FakeAnswerGeneration),
            patch.object(service_module, "load_set", side_effect=fake_load_set),
        ):
            app.process("2024年12月第1套第43题选什么")
            second = app.process("那B呢")
            row = app.episode.lines()[-1]

    assert row["query"] == "那B呢"            # 原话入轨迹,一个字都没改
    assert row["answer_mentioned"] == "B"     # 字母来自原话,不是模型改写出来的
    assert row["state_op"] == "PATCH"         # 追问继承当前卷,不重新定位
    assert "不是 B" in second                 # 答案模式走通


def test_unsafe_relative_reference_stops_before_state_machine():
    """相对指代必须在 state_op_of / 改表 / 读题库之前被拦下。

    用 Mock + assert_not_called 直接证明"没调用过",比只看返回值更硬。
    """
    cases = (
        "下一题",
        "2025年12月第1套的下一套",
        "2025年今年12月第1套的下一题",
        "去年那套的44题",
        "去年那套的下一题",          # 一句话命中两个:提示要同时列出
    )
    with tempfile.TemporaryDirectory(prefix="relative_test_") as tmp:
        app = service_module.Service(config=None, session_id="relative")
        app.episode = Episode("relative", out_dir=tmp)
        # 先建立完整当前表 —— 必须在打桩之前,因为建表本身要调 update()。
        app.table.update(
            {"year": 2024, "month": 12, "exam_set": 1, "question_number": 43}
        )
        before = app.table.to_dict()

        with (
            patch.object(service_module, "Find_Intent", FollowUpIntent),
            patch.object(service_module, "state_op_of") as state_op,
            patch.object(service_module.LocationTable, "update") as table_update,
            patch.object(service_module.LocationTable, "clear") as table_clear,
            patch.object(service_module, "load_set") as load,
        ):
            answers = [app.process(case) for case in cases]

        # ① 状态机、写表、读题库三件事一件都没发生。
        state_op.assert_not_called()
        table_update.assert_not_called()
        table_clear.assert_not_called()
        load.assert_not_called()

        # ② 每一轮的轨迹契约。
        rows = app.episode.lines()
        assert len(rows) == len(cases)
        for answer, row in zip(answers, rows):
            assert "还不能安全换算" in answer
            assert row["stage"] == "ambiguous_reference"
            assert row["state_op"] == "NOOP"
            assert row["hit"] is False
            assert row["out_of_library"] is False
            assert row["filters"] == before
            assert row["retrieved_doc_ids"] == []

        # ③ position 仍保存本轮确定性抽到的字段,不改表。
        assert rows[1]["position"] == {"year": 2025, "month": 12, "exam_set": 1}
        assert rows[3]["position"] == {"question_number": 44}
        assert app.table.to_dict() == before

        # ④ 一句话命中多个时,提示里要同时列出。
        assert "去年" in answers[4] and "下一题" in answers[4]


def test_normal_follow_up_is_not_rejected():
    """反例:正常追问与普通指代不得被相对指代守卫拦下。"""
    with tempfile.TemporaryDirectory(prefix="no_reject_test_") as tmp:
        app = service_module.Service(config=None, session_id="no-reject")
        app.episode = Episode("no-reject", out_dir=tmp)

        with (
            patch.object(service_module, "Find_Intent", FollowUpIntent),
            patch.object(service_module, "AnswerGeneration", FakeAnswerGeneration),
            patch.object(service_module, "load_set", side_effect=fake_load_set),
        ):
            app.process("2024年12月第1套第43题选什么")
            app.process("那B呢")
            app.process("第44题呢")
            stages = [row["stage"] for row in app.episode.lines()]

    assert stages == ["answer", "answer", "answer"]
    assert "ambiguous_reference" not in stages


if __name__ == "__main__":
    # 不依赖 pytest，也能逐个运行本文件里的测试函数。
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"\n全部通过 ✅({len(tests)} 个)")
