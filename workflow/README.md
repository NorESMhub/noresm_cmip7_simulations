# Workflow

This directory contains the code that generates the
[NorESM3 CMIP7 Cost Plan and Schedule Tracker](https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/index.html).
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
| `build_page.sh` | It generates `index.html` by running `build_scheduler.py` with the plan. | It is run whenever the spreadsheet copy, the template or the plan changes. |
| `build_scheduler.py` | It combines the experiments, the plan and the template into `index.html`. | It is run only by `build_page.sh`. |
| `nird_progress.py` | It generates `progress.json` from GitHub and the case files on NIRD. | It is run whenever the progress needs to be updated. |
| `scheduler_template.html` | It contains the JavaScript that combines `index.html` and `progress.json` in the browser. | Its JavaScript is run each time the web page is opened. |

### `build_page.sh`

`build_page.sh` generates the published web page. It is run on NIRD with the
following command.

```bash
workflow/build_page.sh /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/index.html
```

The script contains the plan, which is the set of runs along with the number of
members and years of each run. The script passes the plan to
`build_scheduler.py` as options. The plan is changed by editing `build_page.sh` and running it again.

### `build_scheduler.py`

`build_scheduler.py` generates `index.html` in five steps.

1. It reads the experiments from `noresm3_experiments_decoded.csv`.
2. It selects the experiments in the tiers or activities that the plan lists
   for each resolution and makes each of them a run at that resolution.
3. It assigns each run a model configuration. The configurations are listed in
   the `COSTS` table in `build_scheduler.py`. Each configuration, e.g.
   `NorESM3 ESM LM`, has a cost per simulated year, a throughput and a list of
   compsets. A run is assigned the configuration whose list contains the
   experiment's compset at the run's resolution. If no list contains the
   compset, the configuration is chosen from the experiment's required model
   components, e.g. an AGCM experiment is assigned the AMIP configuration. A
   run whose configuration is not in `COSTS` is left out, and a warning is
   printed.
4. It sets the number of members and years of each run. These are taken from
   the spreadsheet unless the plan gives them.
5. It replaces the default data in a copy of `scheduler_template.html` with the
   configurations and runs, and writes the result to `index.html`.

The `COSTS` values are estimates from early timing runs. Once a configuration's
cases have timing files, the web page replaces these estimates with the measured
values in `progress.json`.

### `nird_progress.py`

`nird_progress.py` generates `progress.json` in the same directory as the
published web page. It is run on NIRD with the following command.

```bash
python3 -I workflow/nird_progress.py
```

For every case issue, the script reads the following information.

- It reads the issue's title and labels, the case's run script, and the
  CMORization issues that name the case from GitHub.
- It reads the model date, which is the latest date in the names of the case's
  files, e.g. `<case>.cam.i.1930-01-01-00000.nc`. The web page uses this date
  to count the number of years that the case has simulated.
- It reads the CMORized years from the cmip7-prep and cmor4cmip7 output
  directories.
- It reads the cost and throughput from the case's `noresm_timing.*` files.
  There is one timing file for each job.
- It measures the output size, which is the number of GB per simulated year
  that the case's history files, restart files, cmip7-prep time series and
  CMORized files take up on NIRD. The Cost plan multiplies these sizes by each
  run's number of members and years.

The script first writes `progress.json` to a temporary file and then moves it
into place, so that the web page never reads a half-written file. The sections
below describe each step in more detail.

#### Reading GitHub

The script reads every issue in `NorESMhub/noresm_cmip7_simulations` and in
`NorESMhub/CMIP7_CMOR-Publish`. It then lists the run scripts in the `scripts/`
directory on the `CMIP7_Runscripts` branch and reads each case's script from
GitHub's raw file server.

GitHub allows 60 anonymous requests an hour. The script makes one request for
every hundred issues in each repository, along with one request to list the run
scripts. Requests to the raw file server do not count towards this limit.

#### What it does for each case issue

1. It leaves out issues with the `test` label.
2. It reads the case name from the issue title. A title that does not match
   `<compset>.<LM|MM>.nor30b<beta>.…` is listed as skipped and is shown under
   the tracker on the web page.
3. It takes the case's owner from the issue's assignees. If nobody is assigned,
   it takes the owner from the issue's author.
4. It finds the latest model date in the names of the `*.cam.i.*.nc` files in
   the case's `atm/hist` directory.
5. It finds the run script whose name starts with the issue number. It then
   reads `RUN_TYPE`, `RUN_REFCASE`, `RUN_REFDATE` and `RUN_STARTDATE` from the
   script's `./xmlchange` lines, filling in the values of the script's shell
   variables. If `RUN_REFCASE` is the title of another issue, that issue is
   recorded as the case's parent.
6. It records the CMORization issues whose title or body contains the case
   name, along with each issue's state and the cmor tag version given in it.
7. It reads the cmip7-prep output.
8. It reads the cmor4cmip7 output.
9. It measures the size of the case's output on NIRD.
10. It reads the case's timing files.

For each issue, the script prints one line with the issue's labels and what it
found.

#### cmip7-prep output

cmip7-prep CMORizes the atmosphere, land, sea ice and land ice output. Its
output for each case is in the case's own directory,
`/nird/datalake/NS9560K/noresm3/cases/<case>.cmor`.

- The script reads the `completed_steps_<first>-<last>.json` files in that
  directory, but not those in the directories below it. Each file corresponds
  to one set of years, and the script records the `cmor-` steps that each file
  lists.
- The script also records the version directories, `vYYYYMMDD`, that contain
  the case's CMOR files under `cmor/`, along with the years in each version
  directory.

The web page decides which sets of years count. A set counts once it lists
every `cmor-` step that is listed by any set of the simulation. A set in which
one realm failed therefore does not count.

#### cmor4cmip7 output

cmor4cmip7 CMORizes the ocean and ocean biogeochemistry output. Its output for
a whole simulation is in one variant directory, e.g.
`/nird/datapeak/NS9034K/.CMIP7/NorESM3-LM/piControl/r1i1p1f1`. The name of this
directory is made from the issue's resolution, along with its experiment and
variant labels.

- The script reads every file below the variant directory whose name contains
  the issue's experiment and variant, e.g. `_piControl_r1i1p1f1_`. It takes
  each file's variable and time range from the file's name, e.g.
  `tos_tavg-u-hxy-sea_…_185001-185912.nc`.
- It records the years for which every variable has a file.
- It records two kinds of problems. A variable has missing years if it has no
  file for years that other variables have files for. A variable has overlaps
  if two of its files in the same version directory cover the same time.
- It records the version directories that contain the files, along with the
  years in each version directory.

The case issues of a continued simulation share the same variant directory.
The web page assigns each case the years from its `RUN_STARTDATE` to the year
before the next case's `RUN_STARTDATE`. It then shows only the years and
problems that fall within the case's years.

#### Output size

The script measures the number of GB per simulated year that each case takes up
on NIRD. The size is split into the following four parts.

- The history size is the size of the files in each component's `hist/`
  directory.
- The restart size is the size of the files in `rest/` over the years covered
  by the history files.
- The time series size is the size of the netCDF files in cmip7-prep's
  directory outside `cmor/`.
- The CMOR size is the size of each tool's CMORized files, counting the years
  in each version directory.

A part that has already been measured over at least five years is copied from
the previous `progress.json` rather than measured again.

#### Timing

The script reads every `noresm_timing.*` file in the case's `timing` directory,
whether the file is gzipped or not. Each file corresponds to one job. It gives
the machine, the cost in pe-hours per simulated year, the throughput in
simulated years per day, and the date the job ended.

For each machine, the script averages the case's jobs, weighting each job by
the number of years it simulated. It also records each job's date, cost and
throughput, along with the machine of the latest job.

### `scheduler_template.html`

The JavaScript in the web page does the following each time the page is opened.

- It groups the cases into runs by experiment and resolution, and into members
  by their variant label.
- It counts the number of years that each member has simulated, from the run's
  start year to the latest model date of the member's cases. A member with the
  `completed` label counts as finished. The number of years that a run has
  simulated is the mean over its members.
- It shows a case that continues another case underneath that case in the
  Issues column. A case continues another case if its `RUN_REFCASE` is a case of
  the same run and member.
- It works out each case's cmip7prep and cmor4cmip7 chips, as described above.
  The cmip7prep chip is dashed when none of the case's sets of years counts. The
  cmor4cmip7 chip is red when there is a problem with the case's years.
- It replaces each configuration's estimated cost and throughput from `COSTS`
  with the mean of its cases' timings. It then calculates the cost of each run
  with the timings of the machine that the run's latest case ran on.
- It uses the output sizes to estimate the storage needed by each run in the
  Cost plan.
