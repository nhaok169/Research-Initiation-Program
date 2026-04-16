#!/usr/bin/env bash
# 实验 1 + 2 + 3 一键夜间批跑（等同于 run_overnight_123.sh）。
#
# 用法:
#   export NVIDIA_API_KEY=...
#   ./scripts/run_exp1_2_3.sh
#   ./scripts/run_exp1_2_3.sh --foreground
#
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/run_overnight_123.sh" "$@"
