"""按 task_type 分层汇总 exp3 评分结果（需先 grade_jsonl 写出带 ok 的 jsonl）。"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List

from chart_evaluator import load_tasks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, default=Path("tasks.json"))
    ap.add_argument("--graded", type=Path, required=True, help="grade_jsonl.py --out 产出")
    args = ap.parse_args()

    tmap = {t["id"]: t for t in load_tasks(args.tasks)}
    by_type: DefaultDict[str, Dict[str, List[bool]]] = defaultdict(
        lambda: {"a": [], "b": []}
    )
    with args.graded.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            tid = r["task_id"]
            typ = tmap[tid].get("task_type", "?")
            mode = r["mode"]
            by_type[typ][mode].append(bool(r.get("ok")))

    out: Dict[str, Any] = {}
    for typ, modes in sorted(by_type.items()):
        def _rate(xs: List[bool]) -> float:
            return sum(1 for x in xs if x) / len(xs) if xs else 0.0

        out[typ] = {
            "mode_a": _rate(modes["a"]),
            "mode_b": _rate(modes["b"]),
            "n_a": len(modes["a"]),
            "n_b": len(modes["b"]),
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
