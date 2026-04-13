"""导出 SYSTEM 与各任务的 A/B user 文本，便于与 exp1 相同的 bailian_batch_from_dump 流程。"""

from __future__ import annotations

import argparse
from pathlib import Path

from chart_evaluator import build_prompt_block, load_tasks
from prompts_chart import SYSTEM_CHART, user_mode_a, user_mode_b


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=Path("tasks.json"))
    p.add_argument("--out", type=Path, default=Path("prompt_dump"))
    args = p.parse_args()

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "SYSTEM.txt").write_text(SYSTEM_CHART + "\n", encoding="utf-8")
    for t in load_tasks(args.tasks):
        block = build_prompt_block(t)
        tid = t["id"]
        (out / f"{tid}_mode_a_user.txt").write_text(user_mode_a(block), encoding="utf-8")
        (out / f"{tid}_mode_b_user.txt").write_text(user_mode_b(block), encoding="utf-8")
    print("已写入目录:", out.resolve())


if __name__ == "__main__":
    main()
