# Workflow

These files feed the NorESM3 CMIP7 Cost Plan and Schedule Tracker, published at
https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/
(`/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/` on NIRD).

## `noresm3_cases.csv`

One row per case of a run that has started:

| Column | Meaning |
|---|---|
| `run` | the run's name in the tracker, e.g. `piControl ne16` (2°×2° is ne16) |
| `case` | the case name |
| `version` | the NorESM3 beta, e.g. `b28` |
| `owner` | who runs it |
| `issue` | its issue in this repository, e.g. `#011` |
| `first_year`, `last_year` | the model years the case covers; leave `last_year` blank if none are recorded yet |
| `note` | anything else, e.g. `HF` or where it branches from |

A run continued in a new case gets a second row with the same `run`. Add a row
whenever a case starts, then rebuild and republish the tracker page.

## `nird_progress.py`

Writes `progress.json` next to the published page. The page reads it on load, and
its years done replace the ones from `noresm3_cases.csv`.

For each run it finds the latest model date in its cases' file names, such as
`<case>.cam.i.1930-01-01-00000.nc`, and subtracts the run's start year (the
first case's `first_year`). It only lists directories, so it is quick.

Run it on Olivia, where both the archive and the NIRD datalake are mounted:

```bash
python3 -I workflow/nird_progress.py workflow/noresm3_cases.csv \
    /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json \
    --dir "<archive root>/{case}/atm/hist"
```

- `--dir` is each case's directory, with `{case}` standing for the case name.
- `--nird-dir` is the same for the copy on NIRD; the tracker ticks the NIRD step
  once that copy reaches the end of the run.
- `--completed "piControl ne16"` marks a finished run; repeat it for each one.
- `--pattern` sets which files count (default `*.cam.i.*.nc`).

It prints one line per run, so a wrong directory shows straight away.
