#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${DIST_DIR:-$PROJECT_DIR/dist}"
PACKAGE_DATE="$(date +%Y%m%d)"
ZIP_PATH="$DIST_DIR/liangqin-pricing-openclaw-${PACKAGE_DATE}.zip"
INSTALLER_PATH="$DIST_DIR/liangqin-pricing-installer-${PACKAGE_DATE}.sh"

mkdir -p "$DIST_DIR"

bash "$SCRIPT_DIR/package_openclaw_skill.sh" "$DIST_DIR"

PAYLOAD_B64="$(base64 < "$ZIP_PATH" | tr -d '\n')"

cat > "$INSTALLER_PATH" <<EOF
#!/bin/sh
set -eu

SKILLS_ROOT="\${SKILLS_ROOT:-\$HOME/.openclaw/skills}"
WORKSPACE_ROOT="\${WORKSPACE_ROOT:-\$HOME/.openclaw/workspace/skills}"
WORKSPACE_SKILL_DEST=""
RUN_TEST=1
TEST_MESSAGE=""

while [ \$# -gt 0 ]; do
  case "\$1" in
    --skills-root)
      SKILLS_ROOT="\$2"
      shift 2
      ;;
    --workspace-root)
      WORKSPACE_ROOT="\$2"
      shift 2
      ;;
    --workspace-dest)
      WORKSPACE_SKILL_DEST="\$2"
      shift 2
      ;;
    --skip-test)
      RUN_TEST=0
      shift 1
      ;;
    --message)
      TEST_MESSAGE="\$2"
      shift 2
      ;;
    *)
      echo "未知参数: \$1" >&2
      exit 1
      ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "需要 python3，但当前环境未找到。" >&2
  exit 1
fi

if [ -n "\$WORKSPACE_SKILL_DEST" ]; then
  WORKSPACE_ROOT="\$(dirname "\$WORKSPACE_SKILL_DEST")"
fi

TMP_DIR="\$(mktemp -d)"
cleanup() {
  rm -rf "\$TMP_DIR"
}
trap cleanup EXIT INT TERM

ZIP_FILE="\$TMP_DIR/liangqin-pricing.zip"
EXTRACT_DIR="\$TMP_DIR/extracted"

python3 - <<'PY' "\$ZIP_FILE"
import base64
import sys
from pathlib import Path

payload = """$PAYLOAD_B64"""
Path(sys.argv[1]).write_bytes(base64.b64decode(payload))
PY

python3 - <<'PY' "\$ZIP_FILE" "\$EXTRACT_DIR"
import sys
import zipfile
from pathlib import Path

zip_path = Path(sys.argv[1])
extract_dir = Path(sys.argv[2])
extract_dir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(zip_path) as zf:
    zf.extractall(extract_dir)
PY

PRICING_SOURCE="\$EXTRACT_DIR/liangqin-pricing"
CONTRACT_REVIEW_SOURCE="\$EXTRACT_DIR/liangqin-contract-review"
PUBLISH_SCRIPT_SOURCE="\$EXTRACT_DIR/scripts/publish_openclaw_skills.py"
PRICING_DEST="\$SKILLS_ROOT/liangqin-pricing"
CONTRACT_REVIEW_DEST="\$SKILLS_ROOT/liangqin-contract-review"
PUBLISH_SCRIPT_DEST="\$SKILLS_ROOT/scripts/publish_openclaw_skills.py"

mkdir -p "\$SKILLS_ROOT"
mkdir -p "\$SKILLS_ROOT/scripts"
rm -rf "\$PRICING_DEST" "\$CONTRACT_REVIEW_DEST"
cp -R "\$PRICING_SOURCE" "\$PRICING_DEST"
cp -R "\$CONTRACT_REVIEW_SOURCE" "\$CONTRACT_REVIEW_DEST"
cp "\$PUBLISH_SCRIPT_SOURCE" "\$PUBLISH_SCRIPT_DEST"

python3 "\$PUBLISH_SCRIPT_DEST" \\
  --source-root "\$SKILLS_ROOT" \\
  --skills-root "\$SKILLS_ROOT" \\
  --workspace-root "\$WORKSPACE_ROOT" \\
  --publish-engine "\$PRICING_DEST/scripts/publish_skill.py"

if [ "\$RUN_TEST" -eq 1 ]; then
  if [ -n "\$TEST_MESSAGE" ]; then
    python3 "\$PRICING_DEST/scripts/refresh_and_test.py" --message "\$TEST_MESSAGE"
  else
    python3 "\$PRICING_DEST/scripts/refresh_and_test.py"
  fi
fi

echo "安装完成：\$PRICING_DEST"
echo "安装完成：\$CONTRACT_REVIEW_DEST"
echo "已同步到：\$WORKSPACE_ROOT"
EOF

chmod +x "$INSTALLER_PATH"

echo "单文件安装器已生成：$INSTALLER_PATH"
