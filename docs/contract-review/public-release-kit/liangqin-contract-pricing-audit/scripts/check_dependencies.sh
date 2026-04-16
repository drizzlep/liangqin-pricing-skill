#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR_DEFAULT="${REPO_ROOT}/apps/contract-review"
APP_DIR="${LIANGQIN_CONTRACT_AUDIT_APP_DIR:-$APP_DIR_DEFAULT}"

DEFAULT_PRICING_DIR_CANDIDATES=(
  "${LIANGQIN_PRICING_SKILL_DIR:-}"
  "${REPO_ROOT}/../liangqin-pricing"
  "${REPO_ROOT}/skill/liangqin-pricing"
  "${HOME}/.openclaw/workspace/skills/liangqin-pricing"
  "${HOME}/.openclaw/skills/liangqin-pricing"
)

err() {
  echo "[ERROR] $*" >&2
}

info() {
  echo "[INFO] $*"
}

resolve_pricing_dir() {
  local candidate=""
  for candidate in "${DEFAULT_PRICING_DIR_CANDIDATES[@]}"; do
    if [[ -n "${candidate}" && -d "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

info "检查 python3"
if ! command -v python3 >/dev/null 2>&1; then
  err "未找到 python3"
  exit 1
fi

info "检查审核 app 目录"
if [[ ! -d "${APP_DIR}" ]]; then
  err "未找到合同审核 app 目录：${APP_DIR}"
  err "如为模板仓库，请在接入最终 app 后再执行此检查。"
  exit 1
fi

if [[ ! -f "${APP_DIR}/cli/manual_batch.py" ]]; then
  err "缺少入口脚本：${APP_DIR}/cli/manual_batch.py"
  exit 1
fi

info "检查 liangqin-pricing 依赖"
if ! PRICING_DIR="$(resolve_pricing_dir)"; then
  err "未找到 liangqin-pricing"
  err "请设置 LIANGQIN_PRICING_SKILL_DIR=/path/to/liangqin-pricing"
  exit 1
fi

for file in \
  "${PRICING_DIR}/scripts/precheck_quote.py" \
  "${PRICING_DIR}/scripts/query_price_index.py" \
  "${PRICING_DIR}/data/current/price-index.json"
do
  if [[ ! -f "${file}" ]]; then
    err "缺少关键依赖文件：${file}"
    exit 1
  fi
done

info "检查 PaddleOCR 可导入性"
python3 - <<'PY'
import importlib.util
for mod in ("paddleocr", "paddle"):
    if importlib.util.find_spec(mod) is None:
        raise SystemExit(f"missing:{mod}")
print("ok")
PY

info "依赖检查通过"
info "APP_DIR=${APP_DIR}"
info "LIANGQIN_PRICING_SKILL_DIR=${PRICING_DIR}"
