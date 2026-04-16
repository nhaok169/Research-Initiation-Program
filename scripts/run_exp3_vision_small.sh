#!/usr/bin/env bash
# 选择排队少的小 VLM 跑 exp3 vision 条件（默认 80 题）
# 用法:
#   export NVIDIA_API_KEY=...
#   ./scripts/run_exp3_vision_small.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E3="${ROOT}/exp3_chart_transfer"

if [[ -z "${NVIDIA_API_KEY:-}" ]]; then
  echo "请先设置 NVIDIA_API_KEY" >&2
  exit 1
fi

cd "${E3}"
python3 render_task_images.py --tasks tasks_overnight.json --out-dir task_images

# 候选从小到大，优先小模型（排队通常更少）
for MODEL in \
  "microsoft/phi-3.5-vision-instruct" \
  "meta/llama-3.2-11b-vision-instruct"; do
  echo "[vision] 尝试模型: ${MODEL}" >&2
  cat > config.vision.autogen.json <<EOF
{
  "base_url": "https://integrate.api.nvidia.com/v1",
  "model": "${MODEL}",
  "api_key_env": "NVIDIA_API_KEY",
  "tasks_file": "tasks_overnight.json",
  "image_dir": "task_images",
  "out_jsonl": "exp3_vision_outputs.jsonl",
  "temperature": 0.0,
  "sleep_seconds": 0.3,
  "request_timeout_seconds": 600,
  "max_tasks": 80
}
EOF
  if python3 run_exp3_vision.py --config config.vision.autogen.json; then
    echo "[vision] 跑完: ${MODEL}" >&2
    exit 0
  fi
done

echo "[vision] 两个模型均失败，请检查账号可用模型或网络。" >&2
exit 2

