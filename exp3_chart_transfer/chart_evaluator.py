"""实验三：图表/表格问答评估，支持 mode B 结构化诊断。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chart_sandbox import answers_match, diagnose_answer_code


def _ascii_bars(categories: List[str], series: List[float], width: int = 36) -> str:
    if not series:
        return "(无柱状数据)"
    m = max(series)
    if m <= 0:
        m = 1.0
    lines = []
    for name, v in zip(categories, series):
        w = max(0, min(width, int(round(v / m * width))))
        lines.append(f"{str(name):10} |{'#' * w} {v:g}")
    return "\n".join(lines)


def _ascii_table(table: List[List[float]], row_labels: List[str], col_labels: List[str]) -> str:
    if not table:
        return "(无表格数据)"
    header = "        " + "".join(f"{str(c):>8}" for c in col_labels)
    lines = [header]
    for r, row in enumerate(table):
        lab = str(row_labels[r]) if r < len(row_labels) else str(r)
        lines.append(f"{lab:8}" + "".join(f"{float(x):>8.4g}" for x in row))
    return "\n".join(lines)


def build_prompt_block(task: Dict[str, Any]) -> str:
    cats = [str(x) for x in task.get("categories") or []]
    series = [float(x) for x in task.get("series") or []]
    table = task.get("table")
    row_labels = [str(x) for x in task.get("row_labels") or []]
    col_labels = [str(x) for x in task.get("col_labels") or []]
    parts = [
        f"任务编号: {task['id']} ({task.get('task_type', '')})",
        str(task.get("question", "")).strip(),
        "",
    ]
    has_bars = bool(series and cats and len(series) == len(cats))
    if has_bars:
        parts.append("ASCII 柱状图（高度为数值，类别为横轴标签）：")
        parts.append(_ascii_bars(cats, series))
        parts.append("")
    if table:
        parts.append("数值表格（行标签 / 列标签如下，单位一致）：")
        parts.append(_ascii_table(table, row_labels, col_labels))
        parts.append("")
    if table and not has_bars:
        parts.append("说明：本题以表格为准；series 为空列表，请勿使用柱状序列下标。")
        parts.append("")
    if has_bars:
        parts.append(f"series JSON（与柱状图一致，按类别顺序）: {json.dumps(series, ensure_ascii=False)}")
    if table:
        parts.append(f"table JSON: {json.dumps(table, ensure_ascii=False)}")
    return "\n".join(parts) + "\n"


def extract_python_code(raw: str) -> str:
    blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if blocks:
        return blocks[-1].strip()
    return raw.strip()


def parse_text_number(raw: str) -> Optional[float]:
    text = raw.strip()
    if not text:
        return None
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text.replace(",", ""))
    if not nums:
        return None
    try:
        return float(nums[-1])
    except ValueError:
        return None


def grade_mode_a(task: Dict[str, Any], model_raw: str) -> Tuple[bool, str]:
    gold = task["gold"]
    val = parse_text_number(model_raw)
    if val is None:
        return False, "no_number_parsed"
    if answers_match(gold, val):
        return True, "ok"
    return False, f"wrong_number:parsed={val} gold={gold}"


def diagnose_mode_b(task: Dict[str, Any], model_raw: str) -> Dict[str, Any]:
    gold = task["gold"]
    series = [float(x) for x in task.get("series") or []]
    table = task.get("table")
    code = extract_python_code(model_raw)
    tbl = table if isinstance(table, list) and len(table) > 0 else None
    diag = diagnose_answer_code(code, series, tbl)
    if diag.ok:
        got = diag.answer
        if answers_match(gold, got):
            return {
                "ok": True,
                "reason": "ok",
                "error_bucket": "success",
                "error_code": "ok",
                "diagnostic_message": "执行成功，且答案与 gold 一致。",
                "line": None,
                "col": None,
                "end_line": None,
                "end_col": None,
                "fragment": code,
                "precise_location": False,
                "answer": got,
                "gold": gold,
                "code": code,
            }
        return {
            "ok": False,
            "reason": f"wrong_answer:got={got!r} gold={gold!r}",
            "error_bucket": "answer_wrong",
            "error_code": "wrong_answer",
            "diagnostic_message": f"代码成功执行，但得到答案 {got!r}，gold 为 {gold!r}。",
            "line": None,
            "col": None,
            "end_line": None,
            "end_col": None,
            "fragment": code,
            "precise_location": False,
            "answer": got,
            "gold": gold,
            "code": code,
        }
    assert diag.error is not None
    rec = diag.error.to_record()
    return {
        "ok": False,
        "reason": f"{rec['error_bucket']}:{rec['error_code']}",
        **rec,
        "answer": None,
        "gold": gold,
        "code": code,
    }


def grade_mode_b(task: Dict[str, Any], model_raw: str) -> Tuple[bool, str]:
    out = diagnose_mode_b(task, model_raw)
    return bool(out["ok"]), str(out["reason"])


def load_tasks(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)
