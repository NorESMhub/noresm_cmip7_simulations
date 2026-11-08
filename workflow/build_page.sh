#!/bin/sh
# Build the CMIP7 Cost Plan and Schedule Tracker page with the published plan.
#
#   workflow/build_page.sh [out.html] [extra build_scheduler.py options]
#
# The page goes to out.html, by default noresm3_cmip7_scheduler.html in the
# current directory. On NIRD, write it straight to the published page:
#
#   workflow/build_page.sh /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/index.html
#
# Extra options are passed on, e.g. --progress progress.json to build a copy of
# the progress into a page viewed as a local file.
set -e
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-noresm3_cmip7_scheduler.html}
[ $# -gt 0 ] && shift

python3 -I "$here/build_scheduler.py" \
    --experiments "$here/noresm3_experiments_decoded.csv" \
    --template "$here/scheduler_template.html" \
    --plan "LM:DECK,Fast Track" --plan "MM:DECK,ScenarioMIP" \
    --ensemble 3 \
    --members piControl=1 --members esm-piControl=1 \
    --members esm-flat10=1 --members esm-flat10-zec=1 --members esm-flat10-cdr=1 \
    --years piControl=600 --years esm-piControl=600 \
    --slots 9 \
    --out "$out" "$@"
