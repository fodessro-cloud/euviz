#!/usr/bin/env bash
# Builds the company pages (/stock/<name>), the A-Z list and sitemap.xml from the current data and
# uploads only those to the live site. Other pages are published only by deploy-finila.yml.
# Never deletes anything: a company that drops out keeps its old page.
# Needs FTP_SERVER, FTP_USERNAME, FTP_PASSWORD; optional FTP_DIR (default /).
set -euo pipefail
for v in FTP_SERVER FTP_USERNAME FTP_PASSWORD; do
  [ -n "${!v:-}" ] || { echo "::error title=Missing setting::$v is not set"; exit 1; }
done
FTP_DIR="${FTP_DIR:-/}"
OUT=$(mktemp -d)
python3 scripts/build-stock-pages.py . "$OUT"
cmds="cd '$FTP_DIR' && mirror -R --parallel=8 --no-perms '$OUT/stock' stock"
# SFTP cannot rename onto an existing file: upload to .tmp, then swap it in.
cmds="$cmds && put '$OUT/sitemap.xml' -o sitemap.xml.tmp && rm -f sitemap.xml && mv sitemap.xml.tmp sitemap.xml"
cmds="$cmds && cd js && put '$OUT/js/stock-slugs.json' -o stock-slugs.json.tmp && rm -f stock-slugs.json && mv stock-slugs.json.tmp stock-slugs.json"
err=$(mktemp)
lftp -u "$FTP_USERNAME","$FTP_PASSWORD" \
  -e "set net:max-retries 3; set net:timeout 30; set sftp:auto-confirm yes; $cmds; bye" "$FTP_SERVER" 2>"$err" || {
  echo "::error title=Company pages upload failed::$(tail -n 5 "$err" | tr '\n' ' ' | sed "s/$FTP_PASSWORD/***/g")"; exit 1; }
echo "Uploaded $(ls "$OUT/stock" | wc -l) company pages and sitemap.xml."
