#!/bin/sh
# sequential driver: run tag/variant over all issues
cd "$(dirname "$0")/.."
for tag in run1 run2; do
  for variant in official_circle cli_default; do
    for issue in us6000tjl2@3d us6000tkt2@7d us6000u18k@1d us6000t7zp@3d us6000qw60@1d; do
      python3 -I scripts/run_legacy.py "$issue" "$variant" "$tag" || echo "FAILED $issue $variant $tag"
    done
  done
done
echo ALLDONE
