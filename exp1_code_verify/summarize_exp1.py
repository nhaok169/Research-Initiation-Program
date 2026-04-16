"""读取 run_exp1_compare.py 输出的 jsonl，汇总开环 vs 闭环。"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List


def _mean(xs: List[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    args = ap.parse_args()

    rows: List[Dict[str, Any]] = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    def collect(arm_key: str) -> Dict[str, float]:
        succ = [1.0 if r[arm_key].get("success") else 0.0 for r in rows]
        calls_if_ok = [
            float(r[arm_key]["calls_used"])
            for r in rows
            if r[arm_key].get("success")
        ]
        return {
            "n_tasks": float(len(rows)),
            "success_rate": _mean(succ),
            "mean_calls_when_success": _mean(calls_if_ok),
            "n_success": float(len(calls_if_ok)),
        }

    o = collect("open_loop")
    c = collect("closed_loop")
    first_round = [
        1.0 if r["closed_loop"].get("first_round_success") else 0.0 for r in rows
    ]
    out = {
        "open_loop": o,
        "closed_loop": {
            **c,
            "first_round_success_rate": _mean(first_round),
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(
        f"解读: 成功率 开环={o['success_rate']:.4f} 闭环={c['success_rate']:.4f}；"
        f"闭环首轮成功={out['closed_loop']['first_round_success_rate']:.4f}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
