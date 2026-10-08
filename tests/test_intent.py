import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from memory.session import LocationTable
from retrieval.intent import Find_Intent, _intent_of


class FakeChain:
    """直接返回解析后的对象，不创建或调用真实模型。"""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def invoke(self, _inputs):
        if self.error:
            raise self.error
        return self.result


def _finder(result=None, error=None):
    finder = Find_Intent.__new__(Find_Intent)
    finder.merge_chain = FakeChain(result, error)
    return finder


def test_merged_uses_model_for_intent_only():
    """模型即使返回定位字段，也不能参与题目定位。"""
    result = {"intent": "FOLLOW_UP", "position": {"year": 2025}}
    assert _finder(result).merged("为什么选A", LocationTable()) == (
        "FOLLOW_UP",
        {},
        False,
    )


def test_merged_degrades_on_bad_parser_output():
    """解析器没给 JSON 对象或缺少 intent 时，禁止继承旧卷。"""
    table = LocationTable()
    for result in (["FOLLOW_UP"], "FOLLOW_UP", 123, {}, {"position": {}}):
        assert _finder(result).merged("第44题", table) == (
            "NEW_QUESTION",
            {},
            True,
        )


def test_merged_degrades_when_model_call_fails():
    result = _finder(error=RuntimeError("offline")).merged("第44题", LocationTable())
    assert result == ("NEW_QUESTION", {}, True)


def test_intent_of_normalizes():
    assert _intent_of("follow_up") == "FOLLOW_UP"
    assert _intent_of("  FOLLOW_UP\n") == "FOLLOW_UP"
    assert _intent_of("NOT_RELATED") == "NOT_RELATED"
    assert _intent_of("AMBIGUOUS") == "AMBIGUOUS"
    assert _intent_of("") == "NEW_QUESTION"
    assert _intent_of("????") == "NEW_QUESTION"


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\n全部通过 ✅({len(fns)} 个)")
