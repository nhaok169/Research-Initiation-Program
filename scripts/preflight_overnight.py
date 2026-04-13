"""夜间批跑前自检：本地 GPU 状态 + NVIDIA_API_KEY + 一次极小 Chat 冒烟请求。

用法（在 experiments 目录）:
  export NVIDIA_API_KEY=...
  python3 scripts/preflight_overnight.py

仅看 GPU、不调 API:
  python3 scripts/preflight_overnight.py --skip-api

说明：NVIDIA NIM 为云端推理，本机 GPU 占用与 API 无关；本脚本仍打印 nvidia-smi 便于你发现本机是否已被其它任务占满。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def _run_nvidia_smi() -> None:
    print("--- nvidia-smi（摘要）---", file=sys.stderr)
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.free,utilization.gpu", "--format=csv,noheader"],
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        print("未找到 nvidia-smi（可能无 NVIDIA 驱动或非 GPU 机器）。", file=sys.stderr)
        return
    except subprocess.CalledProcessError as e:
        print("nvidia-smi 失败:", e, file=sys.stderr)
        return
    for line in out.strip().splitlines():
        print(" ", line, file=sys.stderr)


def _post_smoke(base_url: str, api_key: str, model: str, timeout: float) -> None:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 8,
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": 'Reply with exactly: OK'},
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    try:
        text = (body["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"无法解析响应: {json.dumps(body, ensure_ascii=False)[:500]}") from e
    print("--- API 冒烟 ---", file=sys.stderr)
    print("  model =", model, file=sys.stderr)
    print("  reply =", repr(text[:200]), file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-api", action="store_true", help="不发起网络请求")
    ap.add_argument(
        "--base-url",
        default=os.environ.get("OVERNIGHT_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    )
    ap.add_argument(
        "--model",
        default=os.environ.get(
            "OVERNIGHT_MODEL",
            "microsoft/phi-3.5-vision-instruct",
        ),
    )
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args()

    _run_nvidia_smi()

    if args.skip_api:
        print("已跳过 API 测试（--skip-api）。", file=sys.stderr)
        return

    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not key:
        print("错误: 未设置环境变量 NVIDIA_API_KEY。", file=sys.stderr)
        sys.exit(1)

    try:
        _post_smoke(args.base_url, key, args.model, args.timeout)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err}", file=sys.stderr)
        print(
            "提示: NVIDIA 文档里多模态 Phi 的 model 为 microsoft/phi-3.5-vision-instruct（3.5 带点）。"
            "若仍失败可试 OVERNIGHT_MODEL=meta/llama-3.2-3b-instruct。",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as e:
        print("API 冒烟失败:", e, file=sys.stderr)
        sys.exit(2)

    print("preflight 通过。", file=sys.stderr)


if __name__ == "__main__":
    main()
