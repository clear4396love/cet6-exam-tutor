"""模型只识别意图；题目定位和状态变更都由纯代码计算。

Find_Intent.merged(话, 定位表) → (意图, 空定位, 是否降级)。
保留三元组接口是为了不扰动现有 Service；模型不拥有题目定位或写状态权限。
"""
import os  # 读取 API key、计算项目根。
import sys  # 直接运行本文件时补项目路径。
from typing import Literal  # 约束意图和状态操作的枚举值。

# 先设搜索路径，再导入项目模块。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import find_dotenv, load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from config import ragconfig
from memory.session import LocationTable
from retrieval.intent_prompt import MERGE_PROMPT

load_dotenv(find_dotenv())


# 第一列：用户话语的语义关系。
Intent = Literal["NEW_QUESTION", "FOLLOW_UP", "AMBIGUOUS", "NOT_RELATED"]
# 第二列：对 LocationTable 的受限操作；没有未被需求证明的 CLEAR。
# RESET=清表按新值写 / PATCH=留旧卷只补缺的 / NOOP=闲聊先不动。
# 纯类型标注：运行时不做校验（返回别的值不报错），只给人和 mypy 看。
StateOp = Literal["RESET", "PATCH", "NOOP"]

# 一眼能认出的语气词直接短路，省一次 LLM 调用。
BLACKS = frozenset({"嗯", "好的", "ok", "okay", "继续", "continue", "谢谢"})


def _intent_of(raw: str) -> Intent:
    """模型文本归一为四个合法意图；认不出时按新问题处理。"""
    s = raw.strip().upper()
    if s.startswith("NOT_RELAT"):
        return "NOT_RELATED"
    if s.startswith("FOLLOW"):
        return "FOLLOW_UP"
    if s.startswith("AMBIGU"):
        return "AMBIGUOUS"
    return "NEW_QUESTION"


def state_op_of(
    intent: Intent,
    position: dict,
    table: LocationTable,
    *,
    degraded: bool = False,
) -> StateOp:
    """根据最终、已清洗的 position 决定状态操作；模型不参与。

    degraded=True 表示意图识别调用失败，此时禁止继承旧卷。
    """
    # 闲聊或语气词不应改变当前题。
    if intent in ("NOT_RELATED", "AMBIGUOUS"):
        return "NOOP"
    # 用户本轮显式给出任一卷级锚点，应清表后按新值写入。
    if any(position.get(key) for key in ("year", "month", "exam_set")):
        return "RESET"
    # 没给卷级锚点时，只允许可信追问或“完整当前卷 + 新题号”继承。
    if not degraded and (
        intent == "FOLLOW_UP"
        or (
            position.get("question_number") is not None
            and all(table.get(key) for key in ("year", "month", "exam_set"))
        )
    ):
        return "PATCH"
    # 作文等新板块、空定位、降级识别都不得携带旧题号。
    return "RESET"


class Find_Intent:
    """一次 LLM 调用只判断用户话语的语义意图。"""

    def __init__(self, config: ragconfig):
        self.llm = init_chat_model(
            model=config.llm_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=os.getenv("DEEPSEEK_API_KEY"),
        )
        self.merge_chain = (
            PromptTemplate.from_template(MERGE_PROMPT) | self.llm | JsonOutputParser()
        )

    def merged(
        self, user_message: str, table: LocationTable
    ) -> tuple[Intent, dict, bool]:
        """返回 (意图, {}, degraded)；定位统一交给 locator.py。"""
        msg = user_message.strip()
        # 规则短路不是系统故障，所以 degraded=False。
        if msg.lower() in BLACKS:
            return ("AMBIGUOUS", {}, False)
        try:
            data = self.merge_chain.invoke(
                {"context_table": table.to_json(), "user_message": msg}
            )
        except Exception as exc:
            print(f"意图识别失败,退回代码定位:{exc!r}")
            return ("NEW_QUESTION", {}, True)

        if not isinstance(data, dict) or "intent" not in data:
            return ("NEW_QUESTION", {}, True)
        return (_intent_of(str(data["intent"])), {}, False)


if __name__ == "__main__":
    # 只测纯函数，不调模型、不需要 API key。
    assert _intent_of("follow_up") == "FOLLOW_UP"
    assert _intent_of("  FOLLOW_UP\n") == "FOLLOW_UP"
    assert _intent_of("NOT_RELATED") == "NOT_RELATED"
    assert _intent_of("AMBIGUOUS") == "AMBIGUOUS"
    assert _intent_of("") == "NEW_QUESTION"
    current = LocationTable()
    current.update({"year": 2024, "month": 12, "exam_set": 1, "question_number": 43})
    assert state_op_of("NEW_QUESTION", {"question_number": 44}, current) == "PATCH"
    assert state_op_of(
        "NEW_QUESTION", {"question_number": 44}, current, degraded=True
    ) == "RESET"
    assert state_op_of("NEW_QUESTION", {"section": "writing"}, current) == "RESET"
    assert state_op_of("NOT_RELATED", {}, current) == "NOOP"
    print("intent.py 自检通过")
