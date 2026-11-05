"""Write progress.json for the tracker from the dates in the runs' file names.

A run's files carry the model date they were written at, as in
  nHistEsmGHGGaxg.LM.nor30b28.008.20261029.cam.i.1930-01-01-00000.nc
so the latest date in its directories says how far the run has got. Years done
are that date minus the run's start year: a historical run starting in 1850
with a 1930-01-01 file has done 80 years. A monthly file such as
<case>.cam.h0a.1929-12.nc counts as reaching the end of its month.

The runs and their cases come from noresm3_cases.csv (run, case, first_year,
...), the file the page is built from. A run continued in a second case is
read across both; its start year is its first case's first_year.

--dir gives each case's directory, with {case} standing for the case name.
--nird-dir does the same for the copy on NIRD; the tracker ticks the NIRD step
once that copy has reached the end of the run. --completed names a finished run.

  python3 -I workflow/nird_progress.py workflow/noresm3_cases.csv \\
      /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json \\
      --dir "/path/to/archive/{case}/atm/hist"

--pattern sets which files count (default *.cam.i.*.nc).
"""

import argparse
import csv
import datetime
import fnmatch
import json
import os
import re

# YYYY-MM, YYYY-MM-DD or YYYY-MM-DD-SSSSS just before .nc
DATE = re.compile(r"\.(\d{4})-(\d{2})(?:-(\d{2})(?:-\d{5})?)?\.nc$")


def model_dates(directory, pattern):
    """(year, month, day) of every matching file; None if the directory doesn't exist.
    A monthly file (no day) is dated at the start of the next month."""
    if not os.path.isdir(directory):
        return None
    dates = []
    for name in os.listdir(directory):
        if not fnmatch.fnmatchcase(name, pattern):
            continue
        m = DATE.search(name)
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
        if d is None:
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
            d = 1
        dates.append((y, mo, int(d)))
    return dates


def as_years(date):
    y, mo, d = date
    return y + (mo - 1) / 12 + (d - 1) / 365


def latest(cases, template, pattern):
    """Latest date across a run's cases, and the case directories that are missing."""
    dates, missing = [], []
    for case in cases:
        found = model_dates(template.format(case=case), pattern)
        if found is None:
            missing.append(case)
        else:
            dates.extend(found)
    return (max(dates) if dates else None), missing


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cases", help="noresm3_cases.csv")
    p.add_argument("out", help="where to write progress.json")
    p.add_argument("--dir", required=True, help='each case\'s directory, e.g. "/archive/{case}/atm/hist"')
    p.add_argument("--nird-dir", help="each case's directory on NIRD, with {case}")
    p.add_argument("--pattern", default="*.cam.i.*.nc", help="dated files that count, as a shell pattern")
    p.add_argument("--completed", action="append", default=[], metavar="RUN",
                   help='a run that has finished, e.g. "piControl ne16"; repeatable')
    a = p.parse_args()

    runs = {}
    with open(a.cases, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            r = runs.setdefault(row["run"].strip(), {"cases": [], "start": None})
            r["cases"].append(row["case"].strip())
            first = int(row["first_year"])
            r["start"] = first if r["start"] is None else min(r["start"], first)

    out = {}
    for name, r in runs.items():
        entry = {}
        last, missing = latest(r["cases"], a.dir, a.pattern)
        if last:
            entry["yearsCompleted"] = round(max(0.0, as_years(last) - r["start"]), 2)
            entry["modelDate"] = "%04d-%02d-%02d" % last
            report = f"{entry['yearsCompleted']} years (at {entry['modelDate']})"
        else:
            report = "no dated files found"
        if missing:
            report += f"; no directory for {', '.join(missing)}"
        if a.nird_dir:
            nird, _ = latest(r["cases"], a.nird_dir, a.pattern)
            if nird:
                entry["nirdYears"] = round(max(0.0, as_years(nird) - r["start"]), 2)
                report += f", {entry['nirdYears']} on NIRD"
        if name in a.completed:
            entry["completed"] = True
        out[name] = entry
        print(f"{name}: {report}")

    data = {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "runs": out}
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, a.out)
    print(f"{a.out}: {len(out)} runs")


if __name__ == "__main__":
    main()
