#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_PRICING_SOURCE_DIR="$PROJECT_DIR/skill/liangqin-pricing"
REPO_PUBLISH_SCRIPT="$PROJECT_DIR/scripts/publish_openclaw_skills.py"

if [[ -n "${PRICING_SOURCE_DIR:-}" ]]; then
  PRICING_SOURCE_DIR="$PRICING_SOURCE_DIR"
elif [[ -n "${SOURCE_DIR:-}" ]]; then
  PRICING_SOURCE_DIR="$SOURCE_DIR"
elif [[ -d "$REPO_PRICING_SOURCE_DIR" ]]; then
  PRICING_SOURCE_DIR="$REPO_PRICING_SOURCE_DIR"
else
  PRICING_SOURCE_DIR="$HOME/.openclaw/skills/liangqin-pricing"
fi

if [[ -n "${PUBLISH_OPENCLAW_SKILLS_SCRIPT:-}" ]]; then
  PUBLISH_OPENCLAW_SKILLS_SCRIPT="$PUBLISH_OPENCLAW_SKILLS_SCRIPT"
else
  PUBLISH_OPENCLAW_SKILLS_SCRIPT="$REPO_PUBLISH_SCRIPT"
fi

OUTPUT_DIR="${1:-$PROJECT_DIR/dist}"
PACKAGE_DATE="$(date +%Y%m%d)"
PACKAGE_NAME="liangqin-pricing-openclaw-${PACKAGE_DATE}.zip"

if [[ ! -d "$PRICING_SOURCE_DIR" ]]; then
  echo "未找到报价 skill 目录：$PRICING_SOURCE_DIR" >&2
  exit 1
fi

if [[ ! -f "$PUBLISH_OPENCLAW_SKILLS_SCRIPT" ]]; then
  echo "未找到统一发布脚本：$PUBLISH_OPENCLAW_SKILLS_SCRIPT" >&2
  exit 1
fi

for required_file in \
  "$PRICING_SOURCE_DIR/SKILL.md" \
  "$PRICING_SOURCE_DIR/README.md" \
  "$PRICING_SOURCE_DIR/data/current/price-index.json" \
  "$PRICING_SOURCE_DIR/data/current/release.json" \
  "$PRICING_SOURCE_DIR/scripts/publish_skill.py" \
  "$PRICING_SOURCE_DIR/scripts/refresh_and_test.py"; do
  if [[ ! -f "$required_file" ]]; then
    echo "缺少必要文件：$required_file" >&2
    exit 1
  fi
done

STAGING_ROOT="$(mktemp -d)"
trap 'rm -rf "$STAGING_ROOT"' EXIT
mkdir -p "$OUTPUT_DIR"

PRICING_PACKAGE_ROOT="$STAGING_ROOT/liangqin-pricing"
PUBLISH_SCRIPTS_ROOT="$STAGING_ROOT/scripts"

mkdir -p "$PRICING_PACKAGE_ROOT" "$PUBLISH_SCRIPTS_ROOT"

cp "$PRICING_SOURCE_DIR/SKILL.md" "$PRICING_PACKAGE_ROOT/SKILL.md"
cp "$PRICING_SOURCE_DIR/README.md" "$PRICING_PACKAGE_ROOT/README.md"

mkdir -p "$PRICING_PACKAGE_ROOT/data"
cp -R "$PRICING_SOURCE_DIR/data/current" "$PRICING_PACKAGE_ROOT/data/current"
mkdir -p "$PRICING_PACKAGE_ROOT/data/versions"

mkdir -p "$PRICING_PACKAGE_ROOT/references"
cp -R "$PRICING_SOURCE_DIR/references/current" "$PRICING_PACKAGE_ROOT/references/current"
if [[ -d "$PRICING_SOURCE_DIR/references/addenda" ]]; then
  cp -R "$PRICING_SOURCE_DIR/references/addenda" "$PRICING_PACKAGE_ROOT/references/addenda"
  find "$PRICING_PACKAGE_ROOT/references/addenda" -type f \( -name ".DS_Store" -o -name "*.pyc" \) -delete
fi

mkdir -p "$PRICING_PACKAGE_ROOT/scripts"
cp -R "$PRICING_SOURCE_DIR/scripts/." "$PRICING_PACKAGE_ROOT/scripts/"
find "$PRICING_PACKAGE_ROOT/scripts" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$PRICING_PACKAGE_ROOT/scripts" -type f \( -name "*.pyc" -o -name ".DS_Store" \) -delete

mkdir -p "$PRICING_PACKAGE_ROOT/sources/inbox"
if [[ -f "$PRICING_SOURCE_DIR/sources/inbox/README.md" ]]; then
  cp "$PRICING_SOURCE_DIR/sources/inbox/README.md" "$PRICING_PACKAGE_ROOT/sources/inbox/README.md"
fi
mkdir -p "$PRICING_PACKAGE_ROOT/sources/archived"

mkdir -p "$PRICING_PACKAGE_ROOT/reports/validation"
mkdir -p "$PRICING_PACKAGE_ROOT/reports/diffs"
if [[ -d "$PRICING_SOURCE_DIR/reports/addenda" ]]; then
  cp -R "$PRICING_SOURCE_DIR/reports/addenda" "$PRICING_PACKAGE_ROOT/reports/addenda"
  find "$PRICING_PACKAGE_ROOT/reports/addenda" \
    -type d \
    \( -name "__pycache__" -o -name "block-images" -o -name "page-images" -o -name "p48-p49-detail-crops" -o -name "tmp-p49-zoom" -o -name "images" -o -name "ocr" \) \
    -prune \
    -exec rm -rf {} +
  find "$PRICING_PACKAGE_ROOT/reports/addenda" -type f \( -name ".DS_Store" -o -name "*.pyc" -o -name "*.pdf" -o -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" \) -delete
fi

cp "$PUBLISH_OPENCLAW_SKILLS_SCRIPT" "$PUBLISH_SCRIPTS_ROOT/publish_openclaw_skills.py"

ZIP_PATH="$OUTPUT_DIR/$PACKAGE_NAME"
rm -f "$ZIP_PATH"

python3 - <<'PY' "$STAGING_ROOT" "$ZIP_PATH"
import sys
import zipfile
from pathlib import Path

staging_root = Path(sys.argv[1])
zip_path = Path(sys.argv[2])

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(staging_root.rglob("*")):
        if path.is_dir():
            continue
        archive.write(path, path.relative_to(staging_root))
PY

echo "打包完成：$ZIP_PATH"
echo "可直接发给其他 OpenClaw 用户，内含 liangqin-pricing skill。"
