"""读取 exp2_results.jsonl，按条件汇总 completion_tokens，并做配对差值 scratch−skill。"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("exp2_results.jsonl"))
    args = ap.parse_args()

    by_task: Dict[str, Dict[str, Any]] = defaultdict(dict)
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            tid = r["task_id"]
            cond = r["condition"]
            by_task[tid][cond] = r

    scratch_ct: List[int] = []
    skill_ct: List[int] = []
    paired_diff: List[float] = []
    reach_s = []
    reach_k = []

    for tid, m in sorted(by_task.items()):
        if "scratch" not in m or "skill" not in m:
            print("警告: 任务缺一条条件", tid)
            continue
        sc = m["scratch"].get("completion_tokens")
        sk = m["skill"].get("completion_tokens")
        if isinstance(sc, int) and isinstance(sk, int):
            scratch_ct.append(sc)
            skill_ct.append(sk)
            paired_diff.append(float(sc - sk))
        if m["scratch"].get("reach_goal") is not None:
            reach_s.append(bool(m["scratch"]["reach_goal"]))
            reach_k.append(bool(m["skill"]["reach_goal"]))

    def mean(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else float("nan")

    def stdev(xs: List[float]) -> float:
        if len(xs) < 2:
            return float("nan")
        m = mean(xs)
        v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
        return math.sqrt(v)

    out = {
        "n_pairs": len(paired_diff),
        "completion_tokens_mean_scratch": round(mean(scratch_ct), 2) if scratch_ct else None,
        "completion_tokens_mean_skill": round(mean(skill_ct), 2) if skill_ct else None,
        "completion_tokens_stdev_scratch": round(stdev([float(x) for x in scratch_ct]), 2)
        if scratch_ct
        else None,
        "completion_tokens_stdev_skill": round(stdev([float(x) for x in skill_ct]), 2)
        if skill_ct
        else None,
        "paired_mean_scratch_minus_skill": round(mean(paired_diff), 2) if paired_diff else None,
        "skill_rate_vs_scratch_completion": round(mean(skill_ct) / mean(scratch_ct), 4)
        if scratch_ct and mean(scratch_ct) > 0
        else None,
        "reach_goal_rate_scratch": round(sum(reach_s) / len(reach_s), 4) if reach_s else None,
        "reach_goal_rate_skill": round(sum(reach_k) / len(reach_k), 4) if reach_k else None,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
