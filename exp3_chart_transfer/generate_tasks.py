"""生成实验三任务集：柱状图类（series）与表格类（table），可复现随机种子。

用法:
  python generate_tasks.py --out tasks_overnight.json --count 96 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List


def _pick_labels(rng: random.Random, k: int) -> List[str]:
    pool = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    rng.shuffle(pool)
    return [f"类{pool[i]}" for i in range(k)]


def _make_series_task(
    rng: random.Random,
    tid: str,
    task_type: str,
    categories: List[str],
    series: List[int],
) -> Dict[str, Any]:
    if task_type == "argmax_index":
        gold = max(range(len(series)), key=lambda i: series[i])
        q = "柱状图中**最高柱**对应类别在 series 中的**从零开始索引**是多少？只关心索引。"
    elif task_type == "argmin_index":
        gold = min(range(len(series)), key=lambda i: series[i])
        q = "柱状图中**最矮柱**对应类别在 series 中的**从零开始索引**是多少？"
    elif task_type == "max_minus_min":
        gold = max(series) - min(series)
        q = "柱状图所有类别中，**最大值减最小值**等于多少？"
    elif task_type == "sum_all":
        gold = sum(series)
        q = "柱状图所有类别数值之**总和**是多少？"
    elif task_type == "first_plus_last":
        gold = series[0] + series[-1]
        q = "第一个类别与最后一个类别数值之**和**是多少？"
    elif task_type == "mid_ratio_percent":
        a, b = series[0], series[1]
        gold = int(round(100.0 * a / b)) if b != 0 else 0
        q = "取前两个类别，计算 (第一个 / 第二个) * 100，**四舍五入为整数百分比**（无百分号）。若第二个为 0 则答案为 0。"
    else:
        raise ValueError(task_type)
    return {
        "id": tid,
        "task_type": task_type,
        "categories": categories,
        "series": series,
        "table": None,
        "gold": gold,
        "question": q,
    }


def _make_table_task(
    rng: random.Random,
    tid: str,
    task_type: str,
    table: List[List[int]],
    row_labels: List[str],
    col_labels: List[str],
) -> Dict[str, Any]:
    rows = len(table)
    cols = len(table[0]) if rows else 0
    r = rng.randrange(rows)
    c = rng.randrange(cols)
    if task_type == "table_cell":
        gold = table[r][c]
        q = (
            f"表格中第 {r} 行、第 {c} 列（**从零开始**行列索引）的数值是多少？"
            f"行标签为 {row_labels[r]!r}，列标签为 {col_labels[c]!r}。"
        )
    elif task_type == "row_sum":
        gold = sum(table[r])
        q = f"表格第 {r} 行（从零开始）所有列数值之**和**是多少？该行行标签为 {row_labels[r]!r}。"
    elif task_type == "col_sum":
        gold = sum(table[i][c] for i in range(rows))
        q = f"表格第 {c} 列（从零开始）所有行之**和**是多少？该列列标签为 {col_labels[c]!r}。"
    elif task_type == "argmax_row":
        sums = [sum(row) for row in table]
        gold = max(range(len(sums)), key=lambda i: sums[i])
        q = "哪一**行**（从零开始的行索引）的**行和**最大？若并列取较小索引。"
    elif task_type == "argmax_col":
        sums = [sum(table[i][c] for i in range(rows)) for c in range(cols)]
        gold = max(range(len(sums)), key=lambda i: sums[i])
        q = "哪一**列**（从零开始的列索引）的**列和**最大？若并列取较小索引。"
    else:
        raise ValueError(task_type)
    return {
        "id": tid,
        "task_type": task_type,
        "categories": [],
        "series": [],
        "table": table,
        "row_labels": row_labels,
        "col_labels": col_labels,
        "gold": gold,
        "question": q,
    }


def generate_tasks(count: int, seed: int) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    series_types = [
        "argmax_index",
        "argmin_index",
        "max_minus_min",
        "sum_all",
        "first_plus_last",
        "mid_ratio_percent",
    ]
    table_types = ["table_cell", "row_sum", "col_sum", "argmax_row", "argmax_col"]
    out: List[Dict[str, Any]] = []
    for i in range(count):
        tid = f"c{i + 1:03d}"
        if rng.random() < 0.55:
            k = rng.randint(4, 7)
            cats = _pick_labels(rng, k)
            series = [rng.randint(1, 48) for _ in range(k)]
            tt = rng.choice(series_types)
            out.append(_make_series_task(rng, tid, tt, cats, series))
        else:
            r = rng.randint(3, 5)
            c = rng.randint(3, 5)
            table = [[rng.randint(0, 20) for _ in range(c)] for _ in range(r)]
            row_labels = [f"R{j}" for j in range(r)]
            col_labels = [f"C{j}" for j in range(c)]
            tt = rng.choice(table_types)
            out.append(_make_table_task(rng, tid, tt, table, row_labels, col_labels))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("tasks_overnight.json"))
    ap.add_argument("--count", type=int, default=96)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    tasks = generate_tasks(args.count, args.seed)
    args.out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写入", args.out.resolve(), "共", len(tasks), "条", file=sys.stderr)


if __name__ == "__main__":
    main()
