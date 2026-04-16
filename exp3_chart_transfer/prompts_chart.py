"""实验三：图表 / 表格代码协议提示。"""

SYSTEM_CHART = (
    "你是数据分析助手。题目以 ASCII 柱状图与/或文本表格形式给出数值，你必须严格依据题干与 JSON 中的数据作答。"
    "不要编造未给出的数字。"
)


def user_mode_a(block: str) -> str:
    return (
        block
        + "
【方式 A】请只用自然语言给出最终答案（一个明确的数值）。"
        "如需中间推理可写简短文字，但最后答案必须是一个数字，便于自动抽取。"
        "不要写代码，不要写 markdown 代码块。"
    )


def user_mode_b(block: str) -> str:
    example = (
        "
【方式 B — 必须严格遵守，否则判错】
"
        "评测器已在沙箱注入只读变量 **series**（柱状序列，与 JSON 一致）"
        "以及（若题目含表格）**table**（二维数值表）。
"
        "你可使用以下**唯一**形式的代码：在 ```python 代码块中写**恰好一行**赋值：
"
        "  ans = <表达式>
"
        "表达式中允许：整数/小数常量、+ - * / // %、括号、series[i]、table[r][c]（若存在表格）、"
        "以及函数 len(series)/len(table)、max(两参数) / min(两参数) / abs / int / float、"
        "argmax(series) / argmin(series) / sum_series(series) / max_series(series) / min_series(series)、"
        "以及（仅表格题）row_sum(table, 行号字面量) / col_sum(table, 列号字面量) / "
        "argmax_row(table) / argmax_col(table)。
"
        "**禁止**：其它名字、import、def、for、while、print、多行语句、对 series/table 赋值、"
        "使用 sum(table[...])、切片、条件表达式。
"
        "合法示例：
"
        "```python
"
        "ans = argmax(series)
"
        "```
"
        "表格求和示例：
"
        "```python
"
        "ans = row_sum(table, 2)
"
        "```
"
    )
    return block + example
