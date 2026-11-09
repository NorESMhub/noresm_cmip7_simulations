# CMIP7 Run Scripts

CMIP7_Runscripts is the default branch you get when you clone this repository. 

The directory structure is `scripts`/`CMIP7 MIP`/`experiment_id`.

Each run script for a NorESM3 CMIP7 experiment belongs in one of the `experiment_id` directories and should have a filename of the form:
```
<Issue number>.<compset>.<Resolution>.<Betaversion>.<Date>.sh
e.g. 009.n1850GhgGaxg.LM.b28.YYYYMMDD.sh
```

## Adding a run script to this repository

The following steps should be followed to add a run script to this repository:

1. Clone the repository (one time)

``` bash
> git clone -b CMIP7_Runscripts https://github.com/NorESMhub/noresm_cmip7_simulations
```

2. Upload a run script to the repository

``` bash
> cd scripts/<MIP>/<Experiment_id>
> cp <your run script> scripts/<MIP>/<Experiment_id>/<Issue>.<compset>.<Resolution>.<Betaversion>.<Date>.sh
> git add scripts/<MIP>/<Experiment_id>/<Issue>.<compset>.<Resolution>.<Betaversion>.<Date>.sh
> git commit -m "<message>"   # with the message:
  ## Run script for # (e.g. Run script for #11. Naming the issue makes GitHub list the commit on it)
> git push origin CMIP7_Runscripts
```

## Structure of the run script
Each run script hould be a bash script (that begins with `#!/bin/bash`) that contains all the commands used to create the experiment:
- The exact `create_newcase` command. Be sure to include the correct `--usermods_dirs` entry.
    - The case directory name must be in the form, `compset.Resolution.NorESMversionBetaversion.Issue.Date`.
- `cd` into the case directory
- Any `./xmlchange` commands run before setup
- The `./case.setup` command
- `(cdir="$(pwd -P)"; cd $(./xmlquery --value SRCROOT); ./describe_version >> ${cdir}/README.case)`
- Any `./xmlchange` commands run after setup but before build
- Any additions to user_nl_xxx namelist files. These **MUST** be documented with bash comments specifying why these are needed.
- `./case.build`
- `./case.submit`

## Elements of the issue tracker for experiments
- Set the relationship: Parent experiment from which the experiment branches off.
- Start year, end year, branch year
- Important for CMORization
  - Set the label for `experiment_id`
  - Set the label for experiment variant (e.g. `r1i1p1f1`)
