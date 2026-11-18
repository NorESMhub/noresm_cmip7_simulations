"""Write progress.json for the tracker from the GitHub issues and the files on NIRD, and
build the tracker page, index.html, next to it.

workflow/README.md describes what it reads and records.
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
import sys
import urllib.error
import urllib.parse
import urllib.request

# The page is built by build_scheduler.py, next to this script. python3 -I leaves this
# script's directory off the import path, so it is added here.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_scheduler  # noqa: E402

REPO = "NorESMhub/noresm_cmip7_simulations"
# The NorESM3 CMIP7 experiments spreadsheet and its DECK_FASTTRACK tab, which the page's runs
# come from. It is read on every run, so it must stay readable by anyone with the link.
SHEET = "https://docs.google.com/spreadsheets/d/1PZQHmOHVENJeCqwSfk4wfp8okQXw60Bv"
SHEET_TAB = "13331701"


class Failed(Exception):
    """Something the tracker needs could not be read, so neither progress.json nor the page
    is updated."""


# Where things are on NIRD. {case} is a case's name; {resolution}, {experiment} and
# {variant} are its simulation's.
PROGRESS = "/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json"
CASE_DIR = "/nird/datalake/NS9560K/noresm3/cases/{case}"
# A case's model date comes from the dated files that fit HIST_PATTERN in HIST_DIR.
HIST_DIR = CASE_DIR + "/atm/hist"
HIST_PATTERN = "*.cam.i.*.nc"
# Each tool's output, for a case whose issue gives no output root.
CMIP7PREP_DIR = CASE_DIR + ".cmor"
CMOR4CMIP7_DIR = "/nird/datapeak/NS9034K/.CMIP7/NorESM3-{resolution}/{experiment}/{variant}"
# The characters an issue's title may have.
TITLE_CHARACTERS = re.compile(r"[A-Za-z0-9._-]+")
# compset.resolution.version...: n1850GHGGaxg.LM.nor30b28.r1i1p1f1.011.20261102, or without
# the variant, n1850GHGGaxg.LM.nor30b28.011.20261102. The beta may end in a letter: nor30b29a.
TITLE = re.compile(r"^[A-Za-z0-9-]+\.(LM|MM)\.nor30(b\d+[a-z]?)\.")
RESOLUTION = {"LM": "LM", "MM": "MM"}
# YYYY-MM, YYYY-MM-DD or YYYY-MM-DD-SSSSS just before .nc
DATE = re.compile(r"\.(\d{4})-(\d{2})(?:-(\d{2})(?:-\d{5})?)?\.nc$")
# cmip7-prep's record of the steps that finished for one set of years.
COMPLETED = re.compile(r"completed_steps_(\d+)-(\d+)\.json$")
# A CMOR file's variable and the years of its time range, before .nc:
# so_Omon_NorESM3_piControl_r1i1p1f1_gn_000101-001012.nc
CMOR_FILE = re.compile(r"^(.+)_(\d{4})\d*-(\d{4})\d*\.nc$")
# The full start and end dates of a CMOR file's time range, e.g. 185001 and 185912.
CMOR_TIME = re.compile(r"_(\d{4,14})-(\d{4,14})\.nc$")
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
# The CMORization issues, each naming the cases it CMORizes, and the CMOR tag version in its
# description, on the line after its label: "**cmor tag version (decided by ...)**\n20261109".
CMOR_REPO = "NorESMhub/CMIP7_CMOR-Publish"
CMOR_TAG_VERSION = re.compile(r"cmor[ \t]+tag[ \t]+version[^\d]{0,300}?\bv?(\d{8})\b", re.I)
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


def github_api(url):
    """The JSON GitHub's API returns for url. GitHub allows 60 anonymous requests an hour
    from one address, which every user on NIRD shares; once they are used up, this raises
    Failed with the time they are available again."""
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "nird_progress"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            reset = e.headers.get("X-RateLimit-Reset")
            when = (datetime.datetime.fromtimestamp(int(reset)).astimezone().strftime("%H:%M %Z")
                    if reset and reset.isdigit() else "within the hour")
            raise Failed("GitHub's limit of 60 requests an hour from NIRD has been used up, by this "
                         f"script or by other users on NIRD. Run the script again after {when}.") from e
        raise


def fetch_sheet():
    """The spreadsheet's DECK_FASTTRACK tab as CSV text. Raises Failed if it can't be read,
    including when Google sends a sign-in page because the spreadsheet is no longer shared."""
    url = f"{SHEET}/export?format=csv&gid={SHEET_TAB}"
    req = urllib.request.Request(url, headers={"User-Agent": "nird_progress"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            kind = r.headers.get_content_type()
            text = r.read().decode("utf-8")
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise Failed(f"The spreadsheet could not be read: {getattr(e, 'reason', None) or e}") from e
    if kind != "text/csv":
        raise Failed(f"The spreadsheet came back as {kind}, not CSV: it may no longer be readable "
                     "by anyone with the link.")
    return text


def fetch_issues(repo):
    """Every issue in the repository, open and closed, without pull requests."""
    issues, page = [], 1
    while True:
        batch = github_api(f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}")
        issues.extend(i for i in batch if "pull_request" not in i)
        # A page with fewer than a hundred is the last, so no empty page is fetched after it.
        if len(batch) < 100:
            return issues
        page += 1


def list_run_scripts(repo, scripts_dir=None):
    """The run scripts' paths below scripts/, from scripts_dir if given and from the
    CMIP7_Runscripts branch on GitHub otherwise, and why they couldn't be listed if they couldn't."""
    try:
        if scripts_dir:
            if not os.path.isdir(scripts_dir):
                return None, f"{scripts_dir} is not a directory"
            return [os.path.relpath(os.path.join(d, f), scripts_dir)
                    for d, _, files in os.walk(scripts_dir) for f in files if f.endswith(".sh")], None
        tree = github_api(f"https://api.github.com/repos/{repo}/git/trees/{RUNSCRIPTS_BRANCH}?recursive=1")["tree"]
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


# Stands for a part of a case name the script only knows when it runs, such as $(date).
UNKNOWN = "\0"
# Variables that may hold the case name, in a script without a create_newcase line.
CASE_VARIABLES = ("casename", "CASENAME", "case_name", "CASE_NAME", "case", "CASE")


def script_case_name(text):
    """The case name a run script creates: the last part of create_newcase's --case path, with
    the shell variables it uses filled in. A part known only when the script runs, such as
    $(date +%Y%m%d), is UNKNOWN. None if the script names no case."""
    # Commands continued over several lines with a backslash become one line, and $(...) is
    # replaced first, since it may hold quotes of its own.
    text = re.sub(r"\\\n", " ", text)
    text = re.sub(r"\$\((?:[^()]|\([^()]*\))*\)|`[^`]*`", UNKNOWN, text)
    variables, newcase = {}, None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if m := re.match(r"""^(?:export\s+)?([A-Za-z_]\w*)=("[^"]*"|'[^']*'|[^\s;#]*)""", line):
            variables[m.group(1)] = m.group(2).strip("\"'")
        elif m := re.search(r"create_newcase\b.*?--case(?:\s+|=)(\"[^\"]*\"|'[^']*'|[^\s;]+)", line):
            newcase = m.group(1).strip("\"'")

    def expand(value, depth=0):
        if depth > 10:
            return UNKNOWN
        return re.sub(r"\$\{(\w+)[^}]*\}|\$(\w+)",
                      lambda m: expand(variables[m.group(1) or m.group(2)], depth + 1)
                      if (m.group(1) or m.group(2)) in variables else UNKNOWN, value)

    raw = newcase or next((variables[v] for v in CASE_VARIABLES if v in variables), None)
    if not raw:
        return None
    name = expand(raw).rstrip("/").split("/")[-1]
    return name if name.strip(UNKNOWN) else None


def find_case(name, case_dir):
    """The case's name on NIRD: name itself if all of it is known, or else the one case
    directory, below case_dir with {case} as its last part, whose name fits name with any
    UNKNOWN part, e.g. its $(date). Of several that fit, the latest by name. None if none
    fits; the directories that fit are returned too."""
    if UNKNOWN not in name:
        return name, []
    parent, last = os.path.split(case_dir)
    if last != "{case}" or not os.path.isdir(parent):
        return None, []
    pattern = "*".join(glob.escape(p) for p in name.split(UNKNOWN))
    fits = sorted(d for d in os.listdir(parent) if fnmatch.fnmatchcase(d, pattern))
    return (fits[-1] if fits else None), fits


def model_dates(directory, pattern):
    """The latest (year, month, day) among the matching files, and the years between the
    first and the last file that have no file. None if there are no files, False if the
    directory doesn't exist. A monthly file (no day) is dated at the start of the next month."""
    if not os.path.isdir(directory):
        return False
    dates, years = [], set()
    for name in os.listdir(directory):
        if not fnmatch.fnmatchcase(name, pattern):
            continue
        m = DATE.search(name)
        if not m:
            continue
        y, mo, d = int(m.group(1)), int(m.group(2)), m.group(3)
        years.add(y)
        if d is None:
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
            d = 1
        dates.append((y, mo, int(d)))
    if not dates:
        return None
    return max(dates), [y for y in range(min(years), max(years)) if y not in years]


def cmor_sets(directory):
    """[{first, last, steps, failed}] for each completed_steps_<first>-<last>.json. steps are
    the cmor- steps it lists, the ones that finished. failed are the cmor- steps that ran, so
    have a log in logs/<first>-<last>/, but are not listed: they failed or are still running.
    The file alone can't show a realm that failed in every set, since it lists no failures."""
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
        logs = os.path.join(directory, "logs", f"{m.group(1)}-{m.group(2)}")
        ran = {n[:-len(".log")] for n in (os.listdir(logs) if os.path.isdir(logs) else [])
               if n.startswith("cmor-") and n.endswith(".log")}
        sets.append({"first": int(m.group(1)), "last": int(m.group(2)), "steps": steps,
                     "failed": sorted(ran - set(steps))})
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


def variable_name(prefix):
    """A CMOR file's variable as its first two name fields, e.g. tos_tavg-u-hxy-sea or so_Omon."""
    return "_".join(prefix.split("_")[:2])


def cmor_problems(directory, labels):
    """What is wrong with the case's CMOR files under the directory, each kind grouped by the
    years it affects: missing, the variables with no file for years other variables have;
    overlaps, the variables with a year in more than one file of the same version, by
    version. None if nothing is wrong."""
    by_var, files = {}, {}
    for m, v, _ in case_files(directory, labels):
        by_var.setdefault(m.group(1), set()).update(range(int(m.group(2)), int(m.group(3)) + 1))
        t = CMOR_TIME.search(m.group(0))
        start, end = t.group(1).ljust(14, "0"), t.group(2).ljust(14, "9")
        files.setdefault((m.group(1), v), []).append((start, end))
    every = set().union(*by_var.values()) if by_var else set()
    missing = {}
    for var, years in by_var.items():
        if gap := every - years:
            missing.setdefault(tuple(map(tuple, year_ranges(gap))), set()).add(variable_name(var))
    overlaps = {}
    for (var, v), spans in files.items():
        spans.sort()
        years, end = set(), None
        for s, e in spans:
            if end is not None and s <= end:
                years.update(range(int(s[:4]), int(min(e, end)[:4]) + 1))
            end = e if end is None else max(end, e)
        if years:
            overlaps.setdefault((v, tuple(map(tuple, year_ranges(years)))), set()).add(variable_name(var))
    problems = {}
    if missing:
        problems["missing"] = [{"years": [list(r) for r in ys], "variables": sorted(vs)}
                               for ys, vs in sorted(missing.items())]
    if overlaps:
        problems["overlaps"] = [{"version": v, "years": [list(r) for r in ys], "variables": sorted(vs)}
                                for (v, ys), vs in sorted(overlaps.items(), key=lambda kv: (kv[0][0] or "", kv[0][1]))]
    return problems or None


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
    timing files there with each job weighted by the years it simulated: cost in pe-hours,
    which are core-hours, per simulated year, throughput in simulated years per day. Each machine's entry also
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
    # On NIRD the script is run with no arguments. They are for testing a change without
    # touching the published page, and for measuring the storage again.
    p = argparse.ArgumentParser()
    p.add_argument("out", nargs="?", default=PROGRESS,
                   help=f"where to write progress.json; the page, index.html, goes next to it (default {PROGRESS})")
    p.add_argument("--sheet", help="read the experiments from this CSV file, the spreadsheet's "
                                   "DECK_FASTTRACK tab, instead of from the spreadsheet")
    p.add_argument("--issues", help="read the case issues from this JSON file instead of GitHub")
    p.add_argument("--scripts", help="read the run scripts from this scripts/ directory, e.g. in a "
                                     "checkout of the CMIP7_Runscripts branch, instead of GitHub")
    p.add_argument("--remeasure-storage", action="store_true",
                   help="measure every case's storage on NIRD again, instead of keeping what the "
                        "last progress.json has for it; the cost and throughput are read again "
                        "on every run regardless")
    a = p.parse_args()

    # Each case's output as the last run measured it, kept where it covers enough years.
    earlier = {}
    if not a.remeasure_storage:
        try:
            with open(a.out, encoding="utf-8") as f:
                earlier = {c["issue"]: settled_storage(c.get("storage")) for c in json.load(f)["cases"]}
        except (OSError, ValueError, KeyError, TypeError):
            pass

    if a.issues:
        with open(a.issues, encoding="utf-8") as f:
            issues = [i for i in json.load(f) if "pull_request" not in i]
    else:
        issues = fetch_issues(REPO)
    # Only an issue whose title is a name, of letters, digits, ".", "-" and "_", is a case.
    # Any other title, such as one with a space, is a note or a placeholder for a run not
    # set up yet, and the issue is left out.
    named = []
    for issue in issues:
        if TITLE_CHARACTERS.fullmatch(issue["title"].strip()):
            named.append(issue)
        else:
            print(f"#{issue['number']}: skipped, its title is not a name: {issue['title'].strip()!r}")
    issues = named

    # A case's CMORization issues are those in CMIP7_CMOR-Publish that name the case.
    try:
        cmor_issues = fetch_issues(CMOR_REPO)
    except (OSError, ValueError, http.client.HTTPException) as e:
        raise Failed(f"The CMORization issues in {CMOR_REPO} could not be read: {e}") from e
    # A case's run script is the one whose name starts with its issue number.
    scripts, why = list_run_scripts(REPO, a.scripts)
    if scripts is None:
        raise Failed(f"The run scripts could not be listed: {why}")
    scripts_of_issue = {}
    for path in sorted(scripts or []):
        if m := SCRIPT_ISSUE.match(os.path.basename(path)):
            scripts_of_issue.setdefault(int(m.group(1)), []).append(path)

    # Each issue's case name is the one its run script gives create_newcase, so the issue's
    # title doesn't have to be the case name. The part of the name the script only knows
    # when it runs, such as $(date), comes from the case's directory on NIRD. An issue with
    # no run script, or whose script names no case, falls back to its title.
    tracked = []
    for issue in sorted(issues, key=lambda i: i["number"]):
        num, title = issue["number"], issue["title"].strip()
        labels = [l["name"] for l in issue.get("labels", [])]
        if "test" in labels:
            continue
        script_paths, text, name, notes = scripts_of_issue.get(num, []), None, None, []
        if len(script_paths) == 1:
            text, why = read_run_script(REPO, script_paths[0], a.scripts)
            if text is None:
                raise Failed(f"#{num}'s run script, scripts/{script_paths[0]}, could not be read: {why}")
            if pattern := script_case_name(text):
                name, fits = find_case(pattern, CASE_DIR)
                if len(fits) > 1:
                    notes.append("more than one case directory fits its run script: " + ", ".join(fits)
                                 + f"; {name} is used")
                if not name:
                    # Nothing on NIRD yet: the name as far as the script knows it.
                    name = pattern.replace(UNKNOWN, "*")
            else:
                notes.append("its run script names no case; the title is used")
        tracked.append((issue, num, title, labels, script_paths, text, name or title, notes))
    # A case's parent is the issue whose case is its RUN_REFCASE.
    issue_of_case = {name: num for _, num, _, _, _, _, name, _ in tracked}

    cases, skipped = [], []
    for issue, num, title, labels, script_paths, text, name, notes in tracked:
        m = TITLE.match(name)
        if not m:
            skipped.append({"issue": num, "title": title, "reason": f"{name} is not a case name"})
            print(f"#{num} {title}: skipped, {name} is not a case name")
            continue
        if name != title and "*" not in name:
            notes.append(f"its case is {name}")
        people = [u["login"] for u in issue.get("assignees") or []] or [issue["user"]["login"]]
        case = {"issue": num, "case": name, "resolution": RESOLUTION[m.group(1)],
                "version": m.group(2), "owner": ", ".join(people), "labels": labels,
                "completed": "completed" in labels}
        found_dates = model_dates(HIST_DIR.format(case=name), HIST_PATTERN)
        if found_dates:
            last, missing = found_dates
            case["modelDate"] = "%04d-%02d-%02d" % last
            if missing:
                # The years with no file, as [[first, last], ...], e.g. [[1854, 1855], [1857, 1857]].
                case["missingYears"] = year_ranges(missing)
        body = issue.get("body") or ""
        # Each tool's output root is the issue's entry, or the default without one. Either may
        # have {case}, {resolution}, {experiment} and {variant} in it, or <case> and so on,
        # filled in from the issue;
        # the experiment is whichever label names an existing directory. A default root counts
        # only where it exists.
        given = {tool: m.group(1) for tool, r in OUTPUT_ROOTS.items() if (m := r.search(body))}
        variant = next((l for l in labels if VARIANT.match(l)), None)
        output = {}
        for tool, default in (("cmip7prep", CMIP7PREP_DIR), ("cmor4cmip7", CMOR4CMIP7_DIR)):
            root = given.get(tool) or default
            if not root:
                continue
            root = re.sub(r"<(case|resolution|experiment|variant)>", r"{\1}", root)
            if "{variant}" in root and not variant:
                continue
            root = (root.replace("{case}", name).replace("{resolution}", case["resolution"])
                    .replace("{variant}", variant or ""))
            places = ([root.replace("{experiment}", l) for l in labels if l != variant]
                      if "{experiment}" in root else [root])
            if d := next((d for d in places if os.path.isdir(d)), None):
                output[tool] = d
            elif tool in given and places:
                output[tool] = places[0]
        if output:
            case["cmorOutput"] = output
        # Problems with the run script are printed with the case's line.
        problems = notes
        if len(script_paths) > 1:
            problems.append("more than one run script: " + ", ".join(script_paths))
        elif script_paths:
            case["runScript"] = script_paths[0]
            if start := run_settings(text):
                # The parent's case name may still have a * for a part only NIRD knows.
                refcase = start.get("refcase", "")
                if parent := issue_of_case.get(refcase) or next(
                        (n for c, n in issue_of_case.items() if "*" in c and fnmatch.fnmatchcase(refcase, c)), None):
                    start["parent"] = parent
                case["start"] = start
        if m := DATA_VERSION.search(body):
            case["dataVersion"] = "v" + m.group(1).lstrip("vV")
        if found := [i for i in cmor_issues if name in i["title"] + "\n" + (i.get("body") or "")]:
            case["cmorIssues"] = []
            for i in found:
                ci = {"number": i["number"], "state": i["state"]}
                if t := CMOR_TAG_VERSION.search(i.get("body") or ""):
                    ci["tagVersion"] = "v" + t.group(1)
                case["cmorIssues"].append(ci)
        versions = {}
        if prep_dir := output.get("cmip7prep"):
            sets = cmor_sets(prep_dir)
            if sets:
                case["cmor"] = sets
            # cmip7-prep writes its CMOR files under cmor/ in its output directory.
            prep_cmor = os.path.join(prep_dir, "cmor")
            if v := cmor_versions(prep_cmor if os.path.isdir(prep_cmor) else prep_dir, labels):
                versions["cmip7prep"] = v
        if "cmor4cmip7" in output:
            ranges = cmor_file_years(output["cmor4cmip7"], labels)
            if ranges:
                case["cmor4cmip7"] = ranges
            if found_problems := cmor_problems(output["cmor4cmip7"], labels):
                case["cmor4cmip7Problems"] = found_problems
            if v := cmor_versions(output["cmor4cmip7"], labels):
                versions["cmor4cmip7"] = v
        if versions:
            case["cmorVersions"] = versions
        kept = earlier.get(num, {})
        storage = case_storage(CASE_DIR.format(case=name), name,
                               prep_dir, output.get("cmor4cmip7"), labels, kept)
        if storage:
            case["storage"] = storage
        # Each case's timing files are in <case>/<case>/timing in its archive.
        timing_dir = (CASE_DIR + "/{case}/timing").format(case=name)
        if os.path.isdir(timing_dir):
            timing, machine = case_timing(timing_dir)
            if timing:
                case["timing"], case["machine"] = timing, machine
        cases.append(case)
        # The line printed for each case gives its latest model date and its start date.
        if "modelDate" in case:
            report = f"at {case['modelDate']}"
            if startdate := case.get("start", {}).get("startdate"):
                report += f"; start date {startdate}"
        elif not script_paths:
            report = "no run script on GitHub"
        else:
            report = "no output on NIRD" if found_dates is False else "no dated files"
        print(f"#{num} {title} [{', '.join(labels) or 'no labels'}]: " + "; ".join([report] + problems))

    # When the progress was written, in NIRD's local time with its time zone, e.g. CET.
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    data = {"updated": now, "repo": REPO, "cases": cases, "skipped": skipped}
    # The page, index.html next to progress.json, built from the spreadsheet, the plan and the
    # template; it reads progress.json when it is opened. It is built before anything is
    # written, so that if it can't be built neither file is updated.
    page = os.path.join(os.path.dirname(os.path.abspath(a.out)), "index.html")
    sheet = {"url": f"{SHEET}/edit?gid={SHEET_TAB}#gid={SHEET_TAB}", "read": now, "file": None}
    try:
        if a.sheet:
            with open(a.sheet, encoding="utf-8") as f:
                sheet_text = f.read()
            sheet["file"] = os.path.basename(a.sheet)
        else:
            sheet_text = fetch_sheet()
        text, _, sims, warnings = build_scheduler.page_text(sheet_text, sheet)
    except (OSError, ValueError) as e:
        raise Failed(f"The page could not be built: {e}") from e
    if not sims:
        raise Failed("The page could not be built: the spreadsheet has no runs in the plan.")

    # Both files are written to temporary files first and then moved into place, so the page
    # never reads a half-written file.
    written = []
    try:
        for path, content in ((a.out, json.dumps(data, indent=1)), (page, text)):
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                f.write(content)
            written.append(path)
    except OSError as e:
        for done in (a.out, page):
            if os.path.exists(done + ".tmp"):
                os.remove(done + ".tmp")
        raise Failed(f"{path} could not be written: {e}") from e
    for path in written:
        os.replace(path + ".tmp", path)
    for w in warnings:
        print("warning:", w)
    print(f"{a.out}: {len(cases)} cases")
    print(f"{page}: {len(sims)} runs")


if __name__ == "__main__":
    try:
        main()
    except Failed as e:
        sys.exit(f"{e}\nNothing was updated: progress.json and the page are as they were.")
    except (OSError, ValueError, http.client.HTTPException) as e:
        sys.exit(f"GitHub, the spreadsheet or NIRD could not be read: {e}\nNothing was updated: progress.json and the page are as they were.")
