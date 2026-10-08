
import json
import os
import sys
from typing import List

# ★ 先设搜索路径再 import 项目内模块(从任何目录跑都不会挂)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # exam-tutor/
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
_DIR = os.path.dirname(os.path.abspath(__file__))                            # retrieval/
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from answer_prompt import ANSWER_PROMPT, PRACTICE_PROMPT, SECTION_C_PRACTICE_PROMPT, SECTION_C_PROMPT
from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
load_dotenv()
from config import ragconfig


class AnswerGeneration:
    def __init__(self,config:ragconfig,max_tokens:int|None=None):
        self.config=config
        self.max_tokens = max_tokens or self.config.max_tokens  # 8节模板可给更大,不动全局
        self.llm=init_chat_model(
                    model=self.config.llm_name,
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    temperature=self.config.temperature,
                    max_tokens=self.max_tokens,
                    # ★ 关掉思考模式:思考与正文共用 max_tokens,开着会把正文挤空
                    #   (3000 全被思考吃掉 → 正文空返回)。写法同 core/test/测试.py
                    #   与 rag_rag/querying/rag_pipeline.py。
                    extra_body={"thinking": {"type": "disabled"}},
                )
        self.prompt=PromptTemplate.from_template(ANSWER_PROMPT)
        self.chain=self.prompt | self.llm |StrOutputParser()

    def peckage(self,docs: List[str], meta: List[dict])-> str:
        context_lines = []
        for i, (doc, m) in enumerate(zip(docs, meta), 1):   
            page = m.get('page', -1)                        
            page_str = f"第{page + 1}页" if page >= 0 else "页码未知"
            source = m.get('source', '未获得来源')
            context_lines.append(
            f"[证据{i}] | 来源:{source} | {page_str}\n{doc[:self.config.content_max_length]}"
            )
        return "\n\n".join(context_lines)

    def generate(self, question: str, docs: List[str], meta: List[dict]) -> str:
        context=self.peckage(docs, meta)
        result=self.chain.invoke({"context":context,"question":question})
        return result

    def generate_structured(self, question: str, context: str) -> str:
        """结构化证据版:证据已带类型标签([题干]/[答案(KEYS)]/[原文段落X]),
        不再套 [证据N] 打包,直接进 8 节模板。"""
        result=self.chain.invoke({"context":context,"question":question})
        return result

    def generate_section_c(self, question: str, context: str) -> str:
        """用仔细阅读专用八节模板讲解单题。"""
        chain = PromptTemplate.from_template(SECTION_C_PROMPT) | self.llm | StrOutputParser()
        return chain.invoke({"context": context, "question": question})

    def generate_practice_feedback(self, evidence: str, result: dict, progress: dict) -> str:
        """One plain model call with facts already decided by code."""
        chain = PromptTemplate.from_template(PRACTICE_PROMPT) | self.llm | StrOutputParser()
        return chain.invoke({
            "evidence": evidence,
            "result": json.dumps(result, ensure_ascii=False),
            "progress": json.dumps(progress, ensure_ascii=False),
        })

    def generate_section_c_practice_feedback(self, evidence: str, result: dict, progress: dict) -> str:
        """Explain a graded multiple-choice attempt without changing its answer."""
        chain = PromptTemplate.from_template(SECTION_C_PRACTICE_PROMPT) | self.llm | StrOutputParser()
        return chain.invoke({
            "evidence": evidence,
            "result": json.dumps(result, ensure_ascii=False),
            "progress": json.dumps(progress, ensure_ascii=False),
        })


# if __name__ == "__main__":
#     gen = AnswerGeneration(ragconfig)
#     # 模拟 retriever 返回的假证据(只测 generation,不连 Milvus、不调检索)
#     docs = [
#         "翻译是中华文化对外传播的重要途径,也是中外文化交流的桥梁。",
#         "随着全球化进程的加快,中国文化在世界上的影响力日益增强。",
#     ]
#     meta = [
#         {"source": "2024年12月第1套真题.pdf", "page": 3},
#         {"source": "2024年12月第1套真题.pdf", "page": 4},
#     ]
#     question = "2024年12月第1套听力部分讲了什么"
#     print(gen.generate(question, docs, meta))
