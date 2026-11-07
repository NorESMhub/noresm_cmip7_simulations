"""Write progress.json for the tracker from the GitHub issues and the files on NIRD.

Every case has an issue in NorESMhub/noresm_cmip7_simulations whose title is the
case name, such as
  nHistEsmGHGGaxg.LM.nor30b28.008.20261029
and whose labels include the CMIP7 experiment (esm-hist). The script lists the
issues, reads each case's directories on NIRD, and writes one entry per case;
the page groups the cases into its runs by experiment label and resolution.
An issue labelled "test" is left out, and "completed" marks a finished run.

For each case it records:
  - the latest model date in its file names, such as
    <case>.cam.i.1930-01-01-00000.nc; a monthly file such as
    <case>.cam.h0a.1929-12.nc counts as reaching the end of its month;
  - the sets of years cmip7-prep has run over. cmip7-prep writes
    completed_steps_<first>-<last>.json in its output directory for each set,
    listing the steps that finished (cmor-atm-mon, ...);
  - its cost (pe-hours per simulated year) and throughput (simulated years per
    day) on each machine it ran on, from the Machine, Model Cost and Model
    Throughput lines of its timing files, noresm_timing.<case>.<job id>.<date>,
    one per job; the mean over a machine's jobs weights each job by the years it
    simulated. The machine of its latest job is the one it runs on.

--dir gives each case's directory, --cmor-dir its cmip7-prep output directory
and --timing-dir its timing directory, with {case} standing for the case name:

  python3 -I workflow/nird_progress.py \\
      /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json \\
      --dir "/nird/datalake/NS9560K/noresm3/cases/{case}/atm/hist" \\
      --cmor-dir "/nird/datalake/NS9560K/noresm3/cases/{case}.cmor" \\
      --timing-dir "/nird/datalake/NS9560K/noresm3/cases/{case}/timing"

--pattern sets which files count (default *.cam.i.*.nc). --issues reads the
issues from a file saved from the GitHub API instead of fetching them.
"""

import argparse
import datetime
import fnmatch
import glob
import gzip
import json
import os
import re
import urllib.request

REPO = "NorESMhub/noresm_cmip7_simulations"
# compset.resolution.version...: n1850GHGGaxg.LM.nor30b28.011.20261102
TITLE = re.compile(r"^[A-Za-z0-9-]+\.(LM|MM)\.nor30(b\d+)\.")
RESOLUTION = {"LM": "ne16", "MM": "ne30"}
# YYYY-MM, YYYY-MM-DD or YYYY-MM-DD-SSSSS just before .nc
DATE = re.compile(r"\.(\d{4})-(\d{2})(?:-(\d{2})(?:-\d{5})?)?\.nc$")
# cmip7-prep's record of the steps that finished for one set of years.
COMPLETED = re.compile(r"completed_steps_(\d+)-(\d+)\.json$")
# Lines of a timing file, one per job: noresm_timing.<case>.<job id>.<date>.
TIMING_LINES = {
    "cost": re.compile(r"^\s*Model Cost:\s*([\d.]+)\s+pe-hrs/simulated_year", re.M),
    "sypd": re.compile(r"^\s*Model Throughput:\s*([\d.]+)\s+simulated_years/day", re.M),
    "days": re.compile(r"^\s*run length\s*:\s*([\d.]+)\s+days", re.M),
    "pes": re.compile(r"^\s*pe count for cost estimate\s*:\s*(\d+)", re.M),
    "machine": re.compile(r"^\s*Machine\s*:\s*(\S+)", re.M),
}


def fetch_issues(repo):
    """Every issue in the repository, open and closed, without pull requests."""
    issues, page = [], 1
    while True:
        url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "nird_progress"})
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.load(r)
        if not batch:
            return issues
        issues.extend(i for i in batch if "pull_request" not in i)
        page += 1


def latest_date(directory, pattern):
    """Latest (year, month, day) among the matching files; None if there are none,
    False if the directory doesn't exist. A monthly file (no day) is dated at the
    start of the next month."""
    if not os.path.isdir(directory):
        return False
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
    return max(dates) if dates else None


def cmor_sets(directory):
    """[{first, last, steps}] for each completed_steps_<first>-<last>.json, with its cmor- steps."""
    sets = []
    for path in glob.glob(os.path.join(glob.escape(directory), "completed_steps_*.json")):
        m = COMPLETED.search(os.path.basename(path))
        if not m:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                steps = sorted(k for k in json.load(f) if isinstance(k, str) and k.startswith("cmor-"))
        except (OSError, ValueError):
            continue
        sets.append({"first": int(m.group(1)), "last": int(m.group(2)), "steps": steps})
    return sorted(sets, key=lambda s: s["first"])


def read_timing_file(path):
    """{cost, sypd, days, pes, machine} from one timing file; None if it lacks cost or throughput."""
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    found = {k: m.group(1) for k, r in TIMING_LINES.items() if (m := r.search(text))}
    if "cost" not in found or "sypd" not in found or float(found["sypd"]) <= 0:
        return None
    t = {k: float(found[k]) for k in ("cost", "sypd", "days") if k in found}
    if "pes" in found:
        t["pes"] = int(found["pes"])
    if "machine" in found:
        t["machine"] = found["machine"]
    return t


def case_timing(directory):
    """The case's cost and throughput on each machine it ran on, averaged over all its
    timing files there with each job weighted by the years it simulated: cost in pe-hours
    per simulated year, throughput in simulated years per day. Returns ([{machine, jobs,
    years, cost, sypd, pes}], the machine of its latest job), or (None, None) if there are
    no readable timing files."""
    paths = glob.glob(os.path.join(glob.escape(directory), "noresm_timing.*"))
    jobs = [t for path in sorted(paths, key=os.path.getmtime) if (t := read_timing_file(path))]
    if not jobs:
        return None, None
    by_machine = {}
    for t in jobs:
        by_machine.setdefault(t.get("machine", "unknown").lower(), []).append(t)
    timing = []
    for machine, mjobs in sorted(by_machine.items()):
        years = [t.get("days", 365) / 365 for t in mjobs]
        total = sum(years)
        entry = {"machine": machine, "jobs": len(mjobs), "years": round(total, 2),
                 "cost": round(sum(t["cost"] * y for t, y in zip(mjobs, years)) / total, 2),
                 "sypd": round(total / sum(y / t["sypd"] for t, y in zip(mjobs, years)), 2)}
        if "pes" in mjobs[-1]:
            entry["pes"] = mjobs[-1]["pes"]
        timing.append(entry)
    return timing, jobs[-1].get("machine", "unknown").lower()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out", help="where to write progress.json")
    p.add_argument("--dir", required=True, help='each case\'s directory, e.g. "/archive/{case}/atm/hist"')
    p.add_argument("--cmor-dir", help='each case\'s cmip7-prep output directory, e.g. "/cases/{case}.cmor"')
    p.add_argument("--timing-dir", help='each case\'s timing directory, e.g. "/cases/{case}/timing"')
    p.add_argument("--pattern", default="*.cam.i.*.nc", help="dated files that count, as a shell pattern")
    p.add_argument("--repo", default=REPO, help="the repository with the case issues")
    p.add_argument("--issues", help="read the issues from this JSON file instead of GitHub")
    a = p.parse_args()

    if a.issues:
        with open(a.issues, encoding="utf-8") as f:
            issues = [i for i in json.load(f) if "pull_request" not in i]
    else:
        issues = fetch_issues(a.repo)

    cases, skipped = [], []
    for issue in sorted(issues, key=lambda i: i["number"]):
        num, title = issue["number"], issue["title"].strip()
        labels = [l["name"] for l in issue.get("labels", [])]
        if "test" in labels:
            continue
        m = TITLE.match(title)
        if not m:
            skipped.append({"issue": num, "title": title, "reason": "the title is not a case name"})
            print(f"#{num} {title}: skipped, the title is not a case name")
            continue
        people = [u["login"] for u in issue.get("assignees") or []] or [issue["user"]["login"]]
        case = {"issue": num, "case": title, "resolution": RESOLUTION[m.group(1)],
                "version": m.group(2), "owner": ", ".join(people), "labels": labels,
                "completed": "completed" in labels}
        last = latest_date(a.dir.format(case=title), a.pattern)
        if last:
            case["modelDate"] = "%04d-%02d-%02d" % last
            report = f"at {case['modelDate']}"
        else:
            report = "no directory" if last is False else "no dated files"
        if a.cmor_dir:
            sets = cmor_sets(a.cmor_dir.format(case=title))
            if sets:
                case["cmor"] = sets
                report += "; CMORized " + ", ".join(f"{s['first']}-{s['last']}" for s in sets)
        if a.timing_dir:
            timing, machine = case_timing(a.timing_dir.format(case=title))
            if timing:
                case["timing"], case["machine"] = timing, machine
                report += "".join(f"; {t['machine']} {t['cost']} pe-hrs/yr, {t['sypd']} SYPD over {t['jobs']} jobs"
                                  for t in timing)
        cases.append(case)
        print(f"#{num} {title} [{', '.join(labels) or 'no labels'}]: {report}")

    data = {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "cases": cases, "skipped": skipped}
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, a.out)
    print(f"{a.out}: {len(cases)} cases")


if __name__ == "__main__":
    main()
