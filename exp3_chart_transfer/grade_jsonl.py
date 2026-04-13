"""读取 exp3 模型输出 jsonl，统计方式 A / B 正确率。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from chart_evaluator import grade_mode_a, grade_mode_b, load_tasks


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    tasks = {t["id"]: t for t in load_tasks(args.tasks)}
    rows: List[Dict[str, Any]] = []
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            tid = rec["task_id"]
            mode = rec["mode"].lower()
            raw = rec["raw"]
            task = tasks[tid]
            if mode == "a":
                ok, reason = grade_mode_a(task, raw)
                rows.append({"task_id": tid, "mode": "a", "ok": ok, "reason": reason, "raw": raw})
            elif mode == "b":
                ok, reason = grade_mode_b(task, raw)
                rows.append({"task_id": tid, "mode": "b", "ok": ok, "reason": reason, "raw": raw})
            else:
                raise SystemExit(f"unknown mode: {mode}")

    def rate(sub: List[Dict[str, Any]]) -> float:
        if not sub:
            return 0.0
        return sum(1 for r in sub if r.get("ok")) / len(sub)

    a_rows = [r for r in rows if r["mode"] == "a"]
    b_rows = [r for r in rows if r["mode"] == "b"]
    summary = {
        "mode_a_accuracy": rate(a_rows),
        "mode_b_accuracy": rate(b_rows),
        "n_tasks": len(tasks),
        "n_a": len(a_rows),
        "n_b": len(b_rows),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.verbose:
        for r in rows:
            print(r["task_id"], r["mode"], r.get("ok"), r.get("reason", ""))

    if args.out:
        with args.out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
