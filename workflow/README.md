# Workflow

These files feed the NorESM3 CMIP7 Cost Plan and Schedule Tracker, published at
https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/
(`/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/` on NIRD).

## The case issues

The tracker takes its cases from the issues in this repository, one per case:

- **Title:** the case name and nothing else, e.g.
  `nHistEsmGHGGaxg.LM.nor30b28.008.20261029`. `LM` is ne16 and `MM` is ne30.
- **Labels:** the CMIP7 experiment, e.g. `esm-hist`, spelt as in the tracker.
- **Assignee:** whoever runs it; the issue's author if nobody is assigned.
- **`completed`:** add this label when the run has finished.
- **`test`:** add this label to a case that is not a CMIP7 run, to leave it out.

A run continued in a new case gets a second issue with the same experiment label.

## `nird_progress.py`

Writes `progress.json` next to the published page, which reads it on load. For
every case issue it records the latest model date in the case's file names, such
as `<case>.cam.i.1930-01-01-00000.nc`, and the sets of years cmip7-prep has
CMORized. The page groups the cases into its runs and counts the years from each
run's start year.

Run it on NIRD, from this repository's clone:

```bash
python3 -I workflow/nird_progress.py \
    /nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/progress.json \
    --dir "/nird/datalake/NS9560K/noresm3/cases/{case}/atm/hist" \
    --cmor-dir "/nird/datalake/NS9560K/noresm3/cases/{case}.cmor"
```

- `--dir` is each case's directory, with `{case}` standing for the case name.
- `--cmor-dir` is each case's cmip7-prep output directory. The script reads the
  `completed_steps_<first>-<last>.json` files cmip7-prep writes there. A set of
  years counts once it has every `cmor-` step any of the run's sets has, so a set
  where one realm failed does not count; the range ends at the first year missing.
- `--pattern` sets which files count (default `*.cam.i.*.nc`).
- `--issues` reads the issues from a saved copy of the GitHub API's answer
  instead of fetching them.

It prints one line per issue with its labels, so a missing label or a wrong
directory shows straight away. The page lists the issues it could not place
under the tracker.
