"""对实验一的模型输出打分：方式 A（文本动作序列）与方式 B（可执行代码）。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from env import GridEnv, DIR_MAP
from sandbox import UnsafeCodeError, exec_user_code


def _render_user_map(grid: List[List[int]], start: Tuple[int, int], goal: Tuple[int, int]) -> str:
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
    blocks = re.findall(
        r"```(?:python)?\s*([\s\S]*?)```", raw, re.IGNORECASE
    )
    if blocks:
        return blocks[-1].strip()
    return raw.strip()


_TOKEN_PATTERNS = [
    (re.compile(r"\bup\b", re.I), "up"),
    (re.compile(r"\bdown\b", re.I), "down"),
    (re.compile(r"\bleft\b", re.I), "left"),
    (re.compile(r"\bright\b", re.I), "right"),
    (re.compile(r"\bu\b", re.I), "up"),
    (re.compile(r"\bd\b", re.I), "down"),
    (re.compile(r"\bl\b", re.I), "left"),
    (re.compile(r"\br\b", re.I), "right"),
    (re.compile(r"上"), "up"),
    (re.compile(r"下"), "down"),
    (re.compile(r"左"), "left"),
    (re.compile(r"右"), "right"),
]


def parse_text_actions(raw: str) -> List[str]:
    """从自然语言或列表中抽取动作序列（用于方式 A 的自动核对，可与人工标注对照）。"""
    text = raw.strip()
    bracket = re.search(r"\[([^\]]+)\]", text)
    if bracket:
        text = bracket.group(1)
    parts = re.split(r"[,，;\n|]+", text)
    actions: List[str] = []
    for p in parts:
        chunk = p.strip()
        if not chunk:
            continue
        mrep = re.search(
            r"(向上|向下|向左|向右|上|下|左|右)\s*(\d+)\s*步?", chunk
        )
        if mrep:
            mp = {"向上": "up", "上": "up", "向下": "down", "下": "down", "向左": "left", "左": "left", "向右": "right", "右": "right"}
            d = mp[mrep.group(1)]
            for _ in range(int(mrep.group(2))):
                actions.append(d)
            continue
        num_word = re.match(
            r"^(向上|向下|向左|向右|上|下|左|右)\s*([一二三四五六七八九十]+)\s*步?$",
            chunk,
        )
        if num_word:
            cn = "一二三四五六七八九十"
            mp = {"向上": "up", "上": "up", "向下": "down", "下": "down", "向左": "left", "左": "left", "向右": "right", "右": "right"}
            d = mp[num_word.group(1)]
            nmap = {cn[i]: i + 1 for i in range(len(cn))}
            val = nmap.get(num_word.group(2), 1)
            for _ in range(val):
                actions.append(d)
            continue
        matched = False
        for rx, name in _TOKEN_PATTERNS:
            if rx.search(chunk):
                actions.append(name)
                matched = True
                break
        if not matched:
            low = chunk.lower().replace(" ", "")
            for ch, name in zip(
                ["u", "d", "l", "r"], ["up", "down", "left", "right"]
            ):
                if low == ch:
                    actions.append(name)
                    matched = True
                    break
    return actions


def grade_mode_a(task: Dict[str, Any], model_raw: str) -> Tuple[bool, str, List[str]]:
    env = GridEnv(task["grid"], tuple(task["start"]), tuple(task["goal"]))
    env.reset()
    actions = parse_text_actions(model_raw)
    if not actions:
        return False, "no_actions_parsed", actions
    for a in actions:
        key = a
        if key not in DIR_MAP:
            return False, f"unknown_action:{a}", actions
        env.move(key)
    return env.at_goal(), "ok" if env.at_goal() else "not_at_goal", actions


def grade_mode_b(task: Dict[str, Any], model_raw: str) -> Tuple[bool, str]:
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


def summarize_results(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    a_rows = [r for r in rows if "a_ok" in r]
    b_rows = [r for r in rows if "b_ok" in r]

    def rate(sub: List[Dict[str, Any]], key: str) -> float:
        if not sub:
            return 0.0
        return sum(1 for r in sub if r.get(key)) / len(sub)

    return {"mode_a": rate(a_rows, "a_ok"), "mode_b": rate(b_rows, "b_ok")}
