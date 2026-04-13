"""在长时间批跑前检查 NVIDIA GPU 显存与利用率，避免与已有任务抢显存。

典型用法（本地 vLLM / TensorRT-LLM 占满 GPU 时拒绝启动）:
  python scripts/check_gpu_before_run.py --min-free-mib 8000 --max-util-pct 90

若无 nvidia-smi 或非 NVIDIA 环境，默认放行并打印提示。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import List, Optional, Tuple


def _parse_nvidia_smi_query() -> Optional[Tuple[List[int], List[int]]]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    free_mib: List[int] = []
    utils: List[int] = []
    for line in out.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\s*,\s*(\d+)\s*$", line)
        if not m:
            continue
        free_mib.append(int(m.group(1)))
        utils.append(int(m.group(2)))
    if not free_mib:
        return None
    return free_mib, utils


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--min-free-mib",
        type=int,
        default=2048,
        help="每块 GPU 可用显存下限（MiB），低于则退出码 2",
    )
    ap.add_argument(
        "--max-util-pct",
        type=int,
        default=95,
        help="任一块 GPU 利用率超过该百分比则退出码 3（表示可能被占用）",
    )
    ap.add_argument(
        "--skip-if-missing",
        action="store_true",
        help="无 nvidia-smi 时仍退出 0（默认行为已是放行，此项显式说明用途）",
    )
    args = ap.parse_args()
    _ = args.skip_if_missing

    parsed = _parse_nvidia_smi_query()
    if parsed is None:
        print(
            "[check_gpu] 未检测到 nvidia-smi 或解析失败：假定非本地 GPU 推理，放行。",
            file=sys.stderr,
        )
        sys.exit(0)

    free_mib, utils = parsed
    bad_mem = [i for i, m in enumerate(free_mib) if m < args.min_free_mib]
    bad_util = [i for i, u in enumerate(utils) if u > args.max_util_pct]

    if bad_mem:
        print(
            f"[check_gpu] 失败：GPU {bad_mem} 可用显存 MiB { [free_mib[i] for i in bad_mem] } "
            f"低于阈值 {args.min_free_mib}。",
            file=sys.stderr,
        )
        sys.exit(2)
    if bad_util:
        print(
            f"[check_gpu] 失败：GPU {bad_util} 利用率 { [utils[i] for i in bad_util] }% "
            f"高于阈值 {args.max_util_pct}%（可能已有推理进程）。",
            file=sys.stderr,
        )
        sys.exit(3)

    print(
        f"[check_gpu] 通过：各卡 free_MiB={free_mib} util%={utils} "
        f"(阈值 free>={args.min_free_mib}, util<={args.max_util_pct})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
