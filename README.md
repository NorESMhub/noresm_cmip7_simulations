# CMIP7 Run Scripts

Each file in this branch should contain the run script for a NorESM3 CMIP7 experiment.

Directory list is organized by CMIP7 `experiment_id`.

The run script name should include a corresponding issue tracking number, that describes the experiment and links to CMORized output and diagnostics.

## Adding a run script to this repository

The following steps should be followed to add a run script to this repository:

1. Clone the repository (one time)

``` bash
git clone https://github.com/NorESMhub/noresm_cmip7_simulations
```

2. Upload a run script to the repository

``` bash
git switch CMIP7_Runscripts
## copy the script into its directory under its name;
cp <script dir> scripts/<MIP>/
git add <the script>
git commit -m "<message"   # with the message:
## Run script for # (e.g. Run script for #11. Naming the issue makes GitHub list the commit on it)
git push
```

## Structure of the run script

The filename should be of the form,

```
<Issue>.<compset>.<Resolution>.<Betaversion>.<Date>.sh
e.g. 009.n1850GhgGaxg.LM.b28.YYYYMMDD.sh
```
and should be a bash script (that begins with `#!/bin/bash`) that contains all the commands used to create the experiment:
- Clone and setup of the source code used:
    - The `git clone` command. This can include `-b <tag name>`.
    - `cd` into the the clone directory
    - `git checkout <tag name>` unless included on the `git clone` line
    - `./bin/git-fleximod update`
- The exact `create_newcase` command. Be sure to include the correct `--usermods_dirs` entry.
    - The case directory name must be in the form, `compset.Resolution.noresmversionBetaversion.Issue.Date`.
- `cd` into the case directory
- Any `./xmlchange` commands run before setup
- The `./case.setup` command
- `(cdir="$(pwd -P)"; cd $(./xmlquery --value SRCROOT); ./describe_version >> ${cdir}/README.case)`
- Any `./xmlchange` commands run after setup but before build
- Any additions to user_nl_xxx namelist files. These **MUST** be documented with bash comments specifying why these are needed.
- `./case.build`
- `./case.submit`

## Elements of the issue tracker for experiments

- Set Relationship: Parent experiment from which the experiment branches off.
- Start year, end year, branch year
- Important for CMORization
  - Set label label for `experiment_id`
  - Set label for experiment variant (e.g. `r1i1p1f1`)
