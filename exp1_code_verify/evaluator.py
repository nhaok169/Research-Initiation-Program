"""实验一：任务文本构建、从模型回复抽取代码、实验二复用的 grade_mode_b。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from env import GridEnv
from sandbox import UnsafeCodeError, exec_user_code


def _render_user_map(
    grid: List[List[int]], start: Tuple[int, int], goal: Tuple[int, int]
) -> str:
    lines = []
    for r, row in enumerate(grid):
        s = []
        for c, v in enumerate(row):
            if (r, c) == goal:
                s.append("G" if v == 0 else "G")
            elif (r, c) == start:
                s.append("S" if v == 0 else "?")
            else:
                s.append("#" if v == 1 else ".")
        lines.append("".join(s))
    return "\n".join(lines)


def build_prompt_block(task: Dict[str, Any]) -> str:
    sr, sc = task["start"]
    gr, gc = task["goal"]
    grid = task["grid"]
    m = _render_user_map(grid, (sr, sc), (gr, gc))
    return (
        f"任务编号: {task['id']} ({task.get('name', '')})\n"
        f"{task['question']}\n\n"
        f"ASCII 地图（S 起点，G 终点，# 墙，. 空地）：\n{m}\n\n"
        f"起点 (行,列) = ({sr},{sc})，终点 (行,列) = ({gr},{gc})。\n"
        f"grid JSON（0 空地 1 墙）：{json.dumps(grid, ensure_ascii=False)}\n"
    )


def extract_python_code(raw: str) -> str:
    blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if blocks:
        return blocks[-1].strip()
    return raw.strip()


def grade_mode_b(task: Dict[str, Any], model_raw: str) -> Tuple[bool, str]:
    """实验二沿用：非 strict 撞墙（静默失败），与历史行为一致。"""
    env = GridEnv(task["grid"], tuple(task["start"]), tuple(task["goal"]))
    env.reset()
    code = extract_python_code(model_raw)
    if not code.strip():
        return False, "empty_code"
    try:
        exec_user_code(code, env)
    except UnsafeCodeError as e:
        return False, f"unsafe_or_invalid:{e}"
    except Exception as e:
        return False, f"runtime_error:{type(e).__name__}:{e}"
    if env.at_goal():
        return True, "ok"
    return False, "executed_but_not_at_goal"


def load_tasks(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)
