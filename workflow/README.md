# Workflow

These files build and feed the NorESM3 CMIP7 Cost Plan and Schedule Tracker,
published at https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/
(`/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/` on NIRD).

## The page

`build_page.sh` builds the page with the published plan. It runs
`build_scheduler.py`, which fills `scheduler_template.html` in from
`noresm3_experiments_decoded.csv` (the experiments) and its own `COSTS` table
(each configuration's cost, throughput and compsets). To publish it, run on NIRD
from this repository's clone:

```bash
git pull
workflow/build_page.sh /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/index.html
```

Run without an argument, it writes `noresm3_cmip7_scheduler.html` in the current
directory. A page opened as a local file can't fetch `progress.json`, so every run
shows as Pending; to see the progress, build a copy of it into the page:

```bash
workflow/build_page.sh preview.html --progress progress.json
```

The plan (resolutions, members, years, slots) is set in `build_page.sh`, and the
page's layout, text and workflow in `scheduler_template.html`. A configuration's
cost and throughput come from its cases' timing files, through `progress.json`;
`COSTS` in `build_scheduler.py` holds the values from earlier timing runs, which
the page uses for a configuration with nothing running yet, and which compsets
belong to each configuration.

## The case issues

The tracker takes its cases from the issues in this repository, one per case:

- **Title:** the case name and nothing else, e.g.
  `nHistEsmGHGGaxg.LM.nor30b28.008.20261029`. `LM` is ne16 and `MM` is ne30.
- **Experiment label:** the CMIP7 experiment, e.g. `esm-hist`, spelt as in the tracker.
- **Variant label:** the ensemble member, e.g. `r1i1p1f1`.
- **Assignee:** whoever runs it; the issue's author if nobody is assigned.
- **`completed`:** add this label when the run has finished.
- **`test`:** add this label to a case that is not a CMIP7 run, to leave it out.
- **Step labels:** add a step's label when the step is done, and the tracker ticks
  its column after the next run of `nird_progress.py`. A run with several members
  needs the label on an issue of each; until then the column shows how many have
  it, e.g. `1/3`.

  | Label | Step |
  |---|---|
  | `run-qa` | QA: the run's QA checklist is done |
  | `cmip7prep-qa` | CMORize: the cmip7-prep output is validated |
  | `cmor4cmip7-qa` | CMORize: the cmor4cmip7 output is QA'd |
  | `esgf` | Publish: the data is on ESGF |

- **Description:** a heading for the run script, the case it continues, if any,
  and each tool's output root, with the link, issue or directory on the line after
  it. Add each root as its tool starts on the case:

  ```
  ### Run script
  https://github.com/NorESMhub/noresm_cmip7_simulations/blob/CMIP7_Runscripts/scripts/piControl/011.n1850GHGGaxg.LM.b28.20261102.sh

  ### Continues
  #2

  ### cmip7prep output root
  /nird/datalake/NS9560K/noresm3/cases/<case>.cmor

  ### cmor4cmip7 output root
  /nird/datapeak/NS9034K/CMIP7
  ```

  The cmip7prep and cmor4cmip7 columns need no label: `nird_progress.py` reads
  the years each tool has CMORized under its root. It reads cmip7-prep's
  `completed_steps_*.json` files, and the time ranges in the names of cmor4cmip7's
  files for the case, those whose name has its experiment and variant, e.g.
  `_piControl_r1i1p1f1_`. A year counts once every variable has it. Without a
  cmip7prep output root it uses `--cmor-dir`.

## The run scripts

Each case's run script is pushed straight to its experiment's directory under
`scripts/` on the `CMIP7_Runscripts` branch, which needs write access to the
repository.

- **Directory:** `scripts/<experiment>/`, named after the issue's experiment label,
  e.g. `scripts/piControl/`. Every experiment label has one. A new label needs its
  own directory, with an empty `.gitkeep` file so that git keeps it while it is empty.
- **Name:** `<issue>.<compset>.<resolution>.<beta>.<date>.sh`, each part copied
  from the case name: `n1850GHGGaxg.LM.nor30b28.011.20261102` gets
  `011.n1850GHGGaxg.LM.b28.20261102.sh`.
- **Push:** from a clone of the repository,

  ```bash
  git switch CMIP7_Runscripts && git pull
  cp /path/to/run_script.sh scripts/piControl/011.n1850GHGGaxg.LM.b28.20261102.sh
  git add scripts/piControl/011.n1850GHGGaxg.LM.b28.20261102.sh
  git commit -m "Run script for #11"
  git push
  ```

  Without a clone, open the experiment's directory under `scripts/` on GitHub, use
  **Add file → Upload files** and choose **Commit directly to the CMIP7_Runscripts
  branch**.
- **Commit message:** `Run script for #11`, with the case's issue number. GitHub
  then shows the commit on the issue. Don't write `Closes #11` or `Fixes #11`:
  either closes the issue.
- **Issue:** add the script's link to the issue's description under the heading
  `### Run script`, e.g.
  `https://github.com/NorESMhub/noresm_cmip7_simulations/blob/CMIP7_Runscripts/scripts/piControl/011.n1850GHGGaxg.LM.b28.20261102.sh`.

## Continuations and members

A simulation continued in a new case gets a new issue with the same experiment and
variant labels, and `#<earlier issue>` under the heading `### Continues` in its
description. The tracker reads the two as one member, taking its progress from the
later model date; the heading is for readers, as the labels are enough for the
tracker. Another member of the ensemble gets its own variant, e.g.
`r2i1p1f1`, and its own progress.

## `nird_progress.py`

Writes `progress.json` next to the published page, which reads it on load. For
every case issue it records the latest model date in the case's file names, such
as `<case>.cam.i.1930-01-01-00000.nc`, the sets of years cmip7-prep has
CMORized, and the case's cost and throughput from its timing files. The page groups the cases into runs by experiment and resolution, and
into members by variant, and counts the years from each run's start year. A run's
years done are the mean over its members.

Run it on NIRD, from this repository's clone:

```bash
python3 -I workflow/nird_progress.py \
    /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json \
    --dir "/nird/datalake/NS9560K/noresm3/cases/{case}/atm/hist" \
    --cmor-dir "/nird/datalake/NS9560K/noresm3/cases/{case}.cmor" \
    --timing-dir "/nird/datalake/NS9560K/noresm3/cases/{case}/timing" \
    --timing-dir "/nird/datalake/NS9560K/noresm3/cases/{case}/{case}/timing"
```

- `--dir` is each case's directory, with `{case}` standing for the case name.
- `--cmor-dir` is each case's cmip7-prep output directory, for a case whose issue
  has no cmip7prep output root. The script reads the
  `completed_steps_<first>-<last>.json` files cmip7-prep writes there. A set of
  years counts once it has every `cmor-` step any of the run's sets has, so a set
  where one realm failed does not count; the range ends at the first year missing.
- `--timing-dir` is each case's timing directory. The script reads the Machine,
  Model Cost (pe-hours per simulated year) and Model Throughput (simulated years
  per day) of every `noresm_timing.*` file there, one per job, gzipped or not. For
  each machine it averages the case's jobs there, weighting each job by the years
  it simulated, and it records the machine of the latest job and each job's end
  date, cost and throughput. The page costs each run on the machine its latest case
  ran on, with the run's own timing there when it has any and its configuration's
  otherwise; a configuration's value is the same mean over all its runs' cases, and
  the value it was built with until it has one. Under Timings by experiment the page
  lists the timing of each run with a case issue, a line for each machine (Olivia in
  green, Betzy in orange), and a run's job count opens charts of its SYPD and cost
  job by job. Some cases keep their timing files one level down, in a
  directory named after the case, so `--timing-dir` is given once for each layout;
  the first that exists is read.
- `--pattern` sets which files count (default `*.cam.i.*.nc`).
- `--issues` reads the issues from a saved copy of the GitHub API's answer
  instead of fetching them.

It reads GitHub anonymously, which allows 60 requests an hour; it makes one for
each hundred issues.

It prints one line per issue with its labels, so a missing label or a wrong
directory shows straight away. The page lists the issues it could not place
under the tracker.
