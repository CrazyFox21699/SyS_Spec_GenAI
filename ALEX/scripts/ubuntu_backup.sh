#!/usr/bin/env bash
# Backup runtime trước khi redeploy ALEX trên Ubuntu công ty.
set -euo pipefail
cd "$(dirname "$0")/.."

STAMP=$(date +%Y%m%d-%H%M%S)
PARENT=$(dirname "$(pwd)")
OUT="${PARENT}/alex-backup-${STAMP}.tgz"

echo ""
echo "=== ALEX backup ==="
echo "Source: $(pwd)"
echo "Output: $OUT"
echo ""

ITEMS=(web_data .env config.yaml)
[ -f config/company-ca.pem ] && ITEMS+=(config/company-ca.pem)

tar czf "$OUT" "${ITEMS[@]}"

echo "OK — backup saved: $OUT"
echo ""
echo "Redeploy (full release, không copy lẻ file):"
echo "  1. Giải nén ZIP mới đè code HOẶC git checkout <tag>"
echo "  2. Khôi phục: cd $PARENT && tar xzf $(basename "$OUT")"
echo "  3. source .venv/bin/activate && pip install -r requirements.txt"
echo "  4. ./scripts/ubuntu_deploy_gates.sh"
echo "  5. ./chay.sh"
echo ""
echo "Chi tiết: docs/UBUNTU_UPDATE_POLICY.md"
echo ""
