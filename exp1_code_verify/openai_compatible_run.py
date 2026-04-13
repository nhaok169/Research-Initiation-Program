"""调用 OpenAI 兼容 Chat Completions API，批量跑 A/B 并写出 model_outputs.jsonl。

环境变量：
  OPENAI_API_KEY      必填
  OPENAI_BASE_URL     可选，默认 https://api.openai.com/v1
  OPENAI_MODEL        可选，默认 gpt-4o-mini（请改成你的 Qwen 端点名）

说明：当前请求为纯文本（ASCII 地图 + JSON grid）。若服务端要求多模态字段，需自行改 messages。
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from evaluator import build_prompt_block, load_tasks
from prompts import SYSTEM_SHARED, user_mode_a, user_mode_b


def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _extract_assistant_text(data: Dict[str, Any]) -> str:
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"unexpected API response: {data!r}") from e


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tasks", type=Path, default=Path(__file__).with_name("tasks.json"))
    p.add_argument("--out", type=Path, default=Path(__file__).with_name("model_outputs.jsonl"))
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--sleep", type=float, default=0.2, help="每次请求间隔秒数，防限流")
    args = p.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("请设置环境变量 OPENAI_API_KEY")

    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    url = f"{base}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    tasks = load_tasks(args.tasks)
    rows: List[Dict[str, Any]] = []

    for t in tasks:
        block = build_prompt_block(t)
        tid = t["id"]
        for mode, user_fn in (("a", user_mode_a), ("b", user_mode_b)):
            user = user_fn(block)
            payload = {
                "model": model,
                "temperature": args.temperature,
                "messages": [
                    {"role": "system", "content": SYSTEM_SHARED},
                    {"role": "user", "content": user},
                ],
            }
            try:
                data = _post_json(url, headers, payload)
                raw = _extract_assistant_text(data)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                raise SystemExit(f"HTTP {e.code} for {tid} mode={mode}: {err_body}") from e
            rows.append({"task_id": tid, "mode": mode, "raw": raw})
            time.sleep(args.sleep)

    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("已写入", args.out.resolve(), "共", len(rows), "条")


if __name__ == "__main__":
    main()
