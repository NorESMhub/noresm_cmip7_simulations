"""Write progress.json for the tracker from the GitHub issues and the files on NIRD.

workflow/README.md describes the case issues, the run scripts and how to run it.
"""

import argparse
import datetime
import fnmatch
import glob
import gzip
import http.client
import json
import os
import re
import shlex
import urllib.error
import urllib.parse
import urllib.request

REPO = "NorESMhub/noresm_cmip7_simulations"
# Where things are on NIRD, the defaults for the options.
PROGRESS = "/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json"
CASE_DIR = "/nird/datalake/NS9560K/noresm3/cases/{case}"
CMOR4CMIP7_DIR = "/nird/datapeak/NS9034K/.CMIP7/NorESM3-{resolution}/{experiment}/{variant}"
# compset.resolution.version...: n1850GHGGaxg.LM.nor30b28.011.20261102
TITLE = re.compile(r"^[A-Za-z0-9-]+\.(LM|MM)\.nor30(b\d+)\.")
RESOLUTION = {"LM": "LM", "MM": "MM"}
# YYYY-MM, YYYY-MM-DD or YYYY-MM-DD-SSSSS just before .nc
DATE = re.compile(r"\.(\d{4})-(\d{2})(?:-(\d{2})(?:-\d{5})?)?\.nc$")
# cmip7-prep's record of the steps that finished for one set of years.
COMPLETED = re.compile(r"completed_steps_(\d+)-(\d+)\.json$")
# A CMOR file's variable and the years of its time range, before .nc:
# so_Omon_NorESM3_piControl_r1i1p1f1_gn_000101-001012.nc
CMOR_FILE = re.compile(r"^(.+)_(\d{4})\d*-(\d{4})\d*\.nc$")
# A model date in a file name, its year first: 0001, 0001-01, 0001-01-01-00000, 000101.
# A kind of output measured over at least this many years is not measured again.
STORAGE_YEARS = 5
NAME_DATE = re.compile(r"(?<!\d)(\d{4})(?:\d{2}|\d{4})?(?:-\d{2}(?:-\d{2}(?:-\d{5})?)?)?(?!\d)")
def entry(label, value):
    """An entry of an issue's description: "- entry: value" on one line, the label in bold or
    not, or the label as a heading, "### label", with the value on the next line that isn't
    blank."""
    return re.compile(r"^[ \t]*(?:[-*+][ \t]+|#{1,6}[ \t]*)?(?:\*\*)?" + label
                      + r"(?:\*\*)?[ \t]*:?[ \t]*(?:\*\*)?\s*`?(" + value + r")", re.M | re.I)


# Where each tool's CMORized output is, when it isn't in the default place:
# "- cmip7prep output root: /nird/...".
OUTPUT_ROOTS = {tool: entry(tool + r"[ \t]+output(?:[ \t]+root)?", r"/[^\s`]+")
                for tool in ("cmip7prep", "cmor4cmip7")}
# The version the case's years are CMORized into, with or without the v:
# "- cmor data version: v20261028".
DATA_VERSION = entry(r"cmor[ \t]+data[ \t]+version", r"v?\d{8}\b")
# The run scripts are on this branch, below scripts/, each named after its case's issue:
# DECK/piControl/011.piControl.LM.beta28.r1i1p1f1.20261102.sh is #11's.
RUNSCRIPTS_BRANCH = "CMIP7_Runscripts"
SCRIPT_ISSUE = re.compile(r"^0*(\d+)\..*\.sh$")
# The settings read from a run script's ./xmlchange lines, and the names they are written under.
RUN_SETTINGS = {"RUN_TYPE": "type", "RUN_REFCASE": "refcase", "RUN_REFDATE": "refdate",
                "RUN_STARTDATE": "startdate"}
# A shell variable given a plain value: refcase="n1850GHGGaxg.LM.nor30b27.002.20261016"
SHELL_VARIABLE = re.compile(r"""^(?:export\s+)?([A-Za-z_]\w*)=("[^"$`]*"|'[^']*'|[^\s"'$`;]*)\s*(?:#.*)?$""")
XMLCHANGE = re.compile(r"^\./xmlchange\s+(.*)$")
# The version directory a CMOR file sits under: .../r1i1p1f1/v20261028/so_..._000101-001012.nc
VERSION_DIR = re.compile(r"^v\d{8}$")
VARIANT = re.compile(r"^r\d+i\d+p\d+f\d+$")
# Lines of a timing file, one per job: noresm_timing.<case>.<job id>.<date>.
TIMING_LINES = {
    "cost": re.compile(r"^\s*Model Cost:\s*([\d.]+)\s+pe-hrs/simulated_year", re.M),
    "sypd": re.compile(r"^\s*Model Throughput:\s*([\d.]+)\s+simulated_years/day", re.M),
    "days": re.compile(r"^\s*run length\s*:\s*([\d.]+)\s+days", re.M),
    "pes": re.compile(r"^\s*pe count for cost estimate\s*:\s*(\d+)", re.M),
    "machine": re.compile(r"^\s*Machine\s*:\s*(\S+)", re.M),
    "date": re.compile(r"^\s*Curr Date\s*:\s*(.+?)\s*$", re.M),
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


def list_run_scripts(repo, scripts_dir=None):
    """The run scripts' paths below scripts/, from scripts_dir if given and from the
    CMIP7_Runscripts branch on GitHub otherwise, and why they couldn't be listed if they couldn't."""
    try:
        if scripts_dir:
            return [os.path.relpath(os.path.join(d, f), scripts_dir)
                    for d, _, files in os.walk(scripts_dir) for f in files if f.endswith(".sh")], None
        url = f"https://api.github.com/repos/{repo}/git/trees/{RUNSCRIPTS_BRANCH}?recursive=1"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "nird_progress"})
        with urllib.request.urlopen(req, timeout=30) as r:
            tree = json.load(r)["tree"]
        return [t["path"][len("scripts/"):] for t in tree
                if t["type"] == "blob" and t["path"].startswith("scripts/") and t["path"].endswith(".sh")], None
    except (OSError, ValueError, KeyError, http.client.HTTPException) as e:
        return None, str(getattr(e, "reason", None) or e)


def read_run_script(repo, path, scripts_dir=None):
    """The text of the run script at path below scripts/, from scripts_dir if given and from
    the CMIP7_Runscripts branch on GitHub otherwise, and why it couldn't be read if it couldn't."""
    try:
        if scripts_dir:
            with open(os.path.join(scripts_dir, path), encoding="utf-8", errors="replace") as f:
                return f.read(), None
        url = (f"https://raw.githubusercontent.com/{repo}/{RUNSCRIPTS_BRANCH}/scripts/"
               + urllib.parse.quote(path))
        req = urllib.request.Request(url, headers={"User-Agent": "nird_progress"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace"), None
    except FileNotFoundError:
        return None, f"not found at scripts/{path}"
    except urllib.error.HTTPError as e:
        return None, f"not found at scripts/{path}" if e.code == 404 else f"not read, HTTP {e.code}"
    except (OSError, http.client.HTTPException) as e:
        return None, str(getattr(e, "reason", None) or e)


def run_settings(text):
    """The RUN_TYPE, RUN_REFCASE, RUN_REFDATE and RUN_STARTDATE a run script sets with
    ./xmlchange, either as KEY=value[,KEY=value] or as --id KEY --val value. A shell variable
    the script gives a plain value, such as refcase="...", is filled in; a setting whose value
    still depends on the shell, such as $(date), is left out."""
    variables, settings = {}, {}

    def expand(value):
        return re.sub(r"\$\{(\w+)\}|\$(\w+)",
                      lambda m: variables.get(m.group(1) or m.group(2), m.group(0)), value)

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if m := SHELL_VARIABLE.match(line):
            variables[m.group(1)] = m.group(2).strip("\"'")
            continue
        m = XMLCHANGE.match(line)
        if not m:
            continue
        try:
            args = shlex.split(expand(m.group(1)), comments=True)
        except ValueError:
            continue
        pairs = []
        if "--id" in args:
            i = args.index("--id")
            val = args[args.index("--val") + 1] if "--val" in args[:-1] else None
            if i + 1 < len(args) and val is not None:
                pairs.append((args[i + 1], val))
        else:
            for arg in args:
                if not arg.startswith("-"):
                    pairs += [tuple(p.split("=", 1)) for p in arg.split(",") if "=" in p]
        for key, value in pairs:
            if key in RUN_SETTINGS and "$" not in value:
                settings[RUN_SETTINGS[key]] = value
    return settings


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


_cmor_files = {}


def file_version(dirpath):
    """The version directory, vYYYYMMDD, nearest above a file; None if there is none."""
    return next((p for p in reversed(dirpath.split(os.sep)) if VERSION_DIR.match(p)), None)


def cmor_files(directory):
    """(name match, version, bytes) of each CMOR file with a time range under the directory,
    read once per run."""
    if directory not in _cmor_files:
        _cmor_files[directory] = [(m, file_version(d), size(os.path.join(d, name)))
                                  for d, _, names in os.walk(directory)
                                  for name in names if (m := CMOR_FILE.match(name))]
    return _cmor_files[directory]


def size(path):
    """The file's size in bytes, 0 if it can't be read."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def file_years(name):
    """The model years a file's name covers: from its first to its last date, written as
    YYYY, YYYY-MM[-DD[-SSSSS]] or YYYYMM[DD]. The case name is taken out first, since its
    date is not a model date."""
    years = [int(m.group(1)) for m in NAME_DATE.finditer(name)]
    return range(min(years), max(years) + 1) if years else range(0)


def output_size(paths, case):
    """{gb, years} for the netCDF files: their size, and how many model years their names
    cover; None if there are no dated ones."""
    years, total = set(), 0
    for path in paths:
        if path.endswith(".nc") and (ys := file_years(os.path.basename(path).replace(case, ""))):
            years.update(ys)
            total += size(path)
    return {"gb": round(total / 1e9, 3), "years": len(years)} if years else None


def files_below(directory, skip=None):
    """The paths of the files below the directory, leaving out its subdirectory skip."""
    paths = []
    for d, subdirs, names in os.walk(directory):
        if d == directory and skip in subdirs:
            subdirs.remove(skip)
        paths += [os.path.join(d, n) for n in names]
    return paths


def settled_storage(storage):
    """The kinds of a case's earlier measurement to keep: those with at least
    STORAGE_YEARS years, by then a steady rate. History counts its longest component, and
    CMOR is kept tool by tool."""
    storage = storage if isinstance(storage, dict) else {}
    kept = {k: v for k, v in storage.items()
            if k in ("rest", "timeseries") and isinstance(v, dict) and v.get("years", 0) >= STORAGE_YEARS}
    if max((s.get("years", 0) for s in storage.get("hist", {}).values()), default=0) >= STORAGE_YEARS:
        kept["hist"] = storage["hist"]
    if cmor := {t: s for t, s in storage.get("cmor", {}).items() if s.get("years", 0) >= STORAGE_YEARS}:
        kept["cmor"] = cmor
    return kept


def case_storage(case_dir, case, prep_dir, cmor4cmip7_dir, labels, kept=None):
    """How much output the case has on NIRD, as {gb, years} for each kind: hist, a dict by
    component of the <component>/hist directories; rest, the restart sets in rest/, over the
    years the history covers; timeseries, cmip7-prep's time series, the files in its
    directory outside cmor/; and cmor, by tool, the CMOR files, each version's years
    counted. The kinds in kept, from an earlier run, are not measured again. A kind with
    nothing on NIRD is left out."""
    kept = kept or {}
    storage = {k: v for k, v in kept.items() if k != "cmor"}
    if case_dir and os.path.isdir(case_dir):
        if "hist" not in storage:
            hist = {}
            for comp in sorted(os.listdir(case_dir)):
                if os.path.isdir(d := os.path.join(case_dir, comp, "hist")) and (s := output_size(files_below(d), case)):
                    hist[comp] = s
            if hist:
                storage["hist"] = hist
        years = max((s["years"] for s in storage.get("hist", {}).values()), default=0)
        if "rest" not in storage and years and (rest := files_below(os.path.join(case_dir, "rest"))):
            storage["rest"] = {"gb": round(sum(map(size, rest)) / 1e9, 3), "years": years}
    if "timeseries" not in storage and prep_dir and (s := output_size(files_below(prep_dir, skip="cmor"), case)):
        storage["timeseries"] = s
    cmor = dict(kept.get("cmor", {}))
    prep_cmor = os.path.join(prep_dir, "cmor") if prep_dir else None
    for tool, d in (("cmip7prep", prep_cmor), ("cmor4cmip7", cmor4cmip7_dir)):
        if tool not in cmor and d and os.path.isdir(d):
            by_version, total = {}, 0
            for m, v, b in case_files(d, labels):
                by_version.setdefault(v, set()).update(range(int(m.group(2)), int(m.group(3)) + 1))
                total += b
            if years := sum(len(ys) for ys in by_version.values()):
                cmor[tool] = {"gb": round(total / 1e9, 3), "years": years}
    if cmor:
        storage["cmor"] = cmor
    return storage


def year_ranges(years):
    """[[first, last], ...] for the runs of consecutive years."""
    ranges = []
    for y in sorted(years):
        if ranges and y == ranges[-1][1] + 1:
            ranges[-1][1] = y
        else:
            ranges.append([y, y])
    return ranges


def case_files(directory, labels):
    """(name match, version) of the case's CMOR files under the directory: those whose name
    has one of its labels as the experiment, followed by its variant label, as in
    so_Omon_NorESM3_piControl_r1i1p1f1_gn_000101-001012.nc."""
    variant = next((l for l in labels if VARIANT.match(l)), None)
    if not variant:
        return []
    keys = [f"_{l}_{variant}_" for l in labels if l != variant]
    return [(m, v, b) for m, v, b in cmor_files(directory) if any(k in m.group(0) for k in keys)]


def cmor_file_years(directory, labels):
    """[[first, last], ...]: the years every variable of the case has a file for under the
    directory, from the time ranges in the CMOR file names. Files without a time range
    (fixed fields) don't count."""
    by_var = {}
    for m, _, _ in case_files(directory, labels):
        by_var.setdefault(m.group(1), set()).update(range(int(m.group(2)), int(m.group(3)) + 1))
    return year_ranges(set.intersection(*by_var.values())) if by_var else []


def cmor_versions(directory, labels):
    """{version: [[first, last], ...]}: the years of the case's CMOR files under the
    directory, by the version directory they are in."""
    by_version = {}
    for m, v, _ in case_files(directory, labels):
        if v:
            by_version.setdefault(v, set()).update(range(int(m.group(2)), int(m.group(3)) + 1))
    return {v: year_ranges(ys) for v, ys in sorted(by_version.items())}


def read_timing_file(path):
    """{cost, sypd, days, pes, machine, date} from one timing file; None if it lacks cost or
    throughput. The date is when the job ended (Curr Date), or the file's time without one."""
    opener = gzip.open if path.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            text = f.read()
        mtime = os.path.getmtime(path)
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
    try:
        t["date"] = datetime.datetime.strptime(found.get("date", ""), "%a %b %d %H:%M:%S %Y")
    except ValueError:
        t["date"] = datetime.datetime.fromtimestamp(mtime)
    return t


def case_timing(directory):
    """The case's cost and throughput on each machine it ran on, averaged over all its
    timing files there with each job weighted by the years it simulated: cost in pe-hours
    per simulated year, throughput in simulated years per day. Each machine's entry also
    lists its jobs, [end date, cost, throughput, years], for the page's plot of how the
    timings vary. Returns ([{machine, jobs, years, cost, sypd, pes, runs}], the machine of
    its latest job), or (None, None) if there are no readable timing files."""
    paths = glob.glob(os.path.join(glob.escape(directory), "noresm_timing.*"))
    jobs = sorted((t for path in paths if (t := read_timing_file(path))), key=lambda t: t["date"])
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
        entry["runs"] = [[t["date"].strftime("%Y-%m-%d %H:%M"), t["cost"], t["sypd"], round(y, 2)]
                         for t, y in zip(mjobs, years)]
        timing.append(entry)
    return timing, jobs[-1].get("machine", "unknown").lower()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out", nargs="?", default=PROGRESS, help=f"where to write progress.json (default {PROGRESS})")
    p.add_argument("--case-dir", default=CASE_DIR,
                   help=f'each case\'s archive directory, with <component>/hist and rest (default "{CASE_DIR}")')
    p.add_argument("--dir", help='the directory of each case\'s dated files (default "<case-dir>/atm/hist")')
    p.add_argument("--cmor-dir", help='each case\'s cmip7-prep output directory, for a case whose issue names '
                                      'no cmip7prep output root (default "<case-dir>.cmor")')
    p.add_argument("--cmor4cmip7-dir", default=CMOR4CMIP7_DIR,
                   help='each simulation\'s cmor4cmip7 variant directory, for a case whose issue names no '
                        f'cmor4cmip7 output root (default "{CMOR4CMIP7_DIR}")')
    p.add_argument("--timing-dir", action="append",
                   help='each case\'s timing directory; give it more than once for cases laid out '
                        'differently, and the first that exists is read (default "<case-dir>/timing" '
                        'and "<case-dir>/{case}/timing")')
    p.add_argument("--pattern", default="*.cam.i.*.nc", help="dated files that count, as a shell pattern")
    p.add_argument("--repo", default=REPO, help="the repository with the case issues")
    p.add_argument("--issues", help="read the issues from this JSON file instead of GitHub")
    p.add_argument("--scripts", help="read the run scripts from this scripts/ directory, e.g. in a "
                                     "checkout of the CMIP7_Runscripts branch, instead of GitHub")
    p.add_argument("--remeasure", action="store_true",
                   help="measure every case's output again, instead of keeping what the last "
                        "progress.json has for it")
    a = p.parse_args()
    a.dir = a.dir or a.case_dir + "/atm/hist"
    a.cmor_dir = a.cmor_dir or a.case_dir + ".cmor"
    a.timing_dir = a.timing_dir or [a.case_dir + "/timing", a.case_dir + "/{case}/timing"]

    # Each case's output as the last run measured it, kept where it covers enough years.
    earlier = {}
    if a.case_dir and not a.remeasure:
        try:
            with open(a.out, encoding="utf-8") as f:
                earlier = {c["issue"]: settled_storage(c.get("storage")) for c in json.load(f)["cases"]}
        except (OSError, ValueError, KeyError, TypeError):
            pass

    if a.issues:
        with open(a.issues, encoding="utf-8") as f:
            issues = [i for i in json.load(f) if "pull_request" not in i]
    else:
        issues = fetch_issues(a.repo)

    # A case's parent is the issue whose title is its RUN_REFCASE.
    issue_of_case = {i["title"].strip(): i["number"] for i in issues}
    # A case's run script is the one whose name starts with its issue number.
    scripts, why = list_run_scripts(a.repo, a.scripts)
    if scripts is None:
        print(f"The run scripts could not be listed: {why}")
    scripts_of_issue = {}
    for path in sorted(scripts or []):
        if m := SCRIPT_ISSUE.match(os.path.basename(path)):
            scripts_of_issue.setdefault(int(m.group(1)), []).append(path)
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
        body = issue.get("body") or ""
        # Each tool's output root is the issue's entry, or the default without one. Either may
        # have {case}, {resolution}, {experiment} and {variant} in it, or <case> and so on,
        # filled in from the issue;
        # the experiment is whichever label names an existing directory. A default root counts
        # only where it exists.
        given = {tool: m.group(1) for tool, r in OUTPUT_ROOTS.items() if (m := r.search(body))}
        variant = next((l for l in labels if VARIANT.match(l)), None)
        output = {}
        for tool, default in (("cmip7prep", a.cmor_dir), ("cmor4cmip7", a.cmor4cmip7_dir)):
            root = given.get(tool) or default
            if not root:
                continue
            root = re.sub(r"<(case|resolution|experiment|variant)>", r"{\1}", root)
            if "{variant}" in root and not variant:
                continue
            root = (root.replace("{case}", title).replace("{resolution}", case["resolution"])
                    .replace("{variant}", variant or ""))
            places = ([root.replace("{experiment}", l) for l in labels if l != variant]
                      if "{experiment}" in root else [root])
            if d := next((d for d in places if os.path.isdir(d)), None):
                output[tool] = d
            elif tool in given and places:
                output[tool] = places[0]
        if output:
            case["cmorOutput"] = output
        found = scripts_of_issue.get(num, [])
        if len(found) > 1:
            report += "; more than one run script: " + ", ".join(found)
        elif found:
            case["runScript"] = found[0]
            text, why = read_run_script(a.repo, case["runScript"], a.scripts)
            if text is None:
                report += f"; run script {why}"
            elif start := run_settings(text):
                if start.get("refcase") in issue_of_case:
                    start["parent"] = issue_of_case[start["refcase"]]
                case["start"] = start
                report += "; " + " ".join(f"{k} {v}" for k, v in start.items())
        else:
            report += "; no run script"
        if m := DATA_VERSION.search(body):
            case["dataVersion"] = "v" + m.group(1).lstrip("vV")
            report += "; CMOR data version " + case["dataVersion"]
        versions = {}
        if prep_dir := output.get("cmip7prep"):
            sets = cmor_sets(prep_dir)
            if sets:
                case["cmor"] = sets
                report += "; cmip7prep " + ", ".join(f"{s['first']}-{s['last']}" for s in sets)
            # cmip7-prep writes its CMOR files under cmor/ in its output directory.
            prep_cmor = os.path.join(prep_dir, "cmor")
            if v := cmor_versions(prep_cmor if os.path.isdir(prep_cmor) else prep_dir, labels):
                versions["cmip7prep"] = v
        if "cmor4cmip7" in output:
            ranges = cmor_file_years(output["cmor4cmip7"], labels)
            if ranges:
                case["cmor4cmip7"] = ranges
            report += "; cmor4cmip7 " + (", ".join(f"{f}-{l}" for f, l in ranges) or "nothing yet")
            if v := cmor_versions(output["cmor4cmip7"], labels):
                versions["cmor4cmip7"] = v
        if versions:
            case["cmorVersions"] = versions
            report += "".join(f"; {tool} in " + ", ".join(v) for tool, v in versions.items())
        kept = earlier.get(num, {})
        storage = case_storage(a.case_dir.format(case=title) if a.case_dir else None, title,
                               prep_dir, output.get("cmor4cmip7"), labels, kept)
        if storage:
            case["storage"] = storage
            sizes = {"history": list(storage.get("hist", {}).values()), "restarts": [storage.get("rest")],
                     "time series": [storage.get("timeseries")], "CMOR": list(storage.get("cmor", {}).values())}
            report += "".join(f"; {kind} {sum(s['gb'] for s in found if s):.1f} GB"
                              for kind, found in sizes.items() if any(found))
            if kept:
                names = {"hist": "history", "rest": "restarts", "timeseries": "time series", "cmor": "CMOR"}
                report += " (kept from the last run: " + ", ".join(
                    names[k] + (" of " + " and ".join(kept[k]) if k == "cmor" else "") for k in kept) + ")"
        timing_dir = next((d for d in (t.format(case=title) for t in a.timing_dir) if os.path.isdir(d)), None)
        if timing_dir:
            timing, machine = case_timing(timing_dir)
            if timing:
                case["timing"], case["machine"] = timing, machine
                report += "".join(f"; {t['machine']} {t['cost']} pe-hrs/yr, {t['sypd']} SYPD over {t['jobs']} jobs"
                                  for t in timing)
        cases.append(case)
        print(f"#{num} {title} [{', '.join(labels) or 'no labels'}]: {report}")

    data = {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "repo": a.repo,
            "cases": cases, "skipped": skipped}
    tmp = a.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, a.out)
    print(f"{a.out}: {len(cases)} cases")


if __name__ == "__main__":
    main()
