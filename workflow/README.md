# Workflow

These files build and feed the NorESM3 CMIP7 Cost Plan and Schedule Tracker,
published at https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/
(`/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/` on NIRD).

## The page

`build_page.sh` builds the page. It runs `build_scheduler.py` with the plan set
in `build_page.sh`: the resolutions, members, years and slots. `build_scheduler.py`
takes the experiments from `noresm3_experiments_decoded.csv`, gives each a
configuration from its `COSTS` table, and writes them into
`scheduler_template.html`. The page reads the runs' progress and timing from
`progress.json` when it loads, so it needs rebuilding only when the plan or the
template changes. To publish it, run on NIRD from this repository's clone:

```bash
git pull
workflow/build_page.sh /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/index.html
```

When a change to the page also changes what `progress.json` holds, run
`nird_progress.py` first.

Run without an argument, it writes `noresm3_cmip7_scheduler.html` in the current
directory. A page opened as a local file can't fetch `progress.json`, so every run
shows as Pending; to see the progress, build a copy of it into the page:

```bash
workflow/build_page.sh preview.html --progress progress.json
```

The page's layout, text and workflow are in `scheduler_template.html`. A
configuration's cost and throughput come from its cases' timing files, through
`progress.json`; the values in `COSTS`, from earlier timing runs, are used only
for a configuration with nothing running yet.

## The case issues

The tracker takes its cases from the issues in this repository, one per case:

- **Title:** the case name and nothing else, e.g.
  `nHistEsmGHGGaxg.LM.nor30b28.008.20261029`. `LM` is ne16pg3_tn14 and `MM` is ne30pg3_tn14; the tracker names runs by them, e.g. `esm-hist LM`.
- **Experiment label:** the CMIP7 experiment, e.g. `esm-hist`, spelt as in the tracker.
- **Variant label:** the ensemble member, e.g. `r1i1p1f1`.
- **Assignee:** whoever runs it; the issue's author if nobody is assigned.
- **`completed`:** add this label when the run has finished.
- **`test`:** add this label to a case that is not a CMIP7 run, to leave it out.
- **`esgf`:** add this label when the data is on ESGF, and the tracker shows it
  after the next run of `nird_progress.py`. A run with several members has a
  row for each, named by its variant, e.g. `1pctCO2 LM r1i1p1f1` to `r3i1p1f1`,
  so each member's issue counts for its own row.

- **Description:** one entry, `- cmor data version:`, with `TBD` until the
  version is decided, which is before CMORization starts, then the version: `v`
  and its date as YYYYMMDD, the `v` optional. `nird_progress.py` reads `TBD` as
  not set.

  ```
  - cmor data version: v20261028
  ```

  The script also reads the entry written as a `### cmor data version` heading
  with the value on the next line. It finds everything else itself: each tool's
  output in its default place (see below), and the case's run script by its issue
  number (see the run scripts below).

  The CMOR data version is the version directory, `vYYYYMMDD`, that both tools write
  the case's years into. cmip7-prep's `--data-version` and cmor4cmip7's version
  must be the same, so that every realm's files for those years are one edition
  of the dataset. `nird_progress.py` records the version directories each tool's
  files for the case are in, and the tracker marks a CMORize column with ⚠ when
  they disagree: a case's cmip7-prep files in a version other than its issue's,
  cmor4cmip7 files in a version no issue of the simulation gives, or years the
  two tools wrote into different versions. Hovering the cell says which.

  The cmip7prep and cmor4cmip7 columns need no label: `nird_progress.py` reads
  the years each tool has CMORized under its output root:

  - **cmip7prep:** `--cmor-dir`, the case's own `.cmor` directory, the one that
    holds cmip7-prep's `completed_steps_*.json` files. Only that directory is
    read, not the ones below it.
  - **cmor4cmip7:** `--cmor4cmip7-dir`, the simulation's variant directory,
    named from the issue's resolution, experiment and variant labels, e.g.
    `/nird/datapeak/NS9034K/.CMIP7/NorESM3-LM/piControl/r1i1p1f1`. Every
    directory below it is read, so every version is, and the years come from the
    time ranges in the names of the files whose name has the issue's experiment
    and variant, e.g. `_piControl_r1i1p1f1_`. A year counts once every variable
    has it, and the tracker counts it once however many issues the simulation
    has.

  Output somewhere else needs an entry giving its root, `- cmip7prep output root:`
  with the case's directory or `- cmor4cmip7 output root:` with the variant
  directory. A cmor4cmip7 root above the model directory would mix the LM and MM
  files of the same experiment and variant.

## The run scripts

Each case's run script is pushed straight to its directory under `scripts/` on
the `CMIP7_Runscripts` branch, which needs write access to the
repository.

- **Directory:** `scripts/<MIP>/<experiment>/`. A case that is not a CMIP7 run, whose issue has the
  `test` label, goes in `scripts/test/`.
- **Name:** `<issue>.<experiment>.<resolution>.<beta>.<variant>.<date>.sh`, the
  experiment and variant from the issue's labels and the rest from the case name:
  `n1850GHGGaxg.LM.nor30b28.011.20261102` gets
  `011.piControl.LM.beta28.r1i1p1f1.20261102.sh`. `nird_progress.py` finds a
  case's script by the issue number its name starts with, so no other script
  may start with it.
- **Push:** in a clone of the repository,

  ```bash
  git switch CMIP7_Runscripts && git pull
  cp /path/to/run_script.sh scripts/DECK/piControl/011.piControl.LM.beta28.r1i1p1f1.20261102.sh
  git add scripts/DECK/piControl/011.piControl.LM.beta28.r1i1p1f1.20261102.sh
  git commit -m "Run script for #11"
  git push
  ```

  The commit message is `Run script for #<case issue>`, e.g. `Run script for #11`.
  Naming the issue makes GitHub list the commit on it. Don't use `Closes #11` or
  `Fixes #11`, as those close the issue.

After the next run of `nird_progress.py`, the tracker links the script after the
case's issue.

`nird_progress.py` also reads how the case started from the script's
`./xmlchange` lines: its `RUN_TYPE`, `RUN_REFCASE`, `RUN_REFDATE` and
`RUN_STARTDATE`, with the script's shell variables, such as `${refcase}`,
filled in. Hovering the case's issue in the tracker shows them, naming the issue
whose title is the `RUN_REFCASE`. A case of the same run and member continues
it, e.g. "Continues #2 (branch at 0171-01-01)", and goes under it in the Issues
column, after an arrow and one step further in for each case it continues. A
case of another experiment branches from
it, e.g. "Branches from #2, piControl LM (hybrid at 0101-01-01, starting
1850-01-01)". Nothing else needs adding to the issue, and GitHub's parent links
are not read.

## Continuations and members

A simulation continued in a new case gets a new issue with the same experiment and
variant labels, and its run script's `RUN_REFCASE` is the earlier case. The
tracker reads the two as one member, taking its progress from the later model
date. Another member of the ensemble gets its own variant, e.g. `r2i1p1f1`, and
its own progress.

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
    --case-dir "/nird/datalake/NS9560K/noresm3/cases/{case}" \
    --cmor-dir "/nird/datalake/NS9560K/noresm3/cases/{case}.cmor" \
    --cmor4cmip7-dir "/nird/datapeak/NS9034K/.CMIP7/NorESM3-{resolution}/{experiment}/{variant}" \
    --timing-dir "/nird/datalake/NS9560K/noresm3/cases/{case}/timing" \
    --timing-dir "/nird/datalake/NS9560K/noresm3/cases/{case}/{case}/timing"
```

- `--dir` is each case's directory, with `{case}` standing for the case name.
- `--case-dir` is each case's archive directory, with `<component>/hist` and
  `rest/`. The script measures the case's output on NIRD in GB per simulated
  year, in four kinds: history, each component's `hist/`; restarts, `rest/`, over
  the years the history covers; time series, the netCDF files in cmip7-prep's
  directory outside `cmor/`; and CMOR, the CMORized files of the case's experiment
  and variant under cmip7-prep's `cmor/` and the cmor4cmip7 root. The years come
  from the model dates in the file names, and the CMOR files count each version's
  years. The Cost plan multiplies each run's rate, or its configuration's, by its
  members and years.
- `--cmor-dir` is each case's cmip7-prep output directory, for a case whose issue
  has no cmip7prep output root. The script reads the
  `completed_steps_<first>-<last>.json` files cmip7-prep writes there. A set of
  years counts once it has every `cmor-` step any of the run's sets has, so a set
  where one realm failed does not count; the range ends at the first year missing.
- `--cmor4cmip7-dir` is each simulation's cmor4cmip7 variant directory, for a
  case whose issue has no cmor4cmip7 output root, with `{resolution}`,
  `{experiment}` and `{variant}` standing for the issue's. The experiment is the
  label that names an existing directory.
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
- `--scripts` reads the run scripts from a `scripts/` directory, e.g. in a
  checkout of the `CMIP7_Runscripts` branch, instead of listing them with
  GitHub's API and fetching them from its raw file server.

It reads GitHub anonymously. The API allows 60 requests an hour, and the script
makes one for each hundred issues and one to list the run scripts; the scripts
themselves come from the raw file server, which is not counted.

It prints one line per issue with its labels, so a missing label or a wrong
directory shows straight away. The page lists the issues it could not place
under the tracker.
