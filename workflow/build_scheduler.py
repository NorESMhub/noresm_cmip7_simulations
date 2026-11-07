"""Build the NorESM3 CMIP7 scheduler page from the experiment sheet.

Reads the experiment table (noresm3_experiments_decoded.csv, decoded from the
DECK/FASTTRACK tab of the experiment sheet), the configuration costs in
noresm3_model_cost.csv and the scheduler template, and writes a page whose
default plan is the selected experiments at each resolution.

Each experiment is assigned a configuration. A configuration whose Compsets
column (in noresm3_model_cost.csv) lists the experiment's compset at that
resolution wins; shell-style wildcards are allowed (N7*EsmGhgGaxg). Otherwise
the required model components and compset decide:
  LAND                          -> land-only
  DCPP activity                 -> DCPP
  AGCM...                       -> AMIP at the chosen resolution
  emission-driven (esm-*, *Esm*) -> ESM at the chosen resolution
  anything else                 -> coupled at the chosen resolution

Usage (build_page.sh runs it with the published plan):
  python3 -I workflow/build_scheduler.py --experiments workflow/noresm3_experiments_decoded.csv \\
      --costs workflow/noresm3_model_cost.csv --template workflow/scheduler_template.html \\
      --out noresm3_cmip7_scheduler.html \\
      --plan "ne16:DECK,Fast Track" --plan "ne30:DECK,ScenarioMIP"

--ensemble N gives every run N members instead of the sheet's Ensemble Members;
--members piControl=1 sets one experiment's members and wins over --ensemble.
--years piControl=600 sets one experiment's years per member.
--running "historical ne16=1" marks one member of a run as already going;
progress (years done) is then entered on the page.
The runs' cases and progress come from progress.json, which
nird_progress.py, next to this script, writes on NIRD from the case
issues and the files there; the published page reads it on load.
--progress progress.json builds a copy into the page, for viewing it where
progress.json can't be fetched (a local file); a fetched one replaces it.
--defer ScenarioMIP keeps those runs in the plan with priority 0, so they are
not scheduled or costed until their priority is set on the page.

A selector lists tiers (DECK, Fast Track) or activities (ScenarioMIP, C4MIP).
With more than one plan, run names carry their resolution.
"""

import argparse
import csv
import fnmatch
import json
import sys

HEADER_KEY = "experiment_id"
START_MARKER = "let DEFAULT_CONFIGS = ["
END_MARKER = "let configs = clone(DEFAULT_CONFIGS);"
NO_PARENT = {"", "-", "obs product"}


def read_experiments(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    for i, row in enumerate(rows):
        if HEADER_KEY in [c.strip() for c in row]:
            header = [c.strip() for c in row]
            return [dict(zip(header, r)) for r in rows[i + 1:] if any(c.strip() for c in r)]
    sys.exit(f"{path}: no header row with {HEADER_KEY}")


def read_costs(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compset_rules(costs):
    """(resolution, pattern, configuration) for every compset listed in the cost table."""
    rules = []
    for c in costs:
        res = (c.get("Resolution") or "").strip()
        for pattern in (c.get("Compsets") or "").split():
            rules.append((res, pattern, c["Configuration"]))
    return rules


def config_name(exp, resolution, rules=()):
    compset_alias = exp.get("Compset Alias", "").strip()
    for res, pattern, name in rules:
        if res == resolution and compset_alias and fnmatch.fnmatchcase(compset_alias, pattern):
            return name
    comps = exp.get("required_model_components", "").upper()
    compset = exp.get("Compset Alias", "")
    name = exp["experiment_id"]
    if comps.startswith("LAND"):
        return "NorESM3 land-only"
    if exp.get("activity_id", "").startswith("DCPP"):
        return "NorESM3 DCPP"
    if comps.startswith("AGCM"):
        return f"NorESM3 AMIP {resolution}"
    if name.startswith("esm-") or "Esm" in compset:
        return f"NorESM3 ESM {resolution}"
    return f"NorESM3 {resolution}"


def matches(exp, selector):
    """An experiment matches when its Tier or its activity_id is in the selector."""
    tier = exp.get("Tier", "").strip()
    activities = [a.strip() for a in exp.get("activity_id", "").split("/")]
    return tier in selector or any(a in selector for a in activities)


def build(experiments, costs, plans, ensemble=None, members=None, years_override=None, deferred=()):
    """plans: list of (resolution, selector) pairs, one per resolution.
    ensemble: members for every run, replacing the sheet's Ensemble Members.
    members: {experiment_id: N}, which wins over both.
    years_override: {experiment_id: years}, replacing min_yrs_per_sim.
    deferred: tiers, activities or experiment_ids whose runs get priority 0, so
    they stay in the plan but are not scheduled or costed."""
    members = members or {}
    years_override = years_override or {}
    configs = []
    for i, c in enumerate(costs, 1):
        configs.append({
            "id": f"c{i}",
            "name": c["Configuration"],
            "costPerYear": number(c.get("Cost / sim-yr (core-hr)")),
            "throughput": number(c.get("Throughput (SYPD)")),
        })
    cfg_id = {c["name"]: c["id"] for c in configs}
    rules = compset_rules(costs)
    label = len(plans) > 1

    warnings = []
    sims = []
    for resolution, selector in plans:
        chosen = [e for e in experiments if matches(e, selector)]
        selected = []
        for e in chosen:
            if config_name(e, resolution, rules) in cfg_id:
                selected.append(e)
            else:
                warnings.append(f"{e['experiment_id']} ({resolution}): configuration "
                                f"{config_name(e, resolution, rules)!r} is not in the cost table; run left out")
        first = len(sims) + 1
        sim_id = {e["experiment_id"]: f"r{first + i}" for i, e in enumerate(selected)}
        for e in selected:
            name = e["experiment_id"]
            parent = e.get("branches from", "").strip()
            depends = []
            if parent.lower() not in NO_PARENT:
                if parent in sim_id:
                    depends.append(sim_id[parent])
                else:
                    warnings.append(f"{name} ({resolution}): parent {parent!r} is not selected; no dependency")
            years = years_override.get(name, number(e.get("min_yrs_per_sim")))
            if years is None:
                warnings.append(f"{name} ({resolution}): no min_yrs_per_sim; years set to 0")
            if name in members:
                ens = members[name]
            elif ensemble is not None:
                ens = ensemble
            else:
                ens = number(e.get("Ensemble Members"))
            tier = e.get("Tier", "").strip()
            activity = e.get("activity_id", "").split("/")[0].strip()
            sims.append({
                "id": sim_id[name],
                "name": f"{name} {resolution}" if label else name,
                # The page matches a case's issue to its run by experiment label and resolution,
                # and counts years done from the start year.
                "experiment": name,
                "resolution": resolution,
                "startYear": int(number(e.get("start_year")) or 1),
                "dependsOn": depends,
                "years": int(years) if years else 0,
                "ensemble": int(ens) if ens is not None else None,
                "configId": cfg_id[config_name(e, resolution, rules)],
                "priority": 0 if matches(e, deferred) or name in deferred else 1 if tier == "DECK" else 2,
                "status": "pending",
                "yearsCompleted": 0,
                "steps": [],
                # The DECK's activity_id is CMIP; label it DECK so it reads as its own group.
                "mip": "DECK" if tier == "DECK" or activity in ("", "CMIP") else activity,
                "cmipPriority": tier,
                "amip": "Yes" if e.get("required_model_components", "").upper().startswith("AGCM") else "No",
            })
    return configs, sims, warnings


def literal(items):
    return "\n".join("    " + json.dumps(x, ensure_ascii=False) + "," for x in items)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--experiments", required=True)
    p.add_argument("--costs", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--plan", action="append", required=True, metavar="RES:SELECTOR",
                   help='resolution and the tiers or activities to run at it, e.g. "ne30:DECK,ScenarioMIP"; repeatable')
    p.add_argument("--slots", type=int, default=5)
    p.add_argument("--ensemble", type=int, help="ensemble members for every run, replacing the sheet's column")
    p.add_argument("--members", action="append", default=[], metavar="EXP=N",
                   help="members for one experiment at every resolution, e.g. piControl=1; repeatable")
    p.add_argument("--years", action="append", default=[], metavar="EXP=N",
                   help="years per member for one experiment at every resolution, e.g. piControl=600; repeatable")
    p.add_argument("--running", action="append", default=[], metavar="NAME=N",
                   help='members of a run already going, e.g. "historical ne16=1"; repeatable')
    p.add_argument("--progress", help="a progress.json to build into the page; see the docstring")
    p.add_argument("--defer", action="append", default=[], metavar="SELECTOR",
                   help="tier, activity or experiment_id to keep in the plan but not schedule yet "
                        "(priority 0), e.g. ScenarioMIP; repeatable")
    a = p.parse_args()

    members = {}
    for spec in a.members:
        exp, _, n = spec.partition("=")
        members[exp.strip()] = int(n)
    years = {}
    for spec in a.years:
        exp, _, n = spec.partition("=")
        years[exp.strip()] = int(n)
    plans = []
    for spec in a.plan:
        res, _, sel = spec.partition(":")
        plans.append((res.strip(), [s.strip() for s in sel.split(",") if s.strip()]))
    configs, sims, warnings = build(read_experiments(a.experiments), read_costs(a.costs), plans, a.ensemble, members, years, a.defer)
    by_name = {s["name"]: s for s in sims}
    for spec in a.running:
        name, _, n = spec.partition("=")
        name = name.strip()
        if name not in by_name:
            sys.exit(f"--running {name!r}: no such run (names look like 'historical ne16')")
        by_name[name]["status"] = "in-progress"
        by_name[name]["membersRunning"] = int(n or 1)
    progress = None
    if a.progress:
        with open(a.progress, encoding="utf-8") as f:
            progress = json.load(f)
    pinned = sum(s.get("membersRunning", 0) for s in sims if s["status"] == "in-progress")
    if pinned > a.slots:
        sys.exit(f"{pinned} members are running but --slots is {a.slots}; raise --slots")

    with open(a.template, encoding="utf-8") as f:
        page = f.read()
    s, e = page.find(START_MARKER), page.find(END_MARKER)
    if s < 0 or e < 0:
        sys.exit("template has no default-data block")
    block = (START_MARKER + "\n" + literal(configs) + "\n  ];\n"
             + "  let DEFAULT_SIMS = [\n" + literal(sims) + "\n  ];\n"
             + f"  let DEFAULT_SLOTS = {a.slots};\n"
             + f"  let DEFAULT_PROGRESS = {json.dumps(progress, ensure_ascii=False)};\n"
             + '  let DEFAULT_COST_UNIT = "core-hr";\n\n  ')
    page = page[:s] + block + page[e:]
    page = page.replace('id="slotsInput" min="1" max="24" step="1" value="5"',
                        f'id="slotsInput" min="1" max="24" step="1" value="{a.slots}"')
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)

    for w in warnings:
        print("warning:", w)
    by_cfg = {}
    for r in sims:
        by_cfg.setdefault(r["configId"], []).append(r["name"])
    for c in configs:
        if c["id"] in by_cfg:
            print(f"{c['name']}: {len(by_cfg[c['id']])} runs")
    print(f"{a.out}: {len(sims)} runs, {len(configs)} configurations")


if __name__ == "__main__":
    main()
