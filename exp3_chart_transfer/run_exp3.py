"""实验三：OpenAI 兼容 Chat Completions 批跑 A/B，写出 model_outputs.jsonl。

用法（在 exp3_chart_transfer 目录）:
  python generate_tasks.py --out tasks_overnight.json --count 96 --seed 42
  python run_exp3.py --config config.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from chart_evaluator import build_prompt_block, load_tasks
from prompts_chart import SYSTEM_CHART, user_mode_a, user_mode_b

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore[misc, assignment]


def _load_cfg(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _api_key(cfg: Dict[str, Any]) -> str:
    name = (cfg.get("api_key_env") or "").strip()
    if name:
        v = os.environ.get(name, "").strip()
        if not v:
            raise SystemExit(f"环境变量 {name} 未设置")
        return v
    for k in ("NVIDIA_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    raise SystemExit("请设置 api_key_env 或 NVIDIA_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY")


def _post(
    base_url: str,
    key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    timeout: float,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _content(data: Dict[str, Any]) -> str:
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def _usage(data: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    u = data.get("usage") or {}
    return (u.get("prompt_tokens"), u.get("completion_tokens"), u.get("total_tokens"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config.json"))
    args = ap.parse_args()
    root = args.config.parent.resolve()
    os.chdir(root)

    cfg = _load_cfg(args.config.resolve())
    base = str(cfg["base_url"]).strip()
    model = str(cfg["model"]).strip()
    temp = float(cfg.get("temperature", 0.0))
    timeout = float(cfg.get("request_timeout_seconds", 600))
    sleep_s = float(cfg.get("sleep_seconds", 0.25))
    tasks_path = Path(cfg.get("tasks_file", "tasks.json"))
    if not tasks_path.is_absolute():
        tasks_path = root / tasks_path
    out_path = Path(cfg.get("out_jsonl", "exp3_model_outputs.jsonl"))
    if not out_path.is_absolute():
        out_path = root / out_path

    tasks = load_tasks(tasks_path)
    key = _api_key(cfg)
    total = len(tasks) * 2
    bar = tqdm(total=total, desc="exp3", unit="req", file=sys.stderr) if tqdm else None

    rows: List[Dict[str, Any]] = []
    try:
        for t in tasks:
            block = build_prompt_block(t)
            tid = t["id"]
            for mode, fn in (("a", user_mode_a), ("b", user_mode_b)):
                user = fn(block)
                try:
                    data = _post(base, key, model, SYSTEM_CHART, user, temp, timeout)
                except urllib.error.HTTPError as e:
                    err = e.read().decode("utf-8", errors="replace")
                    raise SystemExit(f"HTTP {e.code} {tid} mode={mode}: {err}") from e
                raw = _content(data)
                pt, ct, tt = _usage(data)
                rows.append(
                    {
                        "task_id": tid,
                        "mode": mode,
                        "model": model,
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "total_tokens": tt,
                        "raw": raw,
                    }
                )
                if bar:
                    bar.update(1)
                time.sleep(sleep_s)
    finally:
        if bar:
            bar.close()

    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("已写入", out_path, "共", len(rows), "条。评分: python grade_jsonl.py --input", out_path.name)


if __name__ == "__main__":
    main()
