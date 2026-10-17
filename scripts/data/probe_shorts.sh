#!/usr/bin/env bash
# One-off: checks which official short-position registers can be downloaded from GitHub Actions.
mkdir -p data/probe
UA="Mozilla/5.0 (compatible; FINILA-data/1.0; +https://www.finila.com)"
probe() { # name url
  f="data/probe/$1"
  code=$(curl -sS -L -A "$UA" --max-time 60 -o "$f" -w '%{http_code} %{content_type} %{size_download}' "$2" 2>&1)
  echo "$1 | $code | $2" | tee -a data/probe/report.txt
  file "$f" >> data/probe/report.txt
  head -c 600 "$f" | strings | head -8 >> data/probe/report.txt; echo >> data/probe/report.txt
}
: > data/probe/report.txt
probe nl.csv 'https://www.afm.nl/export.aspx?type=8a46a4ef-f196-4467-a7ab-1ae1cb58f0e7&format=csv'
probe it.xlsx 'https://www.consob.it/documents/11973/395154/PncPubbl.xlsx/fbefe0a2-795b-bad3-9369-beccbeb14f27'
probe uk.xlsx 'https://www.fca.org.uk/publication/data/short-positions-daily-update.xlsx'
probe se-current.xlsx 'https://www.fi.se/en/our-registers/net-short-positions/GetAktuellFile/'
probe se-hist.xlsx 'https://www.fi.se/en/our-registers/net-short-positions/GetHistFile/'
probe se-page.html 'https://www.fi.se/en/our-registers/net-short-positions/'
probe de.csv 'https://www.bundesanzeiger.de/pub/en/nlp?0--top~csv~form~panel-form-csv~resource~link'
probe de-page.html 'https://www.bundesanzeiger.de/pub/en/nlp'
probe no.json 'https://ssr.finanstilsynet.no/api/v2/instruments'
probe es-page.html 'https://www.cnmv.es/Portal/Consultas/EE/PosicionesCortas.aspx?lang=en'
probe fr-page.html 'https://www.amf-france.org/en/professionals/issuers-and-financial-disclosure/short-selling/net-short-positions'
probe fr-gouv.json 'https://www.data.gouv.fr/api/1/datasets/?q=positions+courtes+nettes&page_size=5'
probe dk-page.html 'https://www.dfsa.dk/financial-themes/capital-market/short-selling/published-net-short-positions'
probe fi-page.html 'https://www.finanssivalvonta.fi/en/capital-markets/issuers-and-investors/short-selling/'
