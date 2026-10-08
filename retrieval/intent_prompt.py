"""意图识别的 prompt。

MERGE_PROMPT：定位表 + 用户原话 → {"intent": ...} JSON。
    intent 四选一：NEW_QUESTION / FOLLOW_UP / AMBIGUOUS / NOT_RELATED。
    RESET/PATCH/NOOP 不在 prompt 里，由 retrieval.intent.state_op_of() 纯代码算。

定位表字段（和 locator.py / session.py 的 FIELDS 一致）：
    year / month / exam_set / section / question_number

用法（在 retrieval/intent.py 里接）：
    MERGE_PROMPT.format(context_table=table.to_json(), user_message=user_msg)
"""


MERGE_PROMPT = """
你是英语六级真题讲题助手的意图识别器，只判断用户这句话是哪类意图。
年份、月份、套数、板块和题号由代码解析，不归你决定。

【当前题目定位表】(JSON，正在讲的题；空表 = 还没开始讲任何题)：
{context_table}

【用户的这句话】：
{user_message}

【输出格式】
只输出一个 JSON 对象，不要 markdown 围栏、不要解释、不要前后缀：
{{"intent": "NEW_QUESTION"}}
- intent 四选一：NEW_QUESTION / FOLLOW_UP / AMBIGUOUS / NOT_RELATED

【意图判断标准】
- NEW_QUESTION：用户自己开了一个新题——自己带了年份/套数/题号等定位信息，
  或者明显是在问一个全新的问题，跟前文无关。
- FOLLOW_UP：用户在追问当前题目——比如"那B呢""C选项为什么不对""这道题呢"
  "其他选项呢"，都是在问定位表里那道题的延伸。
- AMBIGUOUS：语气词或没内容——"嗯""好的""谢谢""继续"这类；
  或者定位表为空时还在说"那B呢"（没有上文可追，说不清问的是哪道题）。
- NOT_RELATED：跟六级真题无关的闲聊或别的问题，如"现在几点了""你好呀"。
- 定位表为空时，一律不判 FOLLOW_UP。
- 只要用户自己带了定位信息，优先判 NEW_QUESTION，即使句子里有"那""呢"这些词。
"""
