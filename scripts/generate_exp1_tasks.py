"""生成大规模实验一网格任务，写入 JSON。

用法（在仓库根目录）:
  # 默认：全空地 + 题干给出净位移（推荐，便于 Mode B 在成功率上超过 Mode A）
  python scripts/generate_exp1_tasks.py --out exp1_code_verify/tasks_overnight.json --count 80 --seed 42

  # 旧版：随机墙迷宫（与早期 overnight 可比，但 A/B 终局率往往都极低）
  python scripts/generate_exp1_tasks.py --preset random_maze --out ... --count 80 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import deque
from pathlib import Path
from typing import List, Tuple

# 允许从仓库根或 experiments 下调用
_ROOT = Path(__file__).resolve().parent.parent


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


def _try_one(
    rng: random.Random, rows: int, cols: int, wall_p: float
) -> Tuple[List[List[int]], Tuple[int, int], Tuple[int, int]] | None:
    grid = [[1 if rng.random() < wall_p else 0 for _ in range(cols)] for _ in range(rows)]
    free = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 0]
    if len(free) < 2:
        return None
    rng.shuffle(free)
    start, goal = free[0], free[1]
    if not _bfs(grid, start, goal):
        return None
    return grid, start, goal


def generate_random_maze_tasks(
    count: int,
    seed: int,
    rows_min: int,
    rows_max: int,
    cols_min: int,
    cols_max: int,
    wall_p_min: float,
    wall_p_max: float,
) -> List[dict]:
    rng = random.Random(seed)
    out: List[dict] = []
    q = (
        "在下方网格中，坐标为(行,列)，#为墙。.为空地。请让角色从起点走到终点。"
        "墙用1表示、空地为0（见 JSON 状态）。"
    )
    for i in range(count):
        tid = f"t{i + 1:03d}"
        for _ in range(5000):
            rows = rng.randint(rows_min, rows_max)
            cols = rng.randint(cols_min, cols_max)
            wall_p = rng.uniform(wall_p_min, wall_p_max)
            got = _try_one(rng, rows, cols, wall_p)
            if got is None:
                continue
            grid, (sr, sc), (gr, gc) = got
            out.append(
                {
                    "id": tid,
                    "name": f"随机实例{i + 1}",
                    "grid": grid,
                    "start": [sr, sc],
                    "goal": [gr, gc],
                    "question": q,
                }
            )
            break
        else:
            raise RuntimeError(f"无法在限定尝试内生成任务 {tid}，请放宽 wall 概率或增大网格")
    return out


def generate_open_manhattan_tasks(
    count: int,
    seed: int,
    size: int,
    dist_min: int,
    dist_max: int,
) -> List[dict]:
    """全空地；题干写明 Δr、Δc 与最短步数，配合评测器对 A 侧「步数=最短路」约束。"""
    rng = random.Random(seed)
    out: List[dict] = []
    tmpl = (
        "场地为 {rows}×{cols} **全空地**（grid 全为 0），无任何墙，坐标 (行,列)，行向下增大、列向右增大。\n"
        "起点 (行,列)=({sr},{sc})，终点 (行,列)=({gr},{gc})。\n"
        "**净移动量**：行方向 Δr={dr}（正为向下、负为向上）；"
        "列方向 Δc={dc}（正为向右、负为向左）。\n"
        "单调最短走法的总步数为 |Δr|+|Δc|={total}。**你的答案中移动总步数必须恰好等于 {total}。**\n"
        "用 up/down/left/right（或 上/下/左/右）描述每一步；描述多步时请用阿拉伯数字写步数。"
    )
    for i in range(count):
        tid = f"t{i + 1:03d}"
        for _ in range(8000):
            sr, sc = rng.randrange(size), rng.randrange(size)
            gr, gc = rng.randrange(size), rng.randrange(size)
            if (sr, sc) == (gr, gc):
                continue
            total = abs(sr - gr) + abs(sc - gc)
            if not (dist_min <= total <= dist_max):
                continue
            dr = gr - sr
            dc = gc - sc
            grid = [[0] * size for _ in range(size)]
            out.append(
                {
                    "id": tid,
                    "name": f"空地曼哈顿{i + 1}",
                    "open_field": True,
                    "grid": grid,
                    "start": [sr, sc],
                    "goal": [gr, gc],
                    "question": tmpl.format(
                        rows=size,
                        cols=size,
                        sr=sr,
                        sc=sc,
                        gr=gr,
                        gc=gc,
                        dr=dr,
                        dc=dc,
                        total=total,
                    ),
                }
            )
            break
        else:
            raise RuntimeError(f"无法在限定尝试内生成 open_manhattan 任务 {tid}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--preset",
        choices=("open_manhattan", "random_maze"),
        default="open_manhattan",
        help="open_manhattan=全空地+净位移（默认）；random_maze=随机墙",
    )
    ap.add_argument("--out", type=Path, required=True, help="输出 tasks.json 路径")
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rows-min", type=int, default=5)
    ap.add_argument("--rows-max", type=int, default=8)
    ap.add_argument("--cols-min", type=int, default=5)
    ap.add_argument("--cols-max", type=int, default=8)
    ap.add_argument("--wall-p-min", type=float, default=0.12)
    ap.add_argument("--wall-p-max", type=float, default=0.38)
    ap.add_argument("--open-size", type=int, default=9, help="open_manhattan 方形边长")
    ap.add_argument("--open-dist-min", type=int, default=6)
    ap.add_argument("--open-dist-max", type=int, default=14)
    args = ap.parse_args()

    if args.preset == "open_manhattan":
        tasks = generate_open_manhattan_tasks(
            args.count,
            args.seed,
            args.open_size,
            args.open_dist_min,
            args.open_dist_max,
        )
    else:
        tasks = generate_random_maze_tasks(
            args.count,
            args.seed,
            args.rows_min,
            args.rows_max,
            args.cols_min,
            args.cols_max,
            args.wall_p_min,
            args.wall_p_max,
        )

    out_path = args.out
    if not out_path.is_absolute():
        out_path = (_ROOT / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写入", out_path, "共", len(tasks), "条 preset=", args.preset, file=sys.stderr)


if __name__ == "__main__":
    main()
