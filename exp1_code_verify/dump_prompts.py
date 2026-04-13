"""把 10 个任务的 A/B 用户提示导出为文本文件，便于复制到 API 控制台或批处理。"""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluator import build_prompt_block, load_tasks
from prompts import SYSTEM_SHARED, user_mode_a, user_mode_b


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    p.add_argument("--out", type=Path, default=Path(__file__).with_name("prompt_dump"))
    args = p.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "SYSTEM.txt").write_text(SYSTEM_SHARED + "\n", encoding="utf-8")

    tasks = load_tasks(args.tasks)
    for t in tasks:
        block = build_prompt_block(t)
        tid = t["id"]
        (out / f"{tid}_mode_a_user.txt").write_text(user_mode_a(block), encoding="utf-8")
        (out / f"{tid}_mode_b_user.txt").write_text(user_mode_b(block), encoding="utf-8")

    print("已写入目录:", out.resolve())
    print("文件: SYSTEM.txt, 以及各 tXX_mode_a_user.txt / tXX_mode_b_user.txt")


if __name__ == "__main__":
    main()
