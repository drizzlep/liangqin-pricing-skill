#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BATCH_DIR="${1:-}"
RUNTIME_ROOT="${2:-${LIANGQIN_CONTRACT_AUDIT_RUNTIME_ROOT:-/tmp/liangqin-contract-pricing}}"

if [[ -z "${BATCH_DIR}" ]]; then
  echo "用法：bash scripts/run_contract_pricing_audit.sh /path/to/batch-dir [runtime-root]" >&2
  exit 1
fi

if [[ ! -d "${BATCH_DIR}" ]]; then
  echo "[ERROR] 批次目录不存在：${BATCH_DIR}" >&2
  exit 1
fi

bash "${SCRIPT_DIR}/check_dependencies.sh"

APP_DIR="${LIANGQIN_CONTRACT_AUDIT_APP_DIR:-${REPO_ROOT}/apps/contract-review}"
OCR_BACKEND="${LIANGQIN_CONTRACT_AUDIT_OCR_BACKEND:-paddleocr}"
PADDLEOCR_LANG="${LIANGQIN_CONTRACT_AUDIT_PADDLEOCR_LANG:-ch}"
PADDLEOCR_DEVICE="${LIANGQIN_CONTRACT_AUDIT_PADDLEOCR_DEVICE:-cpu}"
OUTPUT_MODE="${LIANGQIN_CONTRACT_AUDIT_OUTPUT_MODE:-json}"

CMD=(
  python3
  "${APP_DIR}/cli/manual_batch.py"
  --batch-dir "${BATCH_DIR}"
  --runtime-root "${RUNTIME_ROOT}"
  --output-mode "${OUTPUT_MODE}"
  --ocr-backend "${OCR_BACKEND}"
  --paddleocr-lang "${PADDLEOCR_LANG}"
  --paddleocr-device "${PADDLEOCR_DEVICE}"
)

if [[ "${LIANGQIN_CONTRACT_AUDIT_FORCE_OCR_FOR_DOCUMENTS:-0}" == "1" ]]; then
  CMD+=(--force-ocr-for-documents)
fi

echo "[INFO] BATCH_DIR=${BATCH_DIR}"
echo "[INFO] RUNTIME_ROOT=${RUNTIME_ROOT}"
echo "[INFO] APP_DIR=${APP_DIR}"

"${CMD[@]}"
