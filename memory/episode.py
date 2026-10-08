import json
import os
import re
import time
import uuid

_DEFAULTS = {                   # 同一 schema 版本内固定键集:字段一个不少,值先全填 None;历史日志不迁移
    "trace_id": None,           # 本轮唯一编号(每轮一个,不是每会话一个);排查问题时拿它定位
    "session_id": None,         # 会话编号;一次会话一个文件,已过 __init__ 的字符白名单
    "turn": None,               # 第几轮,从 1 起;靠读文件末行 +1,关掉程序再开会接着数
    "ts": None,                 # 本行写入的时间
    "query": None,              # 用户原话,不改一个字
    "intent": None,             # 语义列四选一:NEW_QUESTION/FOLLOW_UP/AMBIGUOUS/NOT_RELATED
    "state_op": None,           # 状态列三选一:RESET/PATCH/NOOP;纯代码算,没有 CLEAR
    "position": {},             # ★本轮新抽到的定位(只含这轮说的);state_op_of 的直接输入
    "table_before": {},         # 改表前的快照,用来还原这轮到底改了什么
    "filters": {},              # 本轮结束时的有效定位;不代表本轮一定查过题库
    "retrieved_doc_ids": [],    # 命中的缓存键如 ["2024_12_1"];没命中就是 []
    # 走的哪条分支:answer/explanation/evidence_missing/generation_empty/generation_error/
    # generation_invalid/not_related/ambiguous/ambiguous_reference/missing_question/missing_paper/
    # unsupported_type/duplicate_section/cache_miss_paper/cache_miss_section/
    # cache_miss_question/cache_miss_answer/translation_sample/
    # translation_pending_review/attempt_correct/attempt_wrong(共 20 个值)
    "stage": None,
    "hit": None,                # 是否命中题库缓存
    "out_of_library": None,     # 是否库外/无数据(题不在库、题型没上线)
    "answer_keys": None,        # 该题的 KEYS 标准答案字母
    "answer_mentioned": None,   # ★用户说的字母(不是模型说的);用户没提就是 null
    "answer_agrees": None,      # ★用户说的 vs KEYS;用户没提字母时必须 null,不能是 false
    "attempt_answer": None,     # 练习区显式提交的字母；普通问答保持 null
    "attempt_correct": None,    # 代码按 KEYS 判分；普通问答保持 null
    "answer_verified": None,    # 阅读讲解通过标题与 KEYS 检查为 true;不通过为 false
    "has_valid_citation": None, # L2/L4 才填,本轮固定 null
    "latency_ms": None,         # 本轮耗时(毫秒)
    "error": None,              # 正常是 null;崩了写 repr(异常)
}


class Episode:
    """单会话轨迹文件；写失败不打断用户问答。"""

    def __init__(self, session_id: str | None = None, out_dir: str | None = None):
        # session_id 来自未来前端，先按路径信任边界做字符白名单,留下字母、数字、下划线和连字符，最多 64 个字符。。
        sid = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "")[:64]
        # 未提供合法 ID 时，用时间 + 随机尾缀生成，避免并发启动撞名。
        self.session_id = sid or (
            time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        )
        # 默认目录固定在项目根的 episodes/；构造时不创建目录。
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.out_dir = out_dir or os.path.join(project_root, "episodes")
        # 白名单后的 ID 才能参与路径拼接，防止 ../ 越界。
        self.path = os.path.join(self.out_dir, f"{self.session_id}.jsonl")

    def build(self, **fields) -> dict:
        """纯组装一行固定 schema；不读写磁盘，也不改变对象状态。"""
        # 逐项复制，避免多行共享默认 dict/list 引用。
        row = {
            key: (value.copy() if isinstance(value, (dict, list)) else value)
            for key, value in _DEFAULTS.items()
        }
        # 未知字段不进入日志，防止 schema 被随手扩散。
        for key, value in fields.items():
            if key in row:
                row[key] = value
        # 三个系统字段由存储层兜底生成。
        row["trace_id"] = row["trace_id"] or uuid.uuid4().hex[:12]
        row["session_id"] = self.session_id
        row["turn"] = int(row["turn"] or 1)
        row["ts"] = row["ts"] or time.strftime("%Y-%m-%dT%H:%M:%S%z")
        return row

    def record(self, **fields) -> dict:
        """追加一行；任何写盘失败只打印提示，不向问答链路抛异常。"""
        # 从最后一条有效行继续编号；坏行由 lines() 跳过。
        previous = self.last()
        next_turn = int(previous.get("turn", 0)) + 1 if previous else 1
        row = self.build(**{**fields, "turn": next_turn})
        try:
            # 只有真正写入时才创建目录，不制造无用空目录。
            os.makedirs(self.out_dir, exist_ok=True)
            # Windows 必须显式 UTF-8，否则中文可能按 cp936 写坏。
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        except (OSError, TypeError, ValueError) as exc:
            # 轨迹是旁路能力，失败不能覆盖本轮正常答案。
            print(f"轨迹写入失败:{exc!r}")
        return row

    def lines(self) -> list[dict]:
        """读回全部有效 dict；文件不存在返回空列表，坏行跳过。"""
        if not os.path.exists(self.path):
            return []
        rows = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    try:
                        value = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(value, dict):
                        rows.append(value)
        except OSError as exc:
            print(f"轨迹读取失败:{exc!r}")
        return rows

    def last(self) -> dict | None:
        """返回最后一条有效轨迹；没有则返回 None。"""
        rows = self.lines()
        return rows[-1] if rows else None


if __name__ == "__main__":
    # 自检全部写临时目录，不污染项目 episodes/。
    import tempfile

    with tempfile.TemporaryDirectory(prefix="episode_selftest_") as tmp:
        # ../ 和点号会被白名单吃掉，最终文件仍只能位于 tmp。
        ep = Episode("../student.01", out_dir=tmp)
        assert ep.session_id == "student01"
        assert os.path.dirname(os.path.abspath(ep.path)) == os.path.abspath(tmp)

        # build 只组装，不应创建文件。
        preview = ep.build(query="预览", filters={"question_number": 45})
        assert preview["turn"] == 1
        assert not os.path.exists(ep.path)

        # 连续写两轮，turn 必须单调递增，数字类型不得变成字符串。
        first = ep.record(query="第一轮", filters={"question_number": 45})
        second = ep.record(query="第二轮", answer_verified=None)
        assert first["turn"] == 1 and second["turn"] == 2
        rows = ep.lines()
        assert len(rows) == 2
        assert rows[0]["filters"]["question_number"] == 45
        assert isinstance(rows[0]["filters"]["question_number"], int)
        assert set(rows[0]) == set(rows[1]) == set(_DEFAULTS)
        assert rows[0]["answer_verified"] is None
        assert rows[0]["has_valid_citation"] is None

        # 人工追加坏行；读取必须跳过，不能炸掉整个会话。
        with open(ep.path, "a", encoding="utf-8") as f:
            f.write("这不是 JSON\n")
        assert len(ep.lines()) == 2
        assert ep.last()["turn"] == 2

        # 两次默认生成的 session_id 不应相同。
        assert Episode(out_dir=tmp).session_id != Episode(out_dir=tmp).session_id

    print("episode.py 自检通过")
