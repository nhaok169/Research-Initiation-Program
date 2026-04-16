"""分析实验3 mode=b 的错误诊断分布。"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict

from chart_evaluator import load_tasks


def _bar(pct: float, width: int = 24) -> str:
    n = int(round(width * pct))
    return "#" * n + "-" * (width - n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graded", type=Path, required=True)
    ap.add_argument("--tasks", type=Path, default=Path("tasks.json"))
    args = ap.parse_args()

    tmap = {t["id"]: t for t in load_tasks(args.tasks)}
    rows = []
    with args.graded.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("mode") == "b":
                rows.append(r)

    total = len(rows)
    bucket = Counter()
    code = Counter()
    by_type: Dict[str, Counter[str]] = defaultdict(Counter)
    precise_failure = 0
    failed = 0

    for r in rows:
        b = r.get("error_bucket") or "other"
        c = r.get("error_code") or "other"
        bucket[b] += 1
        code[c] += 1
        typ = tmap.get(r["task_id"], {}).get("task_type", "?")
        by_type[typ][b] += 1
        if not r.get("ok"):
            failed += 1
            if r.get("precise_location"):
                precise_failure += 1

    print("## Mode B 诊断总览")
    print(json.dumps({
        "n_mode_b": total,
        "failure_count": failed,
        "precise_location_on_failures": precise_failure,
        "precise_location_rate_on_failures": (precise_failure / failed if failed else 0.0),
    }, ensure_ascii=False, indent=2))

    print("\n## 按错误大类")
    for k, v in bucket.most_common():
        pct = v / total if total else 0.0
        print(f"- {k}: {v} ({pct:.1%}) {_bar(pct)}")

    print("\n## 按错误代码")
    for k, v in code.most_common():
        pct = v / total if total else 0.0
        print(f"- {k}: {v} ({pct:.1%}) {_bar(pct)}")

    print("\n## 分题型错误分布")
    out: Dict[str, Any] = {}
    for typ in sorted(by_type):
        n = sum(by_type[typ].values())
        out[typ] = {
            b: {
                "count": c,
                "ratio": c / n if n else 0.0,
            }
            for b, c in sorted(by_type[typ].items())
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
