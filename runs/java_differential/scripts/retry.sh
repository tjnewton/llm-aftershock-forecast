#!/bin/sh
# retry missing runs once ComCat stops returning 429; probe every 10 min, max 9 probes per run
cd "$(dirname "$0")/.."
probe() { curl -s -o /dev/null -w '%{http_code}' "https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=us6000qw60&format=geojson"; }
for spec in "us6000qw60@1d official_circle run1" "us6000qw60@1d official_circle run2" \
  "us6000tjl2@3d cli_default run2" "us6000tkt2@7d cli_default run2" "us6000u18k@1d cli_default run2" \
  "us6000t7zp@3d cli_default run2" "us6000qw60@1d cli_default run2"; do
  set -- $spec
  n=0
  until [ -f "out/$1/$2_$3/meta.json" ] || [ $n -ge 9 ]; do
    n=$((n+1))
    code=$(probe); echo "$(date -u +%H:%M:%S) probe $code for $spec"
    if [ "$code" = 200 ]; then
      sleep 20
      rm -rf "out/$1/$2_$3"
      python3 -I scripts/run_legacy.py "$1" "$2" "$3" 2>&1 | tail -1
      [ -f "out/$1/$2_$3/meta.json" ] || { rm -rf "out/$1/$2_$3"; sleep 600; }
    else
      sleep 600
    fi
  done
  sleep 60
done
echo RETRYDONE
