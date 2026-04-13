#!/usr/bin/env bash
# 顺序跑实验一、二、三（API 批跑），默认 nohup 后台。
#
# 默认按「≤7 小时 + NVIDIA 免费 NIM」调参：
#   - 端点: integrate.api.nvidia.com
#   - 模型: microsoft/phi-3.5-vision-instruct（官方 model 字符串为 3.5 带点，勿写成 phi-3_5）
#   - Key: 环境变量 NVIDIA_API_KEY（与 api_key_env 一致）
#   - 规模: 约 196 次 chat 请求（32+32+34 任务 × 各 2 次），按 ~90s/次粗算约 5h，留队列波动余量
#
# 跑前自检: python3 scripts/preflight_overnight.py
#
# 用法:
#   export NVIDIA_API_KEY=...
#   可选: OVERNIGHT_BASE_URL / OVERNIGHT_MODEL / OVERNIGHT_API_KEY_ENV
#   可选: EXP1_COUNT EXP2_COUNT EXP3_COUNT OVERNIGHT_SEED
#   可选: OVERNIGHT_SLEEP_SECONDS OVERNIGHT_REQUEST_TIMEOUT
#   纯云端推理、不想看本机 GPU: SKIP_GPU_CHECK=1
#   本机 GPU 检查放宽: GPU_MIN_FREE_MIB=0 GPU_MAX_UTIL_PCT=100
#
#   ./scripts/run_overnight_123.sh              # 后台
#   ./scripts/run_overnight_123.sh --foreground # 前台
#
# 更快纯文本备用模型: OVERNIGHT_MODEL=meta/llama-3.2-3b-instruct

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
E1="${EXP_ROOT}/exp1_code_verify"
E2="${EXP_ROOT}/exp2_skill_reuse"
E3="${EXP_ROOT}/exp3_chart_transfer"

OVERNIGHT_BASE_URL="${OVERNIGHT_BASE_URL:-https://integrate.api.nvidia.com/v1}"
OVERNIGHT_MODEL="${OVERNIGHT_MODEL:-microsoft/phi-3.5-vision-instruct}"
OVERNIGHT_API_KEY_ENV="${OVERNIGHT_API_KEY_ENV:-NVIDIA_API_KEY}"
OVERNIGHT_SLEEP_SECONDS="${OVERNIGHT_SLEEP_SECONDS:-0.35}"
OVERNIGHT_REQUEST_TIMEOUT="${OVERNIGHT_REQUEST_TIMEOUT:-780}"
EXP1_COUNT="${EXP1_COUNT:-32}"
EXP2_COUNT="${EXP2_COUNT:-32}"
EXP3_COUNT="${EXP3_COUNT:-34}"
SEED="${OVERNIGHT_SEED:-42}"
MIN_FREE_MIB="${GPU_MIN_FREE_MIB:-2048}"
MAX_UTIL="${GPU_MAX_UTIL_PCT:-95}"

export E1 E2 E3 EXP_ROOT
export OVERNIGHT_BASE_URL OVERNIGHT_MODEL OVERNIGHT_API_KEY_ENV
export OVERNIGHT_SLEEP_SECONDS OVERNIGHT_REQUEST_TIMEOUT
export EXP1_COUNT EXP2_COUNT EXP3_COUNT SEED

run_inner() {
  echo "[overnight] EXP_ROOT=${EXP_ROOT}" >&2

  if [[ "${SKIP_GPU_CHECK:-}" == "1" ]]; then
    echo "[overnight] 已跳过 GPU 检查（SKIP_GPU_CHECK=1）" >&2
  else
    python3 "${EXP_ROOT}/scripts/check_gpu_before_run.py" \
      --min-free-mib "${MIN_FREE_MIB}" \
      --max-util-pct "${MAX_UTIL}" || {
      echo "[overnight] GPU 检查未通过。纯云端 API 可设 SKIP_GPU_CHECK=1；或放宽 GPU_MIN_FREE_MIB / GPU_MAX_UTIL_PCT。" >&2
      exit 1
    }
  fi

  python3 "${EXP_ROOT}/scripts/generate_exp1_tasks.py" \
    --out "${E1}/tasks_overnight.json" \
    --count "${EXP1_COUNT}" \
    --seed "${SEED}"

  (cd "${E1}" && python3 validate_tasks.py --tasks tasks_overnight.json)
  (cd "${E1}" && python3 dump_prompts.py --tasks tasks_overnight.json --out prompt_dump_overnight)

  python3 "${EXP_ROOT}/scripts/generate_exp2_tasks.py" \
    --out "${E2}/tasks_overnight.json" \
    --count "${EXP2_COUNT}" \
    --seed "${SEED}"

  (cd "${E3}" && python3 generate_tasks.py --out tasks_overnight.json --count "${EXP3_COUNT}" --seed "${SEED}")

  python3 - <<'PY'
import json
import os
from pathlib import Path

e1 = Path(os.environ["E1"]).resolve()
e2 = Path(os.environ["E2"]).resolve()
e3 = Path(os.environ["E3"]).resolve()
base = os.environ["OVERNIGHT_BASE_URL"]
model = os.environ["OVERNIGHT_MODEL"]
key_env = os.environ["OVERNIGHT_API_KEY_ENV"]
seed = int(os.environ["SEED"])
sleep_seconds = float(os.environ.get("OVERNIGHT_SLEEP_SECONDS", "0.35"))
request_timeout = float(os.environ.get("OVERNIGHT_REQUEST_TIMEOUT", "780"))


def dump(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


dump(
    e1 / "config_overnight_autogen.json",
    {
        "base_url": base,
        "model": model,
        "api_key_env": key_env,
        "prompt_dir": str(e1 / "prompt_dump_overnight"),
        "out_jsonl": str(e1 / "model_outputs_overnight.jsonl"),
        "temperature": 0.0,
        "sleep_seconds": sleep_seconds,
        "request_timeout_seconds": request_timeout,
        "system_file": "SYSTEM.txt",
    },
)
dump(
    e2 / "config_overnight_autogen.json",
    {
        "base_url": base,
        "model": model,
        "api_key_env": key_env,
        "tasks_file": str(e2 / "tasks_overnight.json"),
        "out_jsonl": str(e2 / "exp2_results_overnight.jsonl"),
        "temperature": 0.0,
        "sleep_seconds": sleep_seconds,
        "request_timeout_seconds": request_timeout,
        "verify_code": True,
        "random_seed": seed,
    },
)
dump(
    e3 / "config_overnight_autogen.json",
    {
        "base_url": base,
        "model": model,
        "api_key_env": key_env,
        "tasks_file": str(e3 / "tasks_overnight.json"),
        "out_jsonl": str(e3 / "exp3_model_outputs_overnight.jsonl"),
        "temperature": 0.0,
        "sleep_seconds": sleep_seconds,
        "request_timeout_seconds": request_timeout,
    },
)
print("[overnight] wrote config_overnight_autogen.json ×3")
PY

  echo "[overnight] 开始实验一 API…" >&2
  (cd "${E1}" && python3 bailian_batch_from_dump.py --config config_overnight_autogen.json --no-progress)

  echo "[overnight] 实验一评分…" >&2
  (cd "${E1}" && python3 grade_jsonl.py --tasks tasks_overnight.json \
    --input model_outputs_overnight.jsonl --out graded_overnight.jsonl)

  echo "[overnight] 开始实验二 API…" >&2
  (cd "${E2}" && python3 run_exp2_tokens.py --config config_overnight_autogen.json)

  echo "[overnight] 实验二汇总…" >&2
  (cd "${E2}" && python3 summarize_exp2.py --input exp2_results_overnight.jsonl || true)

  echo "[overnight] 开始实验三 API…" >&2
  (cd "${E3}" && python3 run_exp3.py --config config_overnight_autogen.json)

  echo "[overnight] 实验三评分…" >&2
  (cd "${E3}" && python3 grade_jsonl.py --tasks tasks_overnight.json \
    --input exp3_model_outputs_overnight.jsonl --out exp3_graded_overnight.jsonl)

  echo "[overnight] 实验三按题型汇总…" >&2
  (cd "${E3}" && python3 summarize_exp3.py --tasks tasks_overnight.json --graded exp3_graded_overnight.jsonl || true)

  echo "[overnight] 全部完成。" >&2
  echo "[overnight] 产物: ${E1}/graded_overnight.jsonl , ${E2}/exp2_results_overnight.jsonl , ${E3}/exp3_graded_overnight.jsonl" >&2
}

if [[ "${1:-}" == "--foreground" ]]; then
  run_inner
  exit 0
fi

LOGDIR="${EXP_ROOT}/logs_overnight_$(date +%Y%m%d_%H%M%S)"
mkdir -p "${LOGDIR}"
LOGFILE="${LOGDIR}/run.log"
PIDFILE="${LOGDIR}/overnight.pid"

nohup env \
  E1="${E1}" E2="${E2}" E3="${E3}" EXP_ROOT="${EXP_ROOT}" \
  OVERNIGHT_BASE_URL="${OVERNIGHT_BASE_URL}" OVERNIGHT_MODEL="${OVERNIGHT_MODEL}" \
  OVERNIGHT_API_KEY_ENV="${OVERNIGHT_API_KEY_ENV}" \
  OVERNIGHT_SLEEP_SECONDS="${OVERNIGHT_SLEEP_SECONDS}" \
  OVERNIGHT_REQUEST_TIMEOUT="${OVERNIGHT_REQUEST_TIMEOUT}" \
  EXP1_COUNT="${EXP1_COUNT}" EXP2_COUNT="${EXP2_COUNT}" EXP3_COUNT="${EXP3_COUNT}" \
  SEED="${SEED}" \
  GPU_MIN_FREE_MIB="${MIN_FREE_MIB}" GPU_MAX_UTIL_PCT="${MAX_UTIL}" \
  SKIP_GPU_CHECK="${SKIP_GPU_CHECK:-}" \
  bash "${SCRIPT_DIR}/run_overnight_123.sh" --foreground >>"${LOGFILE}" 2>&1 &

echo $! >"${PIDFILE}"
echo "[overnight] 已后台启动 PID=$(cat "${PIDFILE}")，日志: ${LOGFILE}" >&2
echo "[overnight] 跟踪: tail -f ${LOGFILE}" >&2
