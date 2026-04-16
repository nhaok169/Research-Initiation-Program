"""将 exp3 任务渲染为 PNG 图像（vision 条件输入）。

用法:
  python render_task_images.py --tasks tasks_overnight.json --out-dir task_images
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _require_matplotlib() -> Any:
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise SystemExit("缺少 matplotlib，请执行: python -m pip install matplotlib") from e
    return plt


def _render_bar(task: Dict[str, Any], out_path: Path, plt: Any) -> None:
    cats = task["categories"]
    vals = task["series"]
    fig = plt.figure(figsize=(8, 4.8), dpi=120)
    ax = fig.add_subplot(111)
    ax.bar(range(len(vals)), vals, color="#4C78A8")
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([str(x) for x in cats])
    ax.set_ylabel("value")
    ax.set_title(f"{task['id']} | {task.get('task_type', '')}")
    fig.text(0.01, 0.01, str(task.get("question", "")), fontsize=9)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _render_table(task: Dict[str, Any], out_path: Path, plt: Any) -> None:
    table = task["table"]
    row_labels = task.get("row_labels", [])
    col_labels = task.get("col_labels", [])
    fig = plt.figure(figsize=(8, 4.8), dpi=120)
    ax = fig.add_subplot(111)
    ax.axis("off")
    tbl = ax.table(
        cellText=[[str(x) for x in row] for row in table],
        rowLabels=[str(x) for x in row_labels] if row_labels else None,
        colLabels=[str(x) for x in col_labels] if col_labels else None,
        loc="center",
    )
    tbl.scale(1, 1.4)
    ax.set_title(f"{task['id']} | {task.get('task_type', '')}")
    fig.text(0.01, 0.01, str(task.get("question", "")), fontsize=9)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, default=Path("tasks_overnight.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("task_images"))
    args = ap.parse_args()
    tasks: List[Dict[str, Any]] = json.loads(args.tasks.read_text(encoding="utf-8"))
    plt = _require_matplotlib()
    for t in tasks:
        out = args.out_dir / f"{t['id']}.png"
        if t.get("series") and t.get("categories"):
            _render_bar(t, out, plt)
        else:
            _render_table(t, out, plt)
    print(f"已渲染 {len(tasks)} 张图到 {args.out_dir.resolve()}")


if __name__ == "__main__":
    main()

