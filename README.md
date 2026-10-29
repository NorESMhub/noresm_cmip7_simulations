# CMIP7 Run Scripts

Each file in this branch should contain the run script for a NorESM3 CMIP7 experiment.

The filename should be of the form, `run_<compset>.<Resolution>.<noresmversion><Betaversion>.<Issue>.<Date>.sh` and should be a bash script (that begins with `#!/bin/bash`) that contains all the commands used to create the experiment:
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

