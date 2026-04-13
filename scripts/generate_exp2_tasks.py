"""生成大规模实验二任务（5×5 全空地，仅起终点变化）。

用法:
  python scripts/generate_exp2_tasks.py --out exp2_skill_reuse/tasks_overnight.json --count 80 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import List

_ROOT = Path(__file__).resolve().parent.parent

EMPTY_5 = [[0, 0, 0, 0, 0] for _ in range(5)]


def generate_tasks(count: int, seed: int) -> List[dict]:
    rng = random.Random(seed)
    pairs = set()
    out: List[dict] = []
    for i in range(count):
        tid = f"s{i + 1:03d}"
        for _ in range(10000):
            sr, sc = rng.randint(0, 4), rng.randint(0, 4)
            gr, gc = rng.randint(0, 4), rng.randint(0, 4)
            if (sr, sc) == (gr, gc):
                continue
            key = (sr, sc, gr, gc)
            if key in pairs:
                continue
            pairs.add(key)
            out.append(
                {
                    "id": tid,
                    "grid": [row[:] for row in EMPTY_5],
                    "start": [sr, sc],
                    "goal": [gr, gc],
                }
            )
            break
        else:
            raise RuntimeError(f"无法生成足够多样的起终点: {tid}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--count", type=int, default=80)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    tasks = generate_tasks(args.count, args.seed)
    out_path = args.out
    if not out_path.is_absolute():
        out_path = (_ROOT / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写入", out_path, "共", len(tasks), "条", file=sys.stderr)


if __name__ == "__main__":
    main()
