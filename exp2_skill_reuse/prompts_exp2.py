"""实验二：从零 vs 技能模板 的用户提示构造。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

_EXP1 = Path(__file__).resolve().parent.parent / "exp1_code_verify"
sys.path.insert(0, str(_EXP1))
from evaluator import build_prompt_block  # noqa: E402

SKILL_VERSION = "v1"

SYSTEM = (
    "你是网格导航代码助手。坐标为 (行,列)，行向下增大，列向右增大。"
    "环境将注入 move(\"up\"|\"down\"|\"left\"|\"right\")，无返回值。"
    "只允许顶层 move(\"...\") 与 for _ in range(正整数常量): move(\"...\")；"
    "禁止 def/import/print/while/赋值。"
)


def _manhattan_dirs(
    sr: int, sc: int, gr: int, gc: int
) -> Tuple[str, str, int, int]:
    """先纵向后横向；返回 (竖直方向, 横向方向, 竖直步数, 横向步数)。"""
    dr = gr - sr
    dc = gc - sc
    vdir = "down" if dr >= 0 else "up"
    hdir = "right" if dc >= 0 else "left"
    return vdir, hdir, abs(dr), abs(dc)


def user_scratch(task: Dict[str, Any]) -> str:
    block = build_prompt_block(
        {
            **task,
            "name": "无障碍曼哈顿",
            "question": "网格为全空地（无墙）。请从零写出到达终点的代码，仅用 move 与 for+range(常量)。",
        }
    )
    return (
        block
        + "\n【条件：从零】未提供任何技能模板。请只输出一个 ```python 代码块，不要解释。"
    )


def user_skill(task: Dict[str, Any]) -> str:
    block = build_prompt_block(
        {
            **task,
            "name": "无障碍曼哈顿",
            "question": "网格为全空地（无墙）。",
        }
    )
    sr, sc = int(task["start"][0]), int(task["start"][1])
    gr, gc = int(task["goal"][0]), int(task["goal"][1])
    vdir, hdir, vn, hn = _manhattan_dirs(sr, sc, gr, gc)
    skill = (
        f"\n【可复用技能 · SKILL_VERSION={SKILL_VERSION}】\n"
        "在「全是 0、无墙」的网格上，从起点到终点可走曼哈顿路径："
        "先完成全部纵向移动，再完成全部横向移动（方向已按本题算好）。\n"
        "你只需把下面两行中 range( ) 里的数字填成**非负整数**（与上述步数一致），"
        "方向字符串**不要改**：\n"
        f"for i in range(____): move(\"{vdir}\")\n"
        f"for i in range(____): move(\"{hdir}\")\n"
        "若某维步数为 0，对应 range 填 0。\n"
        "\n【条件：技能】请只输出填好数字后的**一个** ```python 代码块，不要解释。"
    )
    return block + skill
