#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_SOURCE_DIR="$PROJECT_DIR/skill/liangqin-pricing"

if [[ -n "${SOURCE_DIR:-}" ]]; then
  SOURCE_DIR="$SOURCE_DIR"
elif [[ -d "$REPO_SOURCE_DIR" ]]; then
  SOURCE_DIR="$REPO_SOURCE_DIR"
else
  SOURCE_DIR="$HOME/.openclaw/skills/liangqin-pricing"
fi

OUTPUT_DIR="${1:-$PROJECT_DIR/dist}"
PACKAGE_DATE="$(date +%Y%m%d)"
PACKAGE_NAME="liangqin-pricing-openclaw-${PACKAGE_DATE}.zip"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "未找到 skill 目录：$SOURCE_DIR" >&2
  exit 1
fi

for required_file in \
  "$SOURCE_DIR/SKILL.md" \
  "$SOURCE_DIR/README.md" \
  "$SOURCE_DIR/data/current/price-index.json" \
  "$SOURCE_DIR/data/current/release.json" \
  "$SOURCE_DIR/scripts/publish_skill.py" \
  "$SOURCE_DIR/scripts/refresh_and_test.py"; do
  if [[ ! -f "$required_file" ]]; then
    echo "缺少必要文件：$required_file" >&2
    exit 1
  fi
done

STAGING_ROOT="$(mktemp -d)"
trap 'rm -rf "$STAGING_ROOT"' EXIT

PACKAGE_ROOT="$STAGING_ROOT/liangqin-pricing"
mkdir -p "$PACKAGE_ROOT"
mkdir -p "$OUTPUT_DIR"

cp "$SOURCE_DIR/SKILL.md" "$PACKAGE_ROOT/SKILL.md"
cp "$SOURCE_DIR/README.md" "$PACKAGE_ROOT/README.md"

mkdir -p "$PACKAGE_ROOT/data"
cp -R "$SOURCE_DIR/data/current" "$PACKAGE_ROOT/data/current"
mkdir -p "$PACKAGE_ROOT/data/versions"

mkdir -p "$PACKAGE_ROOT/references"
cp -R "$SOURCE_DIR/references/current" "$PACKAGE_ROOT/references/current"

mkdir -p "$PACKAGE_ROOT/scripts"
cp -R "$SOURCE_DIR/scripts/." "$PACKAGE_ROOT/scripts/"
find "$PACKAGE_ROOT/scripts" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$PACKAGE_ROOT/scripts" -type f \( -name "*.pyc" -o -name ".DS_Store" \) -delete

mkdir -p "$PACKAGE_ROOT/sources/inbox"
if [[ -f "$SOURCE_DIR/sources/inbox/README.md" ]]; then
  cp "$SOURCE_DIR/sources/inbox/README.md" "$PACKAGE_ROOT/sources/inbox/README.md"
fi
mkdir -p "$PACKAGE_ROOT/sources/archived"

mkdir -p "$PACKAGE_ROOT/reports/validation"
mkdir -p "$PACKAGE_ROOT/reports/diffs"

ZIP_PATH="$OUTPUT_DIR/$PACKAGE_NAME"
rm -f "$ZIP_PATH"

if command -v zip >/dev/null 2>&1; then
  (
    cd "$STAGING_ROOT"
    zip -qr "$ZIP_PATH" liangqin-pricing
  )
elif command -v ditto >/dev/null 2>&1; then
  (
    cd "$STAGING_ROOT"
    ditto -c -k --sequesterRsrc --keepParent liangqin-pricing "$ZIP_PATH"
  )
else
  echo "系统缺少 zip 或 ditto，无法生成压缩包。" >&2
  exit 1
fi

echo "打包完成：$ZIP_PATH"
echo "可直接发给其他 OpenClaw 用户。"
