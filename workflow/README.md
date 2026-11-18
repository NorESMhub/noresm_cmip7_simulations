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

- **The experiments spreadsheet**

  The DECK_FASTTRACK tab of the
  [NorESM3 CMIP7 experiments spreadsheet](https://docs.google.com/spreadsheets/d/1PZQHmOHVENJeCqwSfk4wfp8okQXw60Bv/edit?gid=13331701#gid=13331701)
  contains each experiment's tier, activity, compset, required model
  components, number of members and number of years. `nird_progress.py`
  downloads the tab as CSV each time it runs, so a change to the spreadsheet
  reaches the web page at the next run, without being reviewed. The spreadsheet
  must stay readable by anyone with the link, since NIRD reads it without
  signing in.

- **`scheduler_template.html`**

  This file contains the web page's layout, text and JavaScript.

- **The case issues**

  The case issues are the issues in
  [NorESMhub/noresm_cmip7_simulations](https://github.com/NorESMhub/noresm_cmip7_simulations/issues).
  Each issue corresponds to one case.

- **The run scripts**

  The run scripts are in the
  [scripts](https://github.com/NorESMhub/noresm_cmip7_simulations/tree/CMIP7_Runscripts/scripts)
  sub-directory directory on this repository's `CMIP7_Runscripts`
  branch. There is one run script for each case, and the name of each
  run script starts with the number of its case issue.

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

- The scripts need Python 3.8 or later and only use the Python standard library.
- The scripts are run on NIRD, in the repository's clone at
  `/projects/NS9560K/www/diagnostics/noresm/noresm_cmip7_simulations`.
- The user running the scripts needs read access to
  `/nird/datalake/NS9560K/noresm3/cases` and `/nird/datapeak/NS9034K/.CMIP7`,
  along with write access to
  `/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning`.
- The scripts need internet access to `api.github.com`,
  `raw.githubusercontent.com` and `docs.google.com`. GitHub and the spreadsheet
  are read anonymously, without a token.

## Scripts

| File | What it does | When it is run |
|---|---|---|
| `nird_progress.py` | It reads the GitHub issues, the run scripts, the case directories on NIRD and the CMORization directories, and writes `progress.json`. It then downloads the spreadsheet and builds `index.html` from it with `build_scheduler.py`. If anything can't be read or built, it updates neither file. | It is run on NIRD whenever the tracker is to be updated: after new output reaches NIRD, or after the spreadsheet changes. The current plan is to run this as a daily cron job on NIRD. |
| `build_scheduler.py` | It holds the plan and the cost table, and the code that builds `index.html` from the spreadsheet and `scheduler_template.html`. | It is not run on its own: `nird_progress.py` uses it to build the page. |
| `scheduler_template.html` | It holds the web page's layout, text and JavaScript, and becomes `index.html`. Its JavaScript reads `progress.json` and fills in the tracker. | Its JavaScript runs in the browser each time the web page is opened. |

### `build_scheduler.py`

`build_scheduler.py` is not run on its own. It holds the plan and the cost
table, which are changed by editing them there, and the code `nird_progress.py`
uses to build `index.html` in five steps.

1. It reads the experiments from the spreadsheet's tab, which
   `nird_progress.py` has downloaded. Rows above the header row, the one with
   an `experiment_id` column, are notes and are skipped.
2. It chooses which experiments are run at each resolution. `PLAN`, near the
   top of `build_scheduler.py`, lists for each resolution the tiers from the
   spreadsheet's Tier column, and for each tier either all its experiments or
   only those of some of its activities:

   ```python
   PLAN = {
       "LM": {"DECK": "all", "Fast Track": "all"},
       "MM": {"DECK": "all", "Fast Track": ["ScenarioMIP"]},
   }
   ```

   That is, every DECK and Fast Track experiment at LM, and at MM every DECK
   experiment and, of the Fast Track, only ScenarioMIP. The plan is changed by
   editing it there and running `nird_progress.py` again.
3. It gives each run an estimated cost and throughput. The estimates come from
   the `COSTS` table in `build_scheduler.py`, which has one estimate for each
   model configuration, e.g. `NorESM3 LM` for the coupled model at LM
   resolution. Each estimate lists the compsets it applies to, e.g.
   `N1850GhgGaxg`, which is the compset of piControl. A run whose compset is not
   listed is given the estimate for the coupled, ESM or AMIP configuration at
   its resolution. A configuration whose cost and throughput aren't known yet,
   such as land-only or DCPP, is listed in `COSTS` without them. Its runs are
   tracked as usual and marked in the Cost plan as not yet costed, until timing
   files supply the numbers. A run whose configuration is not in `COSTS` at all
   is left out of the web page, and `nird_progress.py` prints a warning about it.
4. It takes the number of members and years of each run from the spreadsheet.
5. It writes the runs and their estimates into a copy of
   `scheduler_template.html`, which `nird_progress.py` then writes as
   `index.html`.

### `nird_progress.py`

`nird_progress.py` generates `progress.json`, and then the web page,
`index.html`, in the same directory. On NIRD it is always run with no
arguments, as follows. The paths on NIRD that it reads and writes are set at the
top of the script.

```bash
python3 -I workflow/nird_progress.py
```

The web page shows how far each case has run, how much of its output has been
CMORized, what it costs and how much storage it needs. The script collects this
information for every case issue, as described in the sections below.

The script updates `progress.json` and `index.html` only if it has read
everything and built the page without an error. If GitHub can't be read, a run
script can't be read, the spreadsheet can't be downloaded, the spreadsheet has
no runs in the plan, or the page can't be built, the script stops with a
message saying why, and both files stay as they were. It builds the page before
writing anything, writes both files to temporary files, and then moves them into
place, so that the web page never reads a half-written file. For each
issue, the script also prints one line with the issue's labels, the case's
latest model date and its start date. A case with no output yet is marked
"no output on NIRD", or "no run script on GitHub" if its run script is missing
too.

#### Arguments

The script's arguments are needed only for testing a change without touching the
published page, or for measuring the output again. Each can be combined with the
others.

| Argument | What it does |
| --- | --- |
| `out` | Writes `progress.json` here instead of to the published page's directory. `index.html` is written next to it. Use it to try a change to the template, the plan or the script. |
| `--scripts DIR` | Reads the run scripts from `DIR`, a `scripts/` directory such as in a local checkout of the `CMIP7_Runscripts` branch, instead of from GitHub. Use it to check a run script before pushing it. |
| `--issues FILE` | Reads the case issues from `FILE`, a JSON file in the form GitHub's API returns them, instead of from GitHub. Use it when GitHub can't be reached. |
| `--sheet FILE` | Reads the experiments from `FILE`, the spreadsheet's DECK_FASTTRACK tab saved as CSV, instead of downloading it. Use it to try a change to the spreadsheet before making it, or when the spreadsheet can't be reached. The page then says which file it was built from, in bold red. |
| `--remeasure-storage` | Measures every case's storage on NIRD again. Without it, a case's storage is taken from the last `progress.json` once it covers enough years. Use it after output on NIRD has been deleted or moved. The cost and throughput are not affected: they are read from the timing files on every run. |

For example, the following command writes a test copy of the page to
`$HOME/tracker_test`, which must exist, from a local checkout of the run scripts.

```bash
python3 -I workflow/nird_progress.py $HOME/tracker_test/progress.json --scripts ../CMIP7_Runscripts/scripts
```

#### Reading GitHub

The script reads every issue in `NorESMhub/noresm_cmip7_simulations` and in
`NorESMhub/CMIP7_CMOR-Publish`. It also reads each case's run script from the
[`CMIP7_Runscripts`](https://github.com/NorESMhub/noresm_cmip7_simulations/tree/CMIP7_Runscripts/scripts)
branch of `NorESMhub/noresm_cmip7_simulations`, below `scripts/`.

GitHub allows 60 anonymous requests an hour from one address, and every user on
NIRD shares that address. The script needs one request for each hundred issues
in each repository, and one for the list of run scripts: three while each
repository has fewer than a hundred issues. The run scripts
themselves come from GitHub's raw file server, which is not counted. If the limit
has been used up, by this script or by others on NIRD, the script stops, says
when it can be run again, and leaves `progress.json` and the page as they were.

#### The case and its owner

The script takes each case's name from its run script, not from the issue's
title: it is the last part of the path the script gives `create_newcase
--case`, with the script's shell variables filled in. The case's directory on
NIRD has this name. A part of the name the script only knows when it runs, such
as the date from `$(date +%Y%m%d)`, is taken from the one directory on NIRD
whose name fits; if several fit, the latest is used and the script says so.
Until the case has a directory on NIRD, the unknown part is shown as `*`.

The issue's title is therefore only a label, and changing it changes nothing.
An issue with no run script on the `CMIP7_Runscripts` branch yet, or whose run
script names no case, falls back to its title as the case name. When the title
and the case name differ, the script's line for the issue gives the case name.

Issues with the `test` label are not CMIP7 runs and are left out. An issue's
title may have only letters, digits, `.`, `-` and `_`. Any other title, such as
one with a space for a run that is not set up yet, is a note, and the issue is
left out as soon as the issues are read, before anything from it is used. An issue whose case name is not of the form
`compset.LM.nor30b28...` is also left out. For each issue left out, the script
prints a line saying why.

The web page shows a case once its issue has an experiment label for a run in
the plan and a variant label, e.g. `historical` and `r2i1p1f1`. Until then, the
issue is listed under "Not shown" below the tracker, together with the issues
whose case names are not of that form.

The case's owner is the person assigned to the issue. If several people are
assigned, all of them are owners, and the tracker shows them all, separated by
commas. If nobody is assigned, the owner is the person who opened the issue. A
run's owners are those of all its cases, each named once.

#### How far the case has run

The web page counts the years a case has simulated from the latest date in the
names of its history files, e.g. `<case>.cam.i.1930-01-01-00000.nc` in the
case's `atm/hist` directory. A year between the first and the last of these
files that has no file of its own is recorded as missing, and the web page shows
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
finished. It also writes a log for each step it runs, finished or not, in
`logs/<first>-<last>/`. The script records the `cmor-` steps each file lists,
and the `cmor-` steps that have a log but are not listed, which failed or are
still running.

A set of years counts as CMORized once it has finished every `cmor-` step that
any set of the same simulation has run. So a set in which one realm failed does
not count, even if that realm failed in every set. A realm that cmip7-prep has
never run, in any set, is not noticed. The script also records which version
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
least five years is kept from the previous `progress.json`. To measure every case
again, for example after output on NIRD has been deleted or moved, or after a
change to the history output, run the script once with `--remeasure-storage`. These
sizes are the storage only: the cost comes from the timing files, which are read
again on every run.

#### Timing

The web page replaces the estimated cost and throughput with measured values
once a case has timing files. The script reads every `noresm_timing.*` file in
`/nird/datalake/NS9560K/noresm3/cases/<case>/<case>/timing`, gzipped or not.
Each file comes from one job, and gives the machine, the cost in core-hours per
simulated year, the throughput in simulated years per day, and the date the job
ended.

The timing files give the cost in pe-hours, which are core-hours on both Betzy
and Olivia. CIME counts every core of each node a job uses, whether or not the
job runs on all of them: 128 cores per node on Betzy and 256 on Olivia. The
tracker calls them core-hours throughout. The cores of the two machines differ,
so a case's cost on Betzy is not its cost on Olivia, and the page keeps the two
apart.

The script averages the case's jobs for each machine, giving a job that
simulated more years more weight. It also records the machine of the latest job, because the web page
costs the rest of the run on that machine. If the PE layout changes during a
run, the average mixes the old and new layouts, weighted by the years run with
each. The page plots each job's cost and throughput, so a change of layout shows
there.

### `scheduler_template.html`

The JavaScript in the web page combines the runs in `index.html` with the cases
in `progress.json` each time the page is opened. The top of the tracker says
when `nird_progress.py` last wrote `progress.json`, in NIRD's local time, or in
bold red why the progress could not be read. The line under it says when the
spreadsheet the plan was built from was downloaded, or, in bold red, the file
given with `--sheet` instead. The tracker first shows only
the runs that are waiting to start, in progress or completed, and a button
above the tables shows every run in the plan.

- A run's cases are the issues with the run's experiment label and resolution.
  The cases are grouped into members by their variant label.
- A member's years done are counted from its start to the latest model date of
  its cases. The start is the earliest `RUN_STARTDATE` in the run scripts of the
  member's cases, or the spreadsheet's start year if none of its run scripts can
  be read. When the two years differ, a bold red `⚠ start date error` appears
  under the case whose run script sets the start; hovering over it shows both
  years. A case whose run script is missing, or sets no
  `RUN_STARTDATE`, is followed by a bold red `⚠ run script missing` or
  `⚠ no RUN_STARTDATE` chip. A member counted from the spreadsheet's start year
  has a bold red note saying so in the Progress column. A member whose issue has the `completed` label
  counts as finished.
- A run's years done are the mean of its members' years done, over the members
  that have at least one case issue. A member with an issue but no output on
  NIRD yet counts as 0 years, and a finished member as all the run's years. A
  member is counted up to the run's years, so one that has run longer doesn't
  raise the mean. Members of the ensemble that have no issue yet are left out:
  the tracker shows how many members are going, e.g. `2 of 3 members going`,
  and the Cost plan costs those members from the mean and the rest from the
  start.
- A case that continues an earlier case of the same member is shown underneath
  that case in the Issues column.
- The cmip7prep chip is dashed until at least one of the case's sets of years
  counts. The cmor4cmip7 chip is red when there is a problem in the case's
  years.
- Each run is costed from measured timings once there are any, separately for
  Olivia and Betzy. A run whose cases have timing files uses its own measured
  cost and throughput. Any other run uses the mean over all the cases of its
  configuration that have timing files. A configuration with no timing files at
  all keeps its estimate from `COSTS` in `build_scheduler.py`. A run is costed on
  the machine its latest case ran on, and on Olivia until its cases have timing
  files.
- The output sizes give the storage estimate for each run in the Cost plan.
