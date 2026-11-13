#!/bin/sh
# Build the CMIP7 Simulation Tracker Dashboard page. The plan is set in
# build_scheduler.py.
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

python3 -I "$here/build_scheduler.py" --out "$out" "$@"
