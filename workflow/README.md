# Workflow

These files feed the NorESM3 CMIP7 Cost Plan and Schedule Tracker, published at
https://ns9560k.web.sigma2.no/datalake/diagnostics/noresm/cmip7_planning/
(`/nird/datalake/NS9560K/www/diagnostics/noresm/cmip7_planning/` on NIRD).

## The case issues

The tracker takes its cases from the issues in this repository, one per case:

- **Title:** the case name and nothing else, e.g.
  `nHistEsmGHGGaxg.LM.nor30b28.008.20261029`. `LM` is ne16 and `MM` is ne30.
- **Experiment label:** the CMIP7 experiment, e.g. `esm-hist`, spelt as in the tracker.
- **Variant label:** the ensemble member, e.g. `r1i1p1f1`.
- **Assignee:** whoever runs it; the issue's author if nobody is assigned.
- **`completed`:** add this label when the run has finished.
- **`test`:** add this label to a case that is not a CMIP7 run, to leave it out.

## The run scripts

Each case's run script is pushed straight to `scripts/` on the `CMIP7_Runscripts`
branch, which needs write access to the repository.

- **Name:** `<issue>.<compset>.<resolution>.<beta>.<date>.sh`, each part copied
  from the case name: `n1850GHGGaxg.LM.nor30b28.011.20261102` gets
  `011.n1850GHGGaxg.LM.b28.20261102.sh`.
- **Push:** from a clone of the repository,

  ```bash
  git switch CMIP7_Runscripts && git pull
  cp /path/to/run_script.sh scripts/011.n1850GHGGaxg.LM.b28.20261102.sh
  git add scripts/011.n1850GHGGaxg.LM.b28.20261102.sh
  git commit -m "Run script for #11"
  git push
  ```

  Without a clone, use **Add file → Upload files** in `scripts/` on GitHub and
  choose **Commit directly to the CMIP7_Runscripts branch**.
- **Commit message:** `Run script for #11`, with the case's issue number. GitHub
  then shows the commit on the issue. Don't write `Closes #11` or `Fixes #11`:
  either closes the issue.
- **Issue:** add a line with the script's link to the issue's description, e.g.
  `Run script: https://github.com/NorESMhub/noresm_cmip7_simulations/blob/CMIP7_Runscripts/scripts/011.n1850GHGGaxg.LM.b28.20261102.sh`.

## Continuations and members

A simulation continued in a new case gets a new issue with the same experiment and
variant labels; the tracker reads the two as one member, taking its progress from
the later model date. Another member of the ensemble gets its own variant, e.g.
`r2i1p1f1`, and its own progress.

## `nird_progress.py`

Writes `progress.json` next to the published page, which reads it on load. For
every case issue it records the latest model date in the case's file names, such
as `<case>.cam.i.1930-01-01-00000.nc`, and the sets of years cmip7-prep has
CMORized. The page groups the cases into runs by experiment and resolution, and
into members by variant, and counts the years from each run's start year. A run's
years done are the mean over its members.

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

It reads GitHub anonymously, which allows 60 requests an hour; it makes one for
each hundred issues.

It prints one line per issue with its labels, so a missing label or a wrong
directory shows straight away. The page lists the issues it could not place
under the tracker.
