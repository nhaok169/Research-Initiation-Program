"""从 prompt_dump 读取已生成的 SYSTEM / user 文本，调用 OpenAI 兼容 Chat Completions，写出 jsonl。

适用：阿里云百炼 compatible-mode、NVIDIA integrate.api.nvidia.com 等（只要兼容
POST {base_url}/chat/completions + Bearer）。

配置：复制 config.example.json 或 config.nvidia.example.json 为 config.json（不要写入 API Key）。
鉴权：在 config.json 设置 api_key_env 为环境变量名；若不设置，则依次尝试
DASHSCOPE_API_KEY、OPENAI_API_KEY、NVIDIA_API_KEY。

用法（PowerShell，在 exp1_code_verify 目录下）:
  $env:NVIDIA_API_KEY = 'nvapi-...'
  python bailian_batch_from_dump.py --config config.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore[misc, assignment]


def _load_config(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _log_line(msg: str, pbar: Any) -> None:
    """不打乱 tqdm：有进度条时用 tqdm.write。"""
    if pbar is not None and tqdm is not None:
        tqdm.write(msg, file=sys.stderr)
    else:
        print(msg, file=sys.stderr)


def _post_chat(
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
    timeout_sec: float,
    pbar: Any = None,
    tid: str = "",
    mode: str = "",
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
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    _log_line(
        f"[等待响应] {tid} mode={mode}（HTTP 阻塞中，大模型首包常需 1–5 分钟；超时 {timeout_sec:.0f}s）",
        pbar,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8")
    except TimeoutError as e:
        raise SystemExit(
            f"请求超时（>{timeout_sec:.0f}s）: {tid} mode={mode}。"
            "可在 config.json 增大 request_timeout_seconds，或换更小/更快模型。"
        ) from e
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            raise SystemExit(
                f"请求超时（>{timeout_sec:.0f}s）: {tid} mode={mode}。"
                "可在 config.json 增大 request_timeout_seconds。"
            ) from e
        raise
    except OSError as e:
        if "timed out" in str(e).lower():
            raise SystemExit(
                f"请求超时: {tid} mode={mode}。请增大 config.json 里的 request_timeout_seconds。"
            ) from e
        raise
    return json.loads(body)


def _is_retryable_http(code: int) -> bool:
    return code in {429, 500, 502, 503, 504}


def _assistant_text(data: Dict[str, Any]) -> str:
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"无法解析响应: {json.dumps(data, ensure_ascii=False)[:800]}") from e


def _discover_tasks(prompt_dir: Path) -> List[str]:
    """匹配任意前缀的 `*_mode_a_user.txt`（支持 t001、s001、c001 等大规模导出）。"""
    pat = re.compile(r"^(.+)_mode_a_user\.txt$")
    ids: List[str] = []
    for p in sorted(prompt_dir.glob("*_mode_a_user.txt")):
        m = pat.match(p.name)
        if m:
            ids.append(m.group(1))
    return ids


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _progress_text(done: int, total: int, tid: str, mode: str, bar_w: int = 22) -> str:
    if total <= 0:
        return "\r[----------] 0/0\r"
    frac = min(1.0, max(0.0, done / total))
    n = int(bar_w * frac)
    bar = "#" * n + "-" * (bar_w - n)
    pct = 100.0 * frac
    return f"\r[{bar}] {done}/{total} ({pct:5.1f}%)  {tid} mode={mode}  "


def _resolve_api_key(cfg: Dict[str, Any]) -> str:
    name = cfg.get("api_key_env")
    if isinstance(name, str) and name.strip():
        var = name.strip()
        val = os.environ.get(var, "").strip()
        if not val:
            raise SystemExit(
                f"config.json 指定了 api_key_env={var!r}，但该环境变量为空或未设置"
            )
        return val
    for var in ("DASHSCOPE_API_KEY", "OPENAI_API_KEY", "NVIDIA_API_KEY"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    raise SystemExit(
        "请设置环境变量：在 config.json 增加 \"api_key_env\": \"你的变量名\"，"
        "或设置 DASHSCOPE_API_KEY / OPENAI_API_KEY / NVIDIA_API_KEY 之一。不要把 Key 写进仓库。"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
        help="默认读取同目录 config.json；可先用 config.example.json 复制一份",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将请求的任务列表与条数，不联网",
    )
    ap.add_argument(
        "--no-progress",
        action="store_true",
        help="关闭进度条（重定向日志时可用）",
    )
    ap.add_argument(
        "--fresh",
        action="store_true",
        help="忽略已有 out_jsonl，从头重跑（默认启用断点续跑）",
    )
    args = ap.parse_args()

    cfg_path: Path = args.config
    if not cfg_path.is_file():
        raise SystemExit(
            f"找不到配置文件: {cfg_path}\n"
            f"请复制 config.example.json 为 config.json 后再运行。"
        )

    cfg = _load_config(cfg_path)
    base_url = str(cfg.get("base_url", "")).strip()
    model = str(cfg.get("model", "")).strip()
    temperature = float(cfg.get("temperature", 0.0))
    sleep_s = float(cfg.get("sleep_seconds", 0.25))
    request_timeout_sec = float(cfg.get("request_timeout_seconds", 600))
    max_retries = int(cfg.get("max_retries", 5))
    retry_backoff_sec = float(cfg.get("retry_backoff_seconds", 8.0))
    prompt_dir = Path(cfg.get("prompt_dir", "prompt_dump"))
    if not prompt_dir.is_absolute():
        prompt_dir = (cfg_path.parent / prompt_dir).resolve()
    system_file = str(cfg.get("system_file", "SYSTEM.txt"))
    out_name = str(cfg.get("out_jsonl", "model_outputs.jsonl"))
    out_path = Path(out_name)
    if not out_path.is_absolute():
        out_path = (cfg_path.parent / out_path).resolve()

    if not base_url or not model:
        raise SystemExit("config.json 中需填写 base_url 与 model")

    system_path = prompt_dir / system_file
    if not system_path.is_file():
        raise SystemExit(f"找不到 SYSTEM 文件: {system_path}")

    task_ids = _discover_tasks(prompt_dir)
    if not task_ids:
        raise SystemExit(f"在 {prompt_dir} 下未发现 *_mode_a_user.txt")

    pairs: List[Tuple[str, str]] = []
    for tid in task_ids:
        for mode in ("a", "b"):
            pairs.append((tid, mode))

    if args.dry_run:
        print("dry-run: 将请求", len(pairs), "次")
        for tid, mode in pairs:
            print(tid, mode)
        return

    api_key = _resolve_api_key(cfg)

    _log_line(
        f"[配置] 单次请求超时 {request_timeout_sec:.0f}s；大模型排队时进度条会在第 1 条停留较久，属正常。",
        None,
    )

    system_text = _read_text(system_path)
    rows: List[Dict[str, Any]] = []
    done_pairs: Set[Tuple[str, str]] = set()
    if out_path.exists() and not args.fresh:
        with out_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    tid = str(rec.get("task_id", ""))
                    mode = str(rec.get("mode", "")).lower()
                    if tid and mode in {"a", "b"}:
                        done_pairs.add((tid, mode))
                        rows.append(rec)
                except Exception:
                    continue
        _log_line(f"[断点续跑] 发现已完成 {len(done_pairs)} 条，将跳过。", None)
    elif args.fresh and out_path.exists():
        out_path.write_text("", encoding="utf-8")

    total_req = len(pairs)
    use_progress = not args.no_progress
    pbar = None
    if use_progress and tqdm is not None:
        pbar = tqdm(
            total=total_req,
            desc="API 请求",
            unit="次",
            dynamic_ncols=True,
            file=sys.stderr,
        )

    try:
        for idx, (tid, mode) in enumerate(pairs, start=1):
            if pbar is not None:
                pbar.set_postfix_str(f"{tid} {mode}", refresh=True)
            elif use_progress:
                sys.stderr.write(_progress_text(idx - 1, total_req, tid, mode))
                sys.stderr.flush()
            if (tid, mode) in done_pairs:
                if pbar is not None:
                    pbar.update(1)
                continue

            user_path = prompt_dir / f"{tid}_mode_{mode}_user.txt"
            if not user_path.is_file():
                raise SystemExit(f"缺少文件: {user_path}")
            user_text = _read_text(user_path)
            last_err = ""
            raw = ""
            ok = False
            for attempt in range(1, max_retries + 2):
                try:
                    data = _post_chat(
                        base_url,
                        api_key,
                        model,
                        system_text,
                        user_text,
                        temperature,
                        request_timeout_sec,
                        pbar=pbar,
                        tid=tid,
                        mode=mode,
                    )
                    raw = _assistant_text(data)
                    ok = True
                    break
                except urllib.error.HTTPError as e:
                    err = e.read().decode("utf-8", errors="replace")
                    last_err = f"HTTP {e.code} {tid} mode={mode}: {err}"
                    if e.code == 403 and "Unpurchased" in err:
                        raise SystemExit(
                            f"HTTP 403 {tid} mode={mode}: 当前账号未开通或未购买 config 里的 model。\n"
                            f"请到控制台开通模型，或把 config.json 的 model 改成账号已可用名称。\n详情: {err}"
                        ) from e
                    if attempt <= max_retries and _is_retryable_http(e.code):
                        wait_s = retry_backoff_sec * attempt
                        _log_line(
                            f"[重试 {attempt}/{max_retries}] {tid} mode={mode} {e.code}，{wait_s:.1f}s 后重试",
                            pbar,
                        )
                        time.sleep(wait_s)
                        continue
                    raise SystemExit(last_err) from e
                except (TimeoutError, urllib.error.URLError, OSError) as e:
                    last_err = f"请求异常 {tid} mode={mode}: {type(e).__name__}:{e}"
                    if attempt <= max_retries:
                        wait_s = retry_backoff_sec * attempt
                        _log_line(
                            f"[重试 {attempt}/{max_retries}] {last_err}，{wait_s:.1f}s 后重试",
                            pbar,
                        )
                        time.sleep(wait_s)
                        continue
                    raise SystemExit(last_err) from e
            if not ok:
                raise SystemExit(last_err or f"未知错误: {tid} mode={mode}")
            rec = {"task_id": tid, "mode": mode, "raw": raw}
            rows.append(rec)
            done_pairs.add((tid, mode))
            with out_path.open("a", encoding="utf-8") as fa:
                fa.write(json.dumps(rec, ensure_ascii=False) + "\n")

            if pbar is not None:
                pbar.update(1)
            elif use_progress:
                sys.stderr.write(_progress_text(idx, total_req, tid, mode))
                sys.stderr.flush()
            time.sleep(sleep_s)
    finally:
        if pbar is not None:
            pbar.close()
        elif use_progress:
            sys.stderr.write("\n")
            sys.stderr.flush()

    print("已写入", out_path, "共", len(done_pairs), "条")
    print("下一步: python grade_jsonl.py --input", out_path.name)


if __name__ == "__main__":
    main()
