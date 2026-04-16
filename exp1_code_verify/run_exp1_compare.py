"""实验一：开环多采样 vs 闭环多轮修正（预算均为最多 3 次 Chat 调用）。

开环：同一任务独立 3 次对话，任意一次执行到达终点则成功。
闭环：同一对话内根据 execute 错误反馈最多修正 3 轮。

用法（在 exp1_code_verify 目录）:
  export NVIDIA_API_KEY=...
  python run_exp1_compare.py --config config.json

配置见 config.example.json。
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
from typing import Any, Dict, List, Set

from evaluator import load_tasks
from execution import execute
from prompts import SYSTEM_CODE, build_feedback_prompt, build_open_loop_prompt

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
    raise SystemExit("请设置 api_key_env 或 NVIDIA_API_KEY / DASHSCOPE_API_KEY / OPENAI_API_KEY")


def _assistant_text(data: Dict[str, Any]) -> str:
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"无法解析响应: {json.dumps(data, ensure_ascii=False)[:800]}") from e


def _is_retryable_http(code: int) -> bool:
    return code in {429, 500, 502, 503, 504}


def _post_chat_messages(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float,
    timeout_sec: float,
    max_retries: int,
    retry_backoff_sec: float,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
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
    last_err = ""
    for attempt in range(1, max_retries + 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return _assistant_text(body)
        except TimeoutError as e:
            last_err = f"超时（>{timeout_sec:.0f}s）: {e}"
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            last_err = f"HTTP {e.code}: {err}"
            if attempt <= max_retries and _is_retryable_http(e.code):
                time.sleep(retry_backoff_sec * attempt)
                continue
            raise SystemExit(last_err) from e
        except urllib.error.URLError as e:
            last_err = f"URLError: {e}"
        except OSError as e:
            last_err = f"{type(e).__name__}: {e}"
        if attempt <= max_retries:
            time.sleep(retry_backoff_sec * attempt)
            continue
        raise SystemExit(last_err)
    raise SystemExit(last_err or "请求失败")


def _run_open_loop(
    task: Dict[str, Any],
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_sec: float,
    max_retries: int,
    retry_backoff_sec: float,
    max_calls: int,
) -> Dict[str, Any]:
    trials: List[Dict[str, Any]] = []
    calls_used = 0
    success = False
    for call_idx in range(1, max_calls + 1):
        user = build_open_loop_prompt(task)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_CODE},
            {"role": "user", "content": user},
        ]
        raw = _post_chat_messages(
            base_url,
            api_key,
            model,
            messages,
            temperature,
            timeout_sec,
            max_retries,
            retry_backoff_sec,
        )
        calls_used = call_idx
        ex = execute(task, raw)
        trials.append(
            {
                "call_idx": call_idx,
                "raw": raw,
                "at_goal": ex.at_goal,
                "error": ex.error,
                "code_extracted": ex.code,
            }
        )
        if ex.at_goal:
            success = True
            break
    return {
        "arm": "open_loop",
        "success": success,
        "calls_used": calls_used,
        "max_calls": max_calls,
        "trials": trials,
    }


def _run_closed_loop(
    task: Dict[str, Any],
    base_url: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_sec: float,
    max_retries: int,
    retry_backoff_sec: float,
    max_rounds: int,
) -> Dict[str, Any]:
    rounds_out: List[Dict[str, Any]] = []
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_CODE},
        {"role": "user", "content": build_open_loop_prompt(task)},
    ]
    calls_used = 0
    success = False
    first_round_success = False
    for rnd in range(1, max_rounds + 1):
        raw = _post_chat_messages(
            base_url,
            api_key,
            model,
            messages,
            temperature,
            timeout_sec,
            max_retries,
            retry_backoff_sec,
        )
        calls_used = rnd
        messages.append({"role": "assistant", "content": raw})
        ex = execute(task, raw)
        rounds_out.append(
            {
                "round": rnd,
                "raw": raw,
                "at_goal": ex.at_goal,
                "error": ex.error,
                "code_extracted": ex.code,
            }
        )
        if ex.at_goal:
            success = True
            if rnd == 1:
                first_round_success = True
            break
        if rnd >= max_rounds:
            break
        fb = build_feedback_prompt(task, ex.code, ex.error or "未知错误")
        messages.append({"role": "user", "content": fb})
    return {
        "arm": "closed_loop",
        "success": success,
        "calls_used": calls_used,
        "max_rounds": max_rounds,
        "first_round_success": first_round_success,
        "rounds": rounds_out,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config.json"))
    ap.add_argument(
        "--tasks",
        type=Path,
        default=None,
        help="覆盖 config 中的 tasks_file",
    )
    ap.add_argument("--dry-run", action="store_true", help="不请求 API，只打印任务数")
    ap.add_argument("--fresh", action="store_true", help="忽略已有输出文件，重写")
    ap.add_argument("--max-tasks", type=int, default=0, help="只跑前 N 题（调试用，0 表示全量）")
    ap.add_argument(
        "--no-progress",
        action="store_true",
        help="关闭 tqdm（日志重定向时可用）",
    )
    args = ap.parse_args()

    cfg_path = args.config.resolve()
    if not cfg_path.is_file():
        raise SystemExit(f"缺少配置: {cfg_path}")

    cfg = _load_cfg(cfg_path)
    base_url = str(cfg.get("base_url", "")).strip()
    model = str(cfg.get("model", "")).strip()
    temperature = float(cfg.get("temperature", 0.0))
    sleep_s = float(cfg.get("sleep_seconds", 0.25))
    timeout_sec = float(cfg.get("request_timeout_seconds", 600))
    max_retries = int(cfg.get("max_retries", 8))
    retry_backoff_sec = float(cfg.get("retry_backoff_seconds", 10.0))
    max_budget = int(cfg.get("max_calls_per_task", 3))
    tasks_path = args.tasks or Path(str(cfg.get("tasks_file", "tasks.json")))
    if not tasks_path.is_absolute():
        tasks_path = (cfg_path.parent / tasks_path).resolve()
    out_path = Path(str(cfg.get("out_jsonl", "exp1_compare_results.jsonl")))
    if not out_path.is_absolute():
        out_path = (cfg_path.parent / out_path).resolve()

    if not base_url or not model:
        raise SystemExit("config 需包含 base_url 与 model")

    tasks = load_tasks(tasks_path)
    if args.max_tasks > 0:
        tasks = tasks[: args.max_tasks]

    if args.dry_run:
        print(f"dry-run: {len(tasks)} tasks, budget={max_budget}", file=sys.stderr)
        return

    api_key = _api_key(cfg)
    done_ids: Set[str] = set()
    if out_path.exists() and not args.fresh:
        with out_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    tid = str(rec.get("task_id", ""))
                    if tid:
                        done_ids.add(tid)
                except json.JSONDecodeError:
                    continue

    pbar = None
    if tqdm is not None and not args.no_progress:
        pbar = tqdm(total=len(tasks) * 2, desc="exp1 compare", unit="arm", file=sys.stderr)

    for task in tasks:
        tid = str(task["id"])
        if tid in done_ids:
            if pbar:
                pbar.update(2)
            continue

        open_res = _run_open_loop(
            task,
            base_url,
            api_key,
            model,
            temperature,
            timeout_sec,
            max_retries,
            retry_backoff_sec,
            max_budget,
        )
        time.sleep(sleep_s)
        closed_res = _run_closed_loop(
            task,
            base_url,
            api_key,
            model,
            temperature,
            timeout_sec,
            max_retries,
            retry_backoff_sec,
            max_budget,
        )
        time.sleep(sleep_s)

        record = {
            "task_id": tid,
            "open_loop": open_res,
            "closed_loop": closed_res,
        }
        with out_path.open("a", encoding="utf-8") as fa:
            fa.write(json.dumps(record, ensure_ascii=False) + "\n")
        done_ids.add(tid)

        if pbar:
            pbar.update(2)

    if pbar:
        pbar.close()

    print("已写入", out_path, "共", len(done_ids), "条任务记录（每行含 open+closed）", file=sys.stderr)
    print("汇总: python summarize_exp1.py --input", out_path.name, file=sys.stderr)


if __name__ == "__main__":
    main()
