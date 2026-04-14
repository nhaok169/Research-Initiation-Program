"""读取 API 保存的 jsonl，统计方式 A / B 正确率。用法见文件末尾 docstring。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from evaluator import grade_mode_a, grade_mode_b, load_tasks, summarize_results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    p.add_argument("--input", type=Path, required=True, help="jsonl: 每行 task_id, mode, raw")
    p.add_argument("--out", type=Path, default=None, help="写出带分数的 jsonl")
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="逐条打印 task_id、mode、reason，便于排查模式 B 为何未得分",
    )
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
                ok, reason, acts = grade_mode_a(task, raw)
                rows.append(
                    {
                        "task_id": tid,
                        "mode": "a",
                        "a_ok": ok,
                        "reason": reason,
                        "parsed_actions": acts,
                        "raw": raw,
                    }
                )
            elif mode == "b":
                ok, reason = grade_mode_b(task, raw)
                rows.append(
                    {
                        "task_id": tid,
                        "mode": "b",
                        "b_ok": ok,
                        "reason": reason,
                        "raw": raw,
                    }
                )
            else:
                raise SystemExit(f"unknown mode: {mode}")

    summary = summarize_results(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.verbose:
        print("--- 明细 ---")
        for r in rows:
            rid = r["task_id"]
            m = r["mode"]
            rs = r.get("reason", "")
            ok = r.get("a_ok") if m == "a" else r.get("b_ok")
            print(f"{rid}  {m}  ok={ok}  {rs}")

    if args.out:
        with args.out.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
