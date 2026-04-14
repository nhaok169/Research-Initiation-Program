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
from typing import Any, Dict, List, Set, Tuple

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


def _is_retryable_http(code: int) -> bool:
    return code in {429, 500, 502, 503, 504}


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
    ap.add_argument("--fresh", action="store_true", help="忽略已有 out_jsonl，从头重跑")
    args = ap.parse_args()
    root = args.config.parent.resolve()
    os.chdir(root)

    cfg = _load_cfg(args.config.resolve())
    base = str(cfg["base_url"]).strip()
    model = str(cfg["model"]).strip()
    temp = float(cfg.get("temperature", 0.0))
    timeout = float(cfg.get("request_timeout_seconds", 600))
    sleep_s = float(cfg.get("sleep_seconds", 0.25))
    max_retries = int(cfg.get("max_retries", 5))
    retry_backoff_sec = float(cfg.get("retry_backoff_seconds", 8.0))
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
    done_pairs: Set[Tuple[str, str]] = set()
    if out_path.exists() and not args.fresh:
        with out_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    tid = str(r.get("task_id", ""))
                    mode = str(r.get("mode", "")).lower()
                    if tid and mode in {"a", "b"}:
                        done_pairs.add((tid, mode))
                        rows.append(r)
                except Exception:
                    continue
        print(f"[断点续跑] 已完成 {len(done_pairs)} 条，继续补跑。", file=sys.stderr)
    elif args.fresh and out_path.exists():
        out_path.write_text("", encoding="utf-8")
    try:
        for t in tasks:
            block = build_prompt_block(t)
            tid = t["id"]
            for mode, fn in (("a", user_mode_a), ("b", user_mode_b)):
                if (tid, mode) in done_pairs:
                    if bar:
                        bar.update(1)
                    continue
                user = fn(block)
                last_err = ""
                data: Dict[str, Any] = {}
                ok_req = False
                for attempt in range(1, max_retries + 2):
                    try:
                        data = _post(base, key, model, SYSTEM_CHART, user, temp, timeout)
                        ok_req = True
                        break
                    except urllib.error.HTTPError as e:
                        err = e.read().decode("utf-8", errors="replace")
                        last_err = f"HTTP {e.code} {tid} mode={mode}: {err}"
                        if attempt <= max_retries and _is_retryable_http(e.code):
                            wait_s = retry_backoff_sec * attempt
                            print(
                                f"[重试 {attempt}/{max_retries}] {tid} mode={mode} HTTP {e.code}，{wait_s:.1f}s 后重试",
                                file=sys.stderr,
                            )
                            time.sleep(wait_s)
                            continue
                        raise SystemExit(last_err) from e
                    except (TimeoutError, urllib.error.URLError, OSError) as e:
                        last_err = f"请求异常 {tid} mode={mode}: {type(e).__name__}:{e}"
                        if attempt <= max_retries:
                            wait_s = retry_backoff_sec * attempt
                            print(
                                f"[重试 {attempt}/{max_retries}] {last_err}，{wait_s:.1f}s 后重试",
                                file=sys.stderr,
                            )
                            time.sleep(wait_s)
                            continue
                        raise SystemExit(last_err) from e
                if not ok_req:
                    raise SystemExit(last_err or f"请求失败: {tid} mode={mode}")
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
                done_pairs.add((tid, mode))
                with out_path.open("a", encoding="utf-8") as fa:
                    fa.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
                if bar:
                    bar.update(1)
                time.sleep(sleep_s)
    finally:
        if bar:
            bar.close()

    print("已写入", out_path, "共", len(done_pairs), "条。评分: python grade_jsonl.py --input", out_path.name)


if __name__ == "__main__":
    main()
