# Workflow

This directory contains the code that generates the
[NorESM3 CMIP7 Simulation Tracker Dashboard](https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/index.html).
This README describes what the code does. The steps that people running
simulations need to follow are described on the web page itself, in the
[Workflow](https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/index.html#workflow)
section.

The tracker consists of the following two files on NIRD.

```
/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/index.html
/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json
```

`index.html` is the generated web page and contains the list of runs, along
with each run's experiment, resolution, number of members and number of years
in the simulation. `progress.json` contains the progress of each run and is
read by the web page each time the page is opened in a browser.

## Inputs and requirements

### Input files

- **`noresm3_experiments_decoded.csv`**

  This file is a copy of the DECK_FASTTRACK tab of the
  [NorESM3 CMIP7 experiments spreadsheet](https://docs.google.com/spreadsheets/d/1qps0xZDkEy1M3GZgjt9mAqAFj2NUK_xd/edit?gid=13331701#gid=13331701).
  It contains each experiment's tier, activity, compset, required model
  components, number of members and number of years. When the spreadsheet
  changes, the tab is exported as a CSV file and saved over this file.

- **`scheduler_template.html`**

  This file contains the web page's layout, text and JavaScript.

- **The case issues**

  The case issues are the issues in
  [NorESMhub/noresm_cmip7_simulations](https://github.com/NorESMhub/noresm_cmip7_simulations/issues).
  Each issue corresponds to one case.

- **The run scripts**

  The run scripts are in the `scripts/` directory on this repository's
  `CMIP7_Runscripts` branch. There is one run script for each case, and the
  name of each run script starts with the number of its case issue.

- **The CMORization issues**

  The CMORization issues are the issues in
  [NorESMhub/CMIP7_CMOR-Publish](https://github.com/NorESMhub/CMIP7_CMOR-Publish/issues).

- **The model output**

  The model output of each case is archived on NIRD in
  `/nird/datalake/NS9560K/noresm3/cases/<case>`. This directory contains the
  case's history files, restart files and timing files.

- **The cmip7-prep output**

  cmip7-prep writes the CMORized atmosphere, land, sea ice and land ice output
  of each case to `/nird/datalake/NS9560K/noresm3/cases/<case>.cmor`.

- **The cmor4cmip7 output**

  cmor4cmip7 writes the CMORized ocean and ocean biogeochemistry output of each
  simulation to
  `/nird/datapeak/NS9034K/.CMIP7/NorESM3-<resolution>/<experiment>/<variant>`.
  When a simulation is continued in a new case, cmor4cmip7 writes the output of
  all of the simulation's cases to this one directory.

### Requirements

- The scripts need Python 3 and use only the Python standard library.
- The scripts are run on NIRD, in the repository's clone at
  `/projects/NS9560K/www/diagnostics/noresm/noresm_cmip7_simulations`.
- The user running the scripts needs read access to
  `/nird/datalake/NS9560K/noresm3/cases` and `/nird/datapeak/NS9034K/.CMIP7`,
  along with write access to
  `/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning`.
- The scripts need internet access to `api.github.com` and
  `raw.githubusercontent.com`. GitHub is read anonymously, without a token.

## Scripts

| Script | What it does | When it is run |
|---|---|---|
| `build_page.sh` | It generates `index.html` by running `build_scheduler.py`. | It is run whenever the spreadsheet copy, the template or the plan changes. |
| `build_scheduler.py` | It combines the experiments, the plan and the template into `index.html`. | It is run only by `build_page.sh`. |
| `nird_progress.py` | It generates `progress.json` from GitHub and the case files on NIRD. | It is run whenever the progress needs to be updated. |
| `scheduler_template.html` | It contains the JavaScript that combines `index.html` and `progress.json` in the browser. | Its JavaScript is run each time the web page is opened. |

### `build_page.sh`

`build_page.sh` generates the published web page. It is run on NIRD with the
following command.

```bash
workflow/build_page.sh /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/index.html
```

The script writes the web page to the file it is given, by running
`build_scheduler.py`.

### `build_scheduler.py`

`build_scheduler.py` generates `index.html` in five steps.

1. It reads the experiments from `noresm3_experiments_decoded.csv`.
2. It chooses which experiments are run at each resolution. The plan at the top
   of `build_scheduler.py` lists the tiers and activities for each resolution,
   e.g. the DECK and Fast Track experiments at LM resolution. The plan is
   changed by editing it there and running `build_page.sh` again.
3. It gives each run an estimated cost and throughput. The estimates come from
   the `COSTS` table in `build_scheduler.py`, which has one estimate for each
   model configuration, e.g. `NorESM3 LM` for the coupled model at LM
   resolution. Each estimate lists the compsets it applies to, e.g.
   `N1850GhgGaxg`, which is the compset of piControl. A run whose compset is not
   listed is given the estimate for the coupled, ESM or AMIP configuration at
   its resolution. There is no estimate yet for land-only or DCPP experiments,
   so they are left out of the web page.
4. It takes the number of members and years of each run from the spreadsheet.
5. It writes the runs and their estimates into a copy of
   `scheduler_template.html`, which becomes `index.html`.

On the web page, these estimates are used only until real timings exist. Once
cases of a configuration have timing files on NIRD, the web page replaces the
estimate with the mean of those cases' measured timings, worked out machine by
machine.

### `nird_progress.py`

`nird_progress.py` generates `progress.json` in the same directory as the
published web page. It is run on NIRD with the following command.

```bash
python3 -I workflow/nird_progress.py
```

The web page shows how far each case has run, how much of its output has been
CMORized, what it costs and how much storage it needs. The script collects this
information for every case issue, as described in the sections below.

The script first writes `progress.json` to a temporary file and then moves it
into place, so that the web page never reads a half-written file. For each
issue, the script also prints one line with the issue's labels and what it
found, so that a missing label or a missing directory is easy to spot.

#### Reading GitHub

The script reads every issue in `NorESMhub/noresm_cmip7_simulations` and in
`NorESMhub/CMIP7_CMOR-Publish`. It also reads each case's run script from the
`CMIP7_Runscripts` branch.

GitHub allows 60 anonymous requests an hour. The script needs only a few,
because it fetches the issues a hundred at a time and the run scripts come from
GitHub's raw file server, which is not counted.

#### The case and its owner

Each case issue is titled with the case name, e.g.
`nHistEsmGHGGaxg.LM.nor30b28.r1i1p1f1.008.20261029`. Issues with the `test`
label are not CMIP7 runs and are left out. An issue whose title is not a case
name is listed under the tracker on the web page, so that it can be corrected.

The case's owner is the person assigned to the issue. If nobody is assigned,
the owner is the person who opened the issue.

#### How far the case has run

The web page counts the years a case has simulated from the latest date in the
names of its history files, e.g. `<case>.cam.i.1930-01-01-00000.nc` in the
case's `atm/hist` directory. A year between the first and the last of these
files that has no file of its own is recorded as missing. The missing years are
listed in the line that the script prints for the case, and the web page shows
a red `gap` chip after the case's issue.

#### How the case started

The web page shows whether a case is a new start, continues an earlier case, or
branches from another experiment. The script finds this out from the case's run
script, whose name starts with the issue number. It reads `RUN_TYPE`,
`RUN_REFCASE`, `RUN_REFDATE` and `RUN_STARTDATE` from the script's
`./xmlchange` lines. If `RUN_REFCASE` is the name of another case, that case's
issue is recorded as the parent.

#### The CMORization issues

The web page links each case to the CMORization issues that name it. The
script records the number and state of each of these issues, along with the
cmor tag version given in it.

#### cmip7-prep output

The web page shows how many years of each case cmip7-prep has CMORized.
cmip7-prep writes a `completed_steps_<first>-<last>.json` file in the case's
`.cmor` directory for each set of years it works on, listing the steps that
finished. The script records the steps in each of these files.

A set of years counts as CMORized only once every realm has finished, so a set
in which one realm failed does not count. The script also records which version
directories, `vYYYYMMDD`, the CMORized files are in, along with the years in
each version directory.

#### cmor4cmip7 output

The web page shows how many years of each simulation cmor4cmip7 has CMORized,
and whether anything is wrong with the files. The script reads the variable and
the years of each file from the file's name, e.g.
`tos_tavg-u-hxy-sea_…_185001-185912.nc`.

A year counts as CMORized once every variable has a file for it. Two kinds of
problems are recorded.

- A variable has missing years if other variables have files for years that it
  has no file for.
- A variable has overlaps if two of its files in the same version directory
  cover the same time.

All the cases of a continued simulation share one cmor4cmip7 directory. The web
page therefore gives each case only the years from its own `RUN_STARTDATE` up to
the next case's `RUN_STARTDATE`, along with the problems in those years.

#### Output size

The Cost plan estimates the storage each run will need. The script therefore
measures how much space each case already takes up on NIRD for each simulated
year, in the following four parts.

- The history files are in each component's `hist/` directory.
- The restart files are in `rest/`.
- The time series are the netCDF files that cmip7-prep writes outside `cmor/`.
- The CMORized files are those written by cmip7-prep and cmor4cmip7.

The Cost plan multiplies these sizes by each run's number of members and years.
Measuring takes a long time, so a size that has already been measured over at
least five years is kept from the previous `progress.json`.

#### Timing

The web page replaces the estimated cost and throughput with measured values
once a case has timing files. The script reads every `noresm_timing.*` file in
`/nird/datalake/NS9560K/noresm3/cases/<case>/timing`, gzipped or not. Each file
comes from one job, and gives the machine, the cost in pe-hours per simulated
year, the throughput in simulated years per day, and the date the job ended.

The script averages the case's jobs for each machine, giving a job that
simulated more years more weight. It also records the machine of the latest job, because the web page
costs the rest of the run on that machine.

### `scheduler_template.html`

The JavaScript in the web page combines the runs in `index.html` with the cases
in `progress.json` each time the page is opened.

- A run's cases are the issues with the run's experiment label and resolution.
  The cases are grouped into members by their variant label.
- A member's years done are counted from the run's start year to the latest
  model date of its cases. A member whose issue has the `completed` label counts
  as finished. A run's years done are the mean over its members.
- A case that continues an earlier case of the same member is shown underneath
  that case in the Issues column.
- The cmip7prep chip is dashed until at least one of the case's sets of years
  counts. The cmor4cmip7 chip is red when there is a problem in the case's
  years.
- Each configuration's estimated cost and throughput are replaced with the mean
  of its cases' measured timings.
- The output sizes give the storage estimate for each run in the Cost plan.
