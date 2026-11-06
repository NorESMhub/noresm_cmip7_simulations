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
  - its run script in the repository's scripts/ directory, named
    <issue>.<compset>.<resolution>.<beta>.<date>.sh and found by the issue
    number it starts with, and whether the issue's description names it.

--dir gives each case's directory and --cmor-dir its cmip7-prep output
directory, with {case} standing for the case name:

  python3 -I workflow/nird_progress.py \\
      /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json \\
      --dir "/nird/datalake/NS9560K/noresm3/cases/{case}/atm/hist" \\
      --cmor-dir "/nird/datalake/NS9560K/noresm3/cases/{case}.cmor"

--pattern sets which files count (default *.cam.i.*.nc). --issues and --scripts
read the issues and the listing of scripts/ from files saved from the GitHub API
instead of fetching them.
"""

import argparse
import datetime
import fnmatch
import glob
import json
import os
import re
import urllib.error
import urllib.request

REPO = "NorESMhub/noresm_cmip7_simulations"
# compset.resolution.version...: n1850GHGGaxg.LM.nor30b28.011.20261102
TITLE = re.compile(r"^[A-Za-z0-9-]+\.(LM|MM)\.nor30(b\d+)\.")
RESOLUTION = {"LM": "ne16", "MM": "ne30"}
# YYYY-MM, YYYY-MM-DD or YYYY-MM-DD-SSSSS just before .nc
DATE = re.compile(r"\.(\d{4})-(\d{2})(?:-(\d{2})(?:-\d{5})?)?\.nc$")
# cmip7-prep's record of the steps that finished for one set of years.
COMPLETED = re.compile(r"completed_steps_(\d+)-(\d+)\.json$")
# A run script: <issue>.<compset>.<resolution>.<beta>.<date>.sh, e.g. 009.n1850GhgGaxg.LM.b28.20261029.sh
SCRIPT = re.compile(r"^(\d+)\..+\.sh$")


def get_json(url):
    """The GitHub API's answer for url, read anonymously."""
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "nird_progress"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_issues(repo):
    """Every issue in the repository, open and closed, without pull requests."""
    issues, page = [], 1
    while True:
        batch = get_json(f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}")
        if not batch:
            return issues
        issues.extend(i for i in batch if "pull_request" not in i)
        page += 1


def fetch_scripts(repo):
    """The files in scripts/ on the repository's default branch; none if it has no scripts/."""
    try:
        return get_json(f"https://api.github.com/repos/{repo}/contents/scripts")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return []
        raise


def scripts_by_issue(listing):
    """{issue number: [script names]} for the run scripts in a listing of scripts/."""
    found = {}
    for entry in listing:
        name = entry["name"] if isinstance(entry, dict) else entry
        m = SCRIPT.match(name)
        if m:
            found.setdefault(int(m.group(1)), []).append(name)
    return found


def expected_script(num, title):
    """The run script name the convention gives a case: n1850GHGGaxg.LM.nor30b28.011.20261102
    becomes 011.n1850GHGGaxg.LM.b28.20261102.sh."""
    parts = title.split(".")
    return f"{num:03d}.{parts[0]}.{parts[1]}.{parts[2].replace('nor30', '')}.{parts[-1]}.sh"


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out", help="where to write progress.json")
    p.add_argument("--dir", required=True, help='each case\'s directory, e.g. "/archive/{case}/atm/hist"')
    p.add_argument("--cmor-dir", help='each case\'s cmip7-prep output directory, e.g. "/cases/{case}.cmor"')
    p.add_argument("--pattern", default="*.cam.i.*.nc", help="dated files that count, as a shell pattern")
    p.add_argument("--repo", default=REPO, help="the repository with the case issues")
    p.add_argument("--issues", help="read the issues from this JSON file instead of GitHub")
    p.add_argument("--scripts", help="read the listing of scripts/ from this JSON file instead of GitHub")
    a = p.parse_args()

    if a.issues:
        with open(a.issues, encoding="utf-8") as f:
            issues = [i for i in json.load(f) if "pull_request" not in i]
    else:
        issues = fetch_issues(a.repo)
    if a.scripts:
        with open(a.scripts, encoding="utf-8") as f:
            scripts = scripts_by_issue(json.load(f))
    else:
        scripts = scripts_by_issue(fetch_scripts(a.repo))

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
        names = scripts.get(num, [])
        case["script"] = names[0] if names else None
        case["scriptLinked"] = bool(names) and names[0] in (issue.get("body") or "")
        if not names:
            report += "; no run script in scripts/"
        else:
            report += f"; script {names[0]}"
            if len(names) > 1:
                report += f" (and {', '.join(names[1:])})"
            if names[0] != expected_script(num, title):
                report += f", expected {expected_script(num, title)}"
            if not case["scriptLinked"]:
                report += ", not linked from the issue"
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
