"""exp3 vision 条件跑批（把任务图像 + 文本问题送入 VLM）。

用法:
  python render_task_images.py --tasks tasks_overnight.json --out-dir task_images
  python run_exp3_vision.py --config config.vision.example.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Set

from chart_evaluator import load_tasks
from prompts_chart import SYSTEM_CHART


def _load_cfg(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _api_key(cfg: Dict[str, Any]) -> str:
    var = (cfg.get("api_key_env") or "NVIDIA_API_KEY").strip()
    key = os.environ.get(var, "").strip()
    if not key:
        raise SystemExit(f"环境变量 {var} 未设置")
    return key


def _post(base_url: str, api_key: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
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
        return json.loads(resp.read().decode("utf-8"))


def _is_retryable_http(code: int) -> bool:
    return code in {429, 500, 502, 503, 504}


def _content(data: Dict[str, Any]) -> str:
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config.vision.example.json"))
    ap.add_argument("--fresh", action="store_true", help="从头重跑并清空 out_jsonl")
    args = ap.parse_args()
    cfg = _load_cfg(args.config)
    base_url = str(cfg.get("base_url", "")).strip()
    model = str(cfg.get("model", "")).strip()
    key = _api_key(cfg)
    tasks_file = Path(cfg.get("tasks_file", "tasks_overnight.json"))
    image_dir = Path(cfg.get("image_dir", "task_images"))
    out = Path(cfg.get("out_jsonl", "exp3_vision_outputs.jsonl"))
    timeout = float(cfg.get("request_timeout_seconds", 600))
    sleep_s = float(cfg.get("sleep_seconds", 0.3))
    max_tasks = int(cfg.get("max_tasks", 80))
    max_retries = int(cfg.get("max_retries", 8))
    retry_backoff_sec = float(cfg.get("retry_backoff_seconds", 8.0))

    done: Set[str] = set()
    if out.exists() and not args.fresh:
        with out.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    tid = str(rec.get("task_id", ""))
                    if tid:
                        done.add(tid)
                except Exception:
                    continue
        print(f"[断点续跑] 已完成 {len(done)} 条，将跳过。")
    elif args.fresh and out.exists():
        out.write_text("", encoding="utf-8")

    tasks = load_tasks(tasks_file)[:max_tasks]
    wrote = 0
    for t in tasks:
        tid = t["id"]
        if tid in done:
            continue
        img_path = image_dir / f"{tid}.png"
        if not img_path.is_file():
            raise SystemExit(f"缺少图像: {img_path}")
        b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
        user = (
            f"任务编号: {tid}\n"
            f"{t.get('question', '')}\n"
            "请只输出最终数值，不要解释。\n"
            f'<img src="data:image/png;base64,{b64}" />'
        )
        payload = {
            "model": model,
            "temperature": float(cfg.get("temperature", 0.0)),
            "messages": [
                {"role": "system", "content": SYSTEM_CHART},
                {"role": "user", "content": user},
            ],
        }
        ok_req = False
        data: Dict[str, Any] = {}
        last_err = ""
        for attempt in range(1, max_retries + 2):
            try:
                data = _post(base_url, key, payload, timeout)
                ok_req = True
                break
            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", errors="replace")
                last_err = f"HTTP {e.code} {tid}: {err}"
                if attempt <= max_retries and _is_retryable_http(e.code):
                    wait_s = retry_backoff_sec * attempt
                    print(f"[重试 {attempt}/{max_retries}] {tid} HTTP {e.code}，{wait_s:.1f}s 后重试")
                    time.sleep(wait_s)
                    continue
                raise SystemExit(last_err) from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = f"请求异常 {tid}: {type(e).__name__}:{e}"
                if attempt <= max_retries:
                    wait_s = retry_backoff_sec * attempt
                    print(f"[重试 {attempt}/{max_retries}] {last_err}，{wait_s:.1f}s 后重试")
                    time.sleep(wait_s)
                    continue
                raise SystemExit(last_err) from e
        if not ok_req:
            raise SystemExit(last_err or f"请求失败: {tid}")
        usage = data.get("usage") or {}
        rec = {
            "task_id": tid,
            "mode": "vision_a",
            "model": model,
            "raw": _content(data),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        wrote += 1
        time.sleep(sleep_s)
    print(f"已写入 {out.resolve()}，本次新增 {wrote} 条（vision 条件）")


if __name__ == "__main__":
    main()

