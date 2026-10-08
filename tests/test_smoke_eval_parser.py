import os  # 计算项目根。
import sys  # 补导入路径。


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from tools.smoke_eval import classify


def test_parser_categories():
    """四类判定 + "只认整行标题"这两条边界。

    这里只测纯函数,不构造 AnswerGeneration、不读缓存、不发请求 ——
    tools.smoke_eval 的所有真实调用都在 main() 里,import 它不花钱。
    """
    # 认的两种形状
    assert classify("**为什么选I**\n正文", "I") == ("MATCH", "I")          # 加粗标题
    assert classify("为什么选 I\n正文", "I") == ("MATCH", "I")             # 独占一行,无加粗
    assert classify("**为什么选A**\n正文", "I") == ("MISMATCH", "A")       # 抠出字母但不是 KEYS

    # 占位符没替换 → 单列一类
    assert classify("**为什么选[答案]**\n正文", "I") == ("PLACEHOLDER", None)
    assert classify("**为什么选[原文]**\n正文", "I") == ("PLACEHOLDER", None)

    # ★ 散文一律不认 —— 正文里出现"为什么选A"不能当成标题
    assert classify("因为为什么不选A是错的,所以答案不可能是 A。", "I") == ("UNPARSEABLE", None)
    assert classify("**本题复盘**\n没有答案节", "I") == ("UNPARSEABLE", None)


if __name__ == "__main__":
    test_parser_categories()
    print("PASS test_parser_categories")
