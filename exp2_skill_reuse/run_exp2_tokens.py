"""实验二：对每个任务依次请求「从零」「技能」两种 user，记录 usage token 与可选正确率。

配置：复制 config.example.json 为 config.json。环境变量见 api_key_env。

用法（在 exp2_skill_reuse 目录）:
  $env:NVIDIA_API_KEY = '...'
  python run_exp2_tokens.py --config config.json
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_EXP1 = Path(__file__).resolve().parent.parent / "exp1_code_verify"
sys.path.insert(0, str(_EXP1))

from evaluator import grade_mode_b  # noqa: E402

from prompts_exp2 import SKILL_VERSION, SYSTEM, user_scratch, user_skill

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore


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
    raise SystemExit("请设置 api_key_env 或 NVIDIA_API_KEY 等")


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


def _usage(data: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    u = data.get("usage") or {}
    return (
        u.get("prompt_tokens"),
        u.get("completion_tokens"),
        u.get("total_tokens"),
    )


def _content(data: Dict[str, Any]) -> str:
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


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
    sleep_s = float(cfg.get("sleep_seconds", 0.2))
    verify = bool(cfg.get("verify_code", True))
    seed = int(cfg.get("random_seed", 42))
    tasks_path = Path(cfg.get("tasks_file", "tasks.json"))
    if not tasks_path.is_absolute():
        tasks_path = root / tasks_path
    out_path = Path(cfg.get("out_jsonl", "exp2_results.jsonl"))
    if not out_path.is_absolute():
        out_path = root / out_path

    tasks: List[Dict[str, Any]] = json.loads(tasks_path.read_text(encoding="utf-8"))
    key = _api_key(cfg)

    random.seed(seed)
    order_plan: List[Tuple[str, str]] = []
    for t in tasks:
        tid = t["id"]
        if random.random() < 0.5:
            order_plan.append((tid, "scratch_then_skill"))
        else:
            order_plan.append((tid, "skill_then_scratch"))

    rows: List[Dict[str, Any]] = []
    total_calls = len(tasks) * 2
    bar = (
        tqdm(total=total_calls, desc="exp2", unit="req", file=sys.stderr)
        if tqdm
        else None
    )

    for t, plan in zip(tasks, order_plan):
        tid = t["id"]
        conds = (
            ("scratch", user_scratch(t), "skill", user_skill(t))
            if plan[1] == "scratch_then_skill"
            else ("skill", user_skill(t), "scratch", user_scratch(t))
        )
        for i in (0, 2):
            label = conds[i]
            user = conds[i + 1]
            try:
                data = _post(base, key, model, SYSTEM, user, temp, timeout)
            except urllib.error.HTTPError as e:
                err = e.read().decode("utf-8", errors="replace")
                raise SystemExit(f"HTTP {e.code} {tid} {label}: {err}") from e
            raw = _content(data)
            pt, ct, tt = _usage(data)
            rec: Dict[str, Any] = {
                "task_id": tid,
                "condition": label,
                "order_plan": plan[1],
                "skill_version": SKILL_VERSION,
                "model": model,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": tt,
                "raw": raw,
            }
            if verify:
                ok, reason = grade_mode_b(t, raw)
                rec["reach_goal"] = ok
                rec["grade_reason"] = reason
            rows.append(rec)
            if bar:
                bar.update(1)
            time.sleep(sleep_s)

    if bar:
        bar.close()

    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("已写入", out_path, "共", len(rows), "条。汇总: python summarize_exp2.py --input", out_path.name)


if __name__ == "__main__":
    main()
