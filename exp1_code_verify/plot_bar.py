"""根据 grade_jsonl 打印的 summary 或自定义数字绘制柱状图（需 matplotlib）。"""

from __future__ import annotations

import argparse
import json


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--summary-json",
        type=str,
        default="",
        help='例如 {"mode_a":0.45,"mode_b":0.95}',
    )
    p.add_argument("--out", type=str, default="exp1_accuracy.png")
    args = p.parse_args()
    data = json.loads(args.summary_json)
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise SystemExit("需要 matplotlib：pip install matplotlib") from e

    labels = ["A 纯文本", "B 代码执行"]
    vals = [float(data["mode_a"]), float(data["mode_b"])]
    plt.figure(figsize=(4, 3))
    plt.bar(labels, vals, color=["#6baed6", "#74c476"])
    plt.ylim(0, 1.05)
    plt.ylabel("正确率")
    plt.title("实验一：过程验证信号（示例）")
    for i, v in enumerate(vals):
        plt.text(i, v + 0.02, f"{v*100:.0f}%", ha="center")
    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print("saved", args.out)


if __name__ == "__main__":
    main()
