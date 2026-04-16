#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_ROOT="$APP_DIR/runtime"
OCR_BACKEND="paddleocr"
BATCH_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --batch-dir)
      BATCH_DIR="$2"
      shift 2
      ;;
    --ocr-backend)
      OCR_BACKEND="$2"
      shift 2
      ;;
    --runtime-root)
      RUNTIME_ROOT="$2"
      shift 2
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$BATCH_DIR" ]]; then
  echo "用法: bash apps/contract-review/scripts/run_acceptance_batch.sh --batch-dir /absolute/path/to/batch [--ocr-backend disabled|paddleocr] [--runtime-root /path]" >&2
  exit 1
fi

python3 "$APP_DIR/cli/manual_batch.py" \
  --batch-dir "$BATCH_DIR" \
  --runtime-root "$RUNTIME_ROOT" \
  --ocr-backend "$OCR_BACKEND"

GROUND_TRUTH_PATH="$(cd "$(dirname "$BATCH_DIR")" && pwd)/acceptance-ground-truth.csv"
if [[ -f "$GROUND_TRUTH_PATH" ]]; then
  python3 "$APP_DIR/cli/acceptance_report.py" \
    --batch-dir "$BATCH_DIR" \
    --runtime-root "$RUNTIME_ROOT" \
    --ground-truth-path "$GROUND_TRUTH_PATH"
else
  echo "未发现验收标注文件，已跳过验收评分：$GROUND_TRUTH_PATH"
fi

echo
echo "验收批次已运行完成。建议优先查看："
echo "- $RUNTIME_ROOT/batches/$(basename "$BATCH_DIR")/batch-dashboard.md"
echo "- $RUNTIME_ROOT/batches/$(basename "$BATCH_DIR")/manual-review-queue.md"
echo "- $RUNTIME_ROOT/batches/$(basename "$BATCH_DIR")/pricing-compare-diagnosis.md"
if [[ -f "$GROUND_TRUTH_PATH" ]]; then
  echo "- $RUNTIME_ROOT/batches/$(basename "$BATCH_DIR")/acceptance-report.md"
fi
