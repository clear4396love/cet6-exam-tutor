"""会话定位表：记住"正在讨论哪道题"，给意图识别和讲解共用。

核心设计：单实例覆盖，不累积。
- 用户问新题（NEW_QUESTION）→ 整张表被新题覆盖。
- 追问（FOLLOW_UP）→ 读表补全缺失信息，表本身不动。

字段和 locator.py 的 parse_conditions 输出一致，只收**真正参与定位**的维度。
答案字母不在这里 —— 它是本轮问句的属性，由 extract_mention_letter 从用户原话抠。
"""
import json

FIELDS = ["year", "month", "exam_set", "section", "question_number"]


class LocationTable:
    """当前题目的定位表。空表 = 还没定位到任何题。

    用法：
        table = LocationTable()
        table.update({"year": 2024, "month": 12, "exam_set": 1})  # 覆盖成新题
        table.to_json()   # 给 MERGE_PROMPT 当 context_table
        table.clear()     # 对话重启 / 连续答非所问时清空
    """

    def __init__(self):
        self._fields = {f: None for f in FIELDS}

    def update(self, fields: dict) -> None:
        """收:新抽到的字段 dict; 吐:None(有副作用——改表:没提的字段保留旧值=继承,提了的覆盖)。"""
        # 用新抽到的定位覆盖/补全。值是 None 的字段不碰（保留旧值）。
        for k, v in fields.items():
            if k in self._fields and v is not None:
                self._fields[k] = v

    def clear(self) -> None:
        """收:无; 吐:None(有副作用——清空整张表,对话重启/答非所问时用)。"""
        for k in self._fields:
            self._fields[k] = None

    def is_empty(self) -> bool:
        """收:无; 吐:bool(表是否全空)。只读,不改表。"""
        return all(v is None for v in self._fields.values())

    def get(self, key: str):
        """收:字段名; 吐:字段值(没有则 None)。只读。"""
        return self._fields.get(key)

    def to_dict(self) -> dict:
        """收:无; 吐:非空字段 dict(空表就是 {},避免喂给模型一堆 null)。只读。"""
        return {k: v for k, v in self._fields.items() if v is not None}

    def to_json(self) -> str:
        """收:无; 吐:JSON 字符串(给 MERGE_PROMPT 当 {context_table})。只读。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)
