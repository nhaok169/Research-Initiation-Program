"""实验一：开环首轮提示与闭环修正提示。"""

from __future__ import annotations

from typing import Any, Dict

from evaluator import build_prompt_block

SYSTEM_CODE = (
    "你是网格导航编程助手。坐标为 (行,列)，先行后列；行号向下增大，列号向右增大。"
    "你必须严格依据给定的 grid（0 空地，1 墙）与起点、终点编写代码。"
)


def _code_protocol() -> str:
    return (
        "\n【输出协议 — 必须严格遵守】\n"
        "评测器已在沙箱里注入 **move(\"up\"|\"down\"|\"left\"|\"right\")**（只改变位置，无返回值）。\n"
        "**禁止**：def / class / import / print / while / if / 赋值 / 重新定义 move / "
        "除 range 以外的任何函数调用。\n"
        "**只允许** 两种顶层语句，且只能写在一个 ```python 代码块中，不要多余解释：\n"
        "  1) move(\"down\")  单行调用，方向为英文小写；\n"
        "  2) for _ in range(3): move(\"up\")  其中 range( ) 内必须是正整数常量。\n"
        "可写多行、多个 for。示例：\n"
        "```python\n"
        "for i in range(4):\n"
        "    move(\"down\")\n"
        "for i in range(4):\n"
        "    move(\"right\")\n"
        "```\n"
    )


def build_open_loop_prompt(task: Dict[str, Any]) -> str:
    """单次独立对话的首条 user：任务描述 + 代码协议（与历史「方式 B」一致）。"""
    return build_prompt_block(task) + _code_protocol()


def build_feedback_prompt(task: Dict[str, Any], previous_code: str, error_message: str) -> str:
    """闭环下一轮 user：附上上一轮代码与沙箱/执行器返回的错误说明。"""
    block = build_prompt_block(task)
    code_show = previous_code.strip() or "（未能提取到代码）"
    return (
        block
        + "\n你上一轮提交的代码在执行时出现以下问题，请**只输出修正后的完整** ```python 代码块"
        "（仍需满足同一协议），不要复述错误：\n\n"
        f"【错误信息】\n{error_message}\n\n"
        f"【上一轮代码】\n```python\n{code_show}\n```\n"
    )
