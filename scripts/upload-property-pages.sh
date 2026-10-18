#!/usr/bin/env bash
# Builds the property pages (/property/<country>, /property/overvalued) from the current data and
# uploads only those to the live site's property-pages/ folder. Never deletes anything.
# Needs FTP_SERVER, FTP_USERNAME, FTP_PASSWORD; optional FTP_DIR (default /).
set -euo pipefail
for v in FTP_SERVER FTP_USERNAME FTP_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "::error title=Missing setting::$v is not set"; exit 1; }
done
FTP_DIR="${FTP_DIR:-/}"
OUT=$(mktemp -d)
python3 scripts/build-property-pages.py . "$OUT"
err=$(mktemp)
lftp -u "$FTP_USERNAME","$FTP_PASSWORD" \
  -e "set net:max-retries 3; set net:timeout 30; set sftp:auto-confirm yes; cd '$FTP_DIR' && mirror -R --parallel=8 --no-perms '$OUT/property-pages' property-pages; bye" "$FTP_SERVER" 2>"$err" || {
  echo "::error title=Property pages upload failed::$(tail -n 5 "$err" | tr '\n' ' ' | sed "s/$FTP_PASSWORD/***/g")"; exit 1; }
echo "Uploaded $(ls "$OUT/property-pages" | wc -l) property pages."
