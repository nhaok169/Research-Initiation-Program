"""跑 API 前检查 tasks.json：起点/终点不在墙上、在界内、且存在通路。

用法: python validate_tasks.py [--tasks tasks.json]
失败时退出码 1 并打印具体任务 id 与原因。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _bfs(grid: List[List[int]], start: Tuple[int, int], goal: Tuple[int, int]) -> bool:
    rows, cols = len(grid), len(grid[0])
    q = deque([start])
    vis = {start}
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            return True
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if (
                0 <= nr < rows
                and 0 <= nc < cols
                and grid[nr][nc] == 0
                and (nr, nc) not in vis
            ):
                vis.add((nr, nc))
                q.append((nr, nc))
    return False


def validate(task: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    tid = task.get("id", "?")
    g = task.get("grid")
    if not g or not isinstance(g, list):
        return [f"{tid}: grid 无效"]
    rows = len(g)
    if rows == 0:
        return [f"{tid}: grid 空"]
    cols = len(g[0])
    for i, row in enumerate(g):
        if len(row) != cols:
            errs.append(f"{tid}: 第{i}行长度与首行不一致")
            return errs

    sr, sc = int(task["start"][0]), int(task["start"][1])
    gr, gc = int(task["goal"][0]), int(task["goal"][1])
    if not (0 <= sr < rows and 0 <= sc < cols):
        errs.append(f"{tid}: 起点越界 start={task['start']}")
    elif g[sr][sc] != 0:
        errs.append(f"{tid}: 起点在墙上 start={task['start']} cell={g[sr][sc]}")
    if not (0 <= gr < rows and 0 <= gc < cols):
        errs.append(f"{tid}: 终点越界 goal={task['goal']}")
    elif g[gr][gc] != 0:
        errs.append(f"{tid}: 终点在墙上 goal={task['goal']} cell={g[gr][gc]}")
    if errs:
        return errs
    if not _bfs(g, (sr, sc), (gr, gc)):
        errs.append(f"{tid}: 起点到终点无通路（BFS）")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    args = ap.parse_args()
    data = json.loads(args.tasks.read_text(encoding="utf-8"))
    all_errs: List[str] = []
    for t in data:
        all_errs.extend(validate(t))
    if all_errs:
        print("tasks.json 校验失败:", file=sys.stderr)
        for e in all_errs:
            print(" ", e, file=sys.stderr)
        print("\n修复 tasks.json 后请执行: python dump_prompts.py", file=sys.stderr)
        sys.exit(1)
    print("tasks.json 校验通过:", len(data), "个任务，起点/终点可通行。")


if __name__ == "__main__":
    main()
