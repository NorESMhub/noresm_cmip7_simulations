#!/bin/bash
set -e

module purge
module load NRIS/Login
module load Python/3.12.3-GCCcore-13.3.0 

# Machine-specific things
ovrwrt=""  # true if you want to overwrite . Not added at the moment...
startdir=$(pwd)
execscr=$0 
project='nn9560k'

# Check for project:
if ! groups | grep -q "${project}"; then
    echo "You are not a member of ${project}, specify another one, check with cost or dusage commands"
    echo "Aborting..."
    exit 1
fi

machine=$(hostname -f | grep -oP '\.?[0-9]*\.\K[^.]*' | head -n 1)
echo "${machine}"
if [[ "${machine}" == "betzy" ]]; then
    workpath=${USERWORK}
elif [[ "${machine}" == "olivia" ]]; then
    workpath="/cluster/work/projects/${project}/${USER}"
else
    echo "Unrecognized machine ${machine}"
    echo "Aborting..."
    exit 1
fi

# On olivia, you might not have this directory right away
if [[ ! -d "${workpath}" && "${machine}" == "olivia" ]]; then
    mkdir -p "${workpath}"
    chmod go+r "${workpath}/"
fi

# Make source code live in work. If you want to keep it forever, change this to "/cluster/projects/${project}/${USER}/srcs"
srcs="${workpath}/srcs"
echo "Source code will go into ${srcs}"
if [[ ! -d "${srcs}" ]]; then
    mkdir -p "${srcs}"
    echo "made srcs"
fi

# Set path to cases
casesdir="/cluster/projects/${project}/${USER}/NorESM/cases" 
if [[ ! -d "${casesdir}" ]]; then
    mkdir -p "${casesdir}"
    echo "made ${casesdir}"
fi

# Get python version
pver=$(python --version 2>&1 | grep -oP 'Python\s\K.*')
IFS="." read -r -a pva <<< "${pver}"
pvma="${pva[0]}"
pvmi="${pva[1]}"
pybad=""
if [ "${pvma}" -lt "3" ]; then
    pybad="true"
elif [ "${pvmi}" -lt "10" ]; then
    pybad="true"
fi
echo "Python version is bad: ${pybad}"
if [[ "${pybad}" ]]; then
    echo "Loading modules:"
    if [[ "${machine}" == "betzy" ]]; then
        module --force purge
        module load StdEnv Python/3.14.2-GCCcore-15.2.0
    else # we have already checked for the machines
        module --force purge
        module load init-NRIS EESSI/2026.06 Python/3.14.2-GCCcore-15.2.0
    fi
    module list
    python --version
fi

# NorESM source-code settings:
noresm_remote="NorESMhub"
noresm_ver="noresm3_0_beta27"
echo "Noresm version: ${noresm_ver}"
noresm_mv=$(echo "${noresm_ver}" | grep -oP 'noresm[0-3]')
echo "Noresm major version: ${noresm_mv}"
if [[ "${noresm_mv}" != "noresm3" && "${noresm_mv}" != "noresm2" ]]; then
    echo "Unrecognized major version of noresm (tag, major version): ${noresm_ver}, ${noresm_mv}"
    echo "Aborting..."
    exit 2
fi

noresm_dir="${srcs}/${noresm_ver}"
if [[ -d "${noresm_dir}" ]]; then
    cd "${noresm_dir}"
    tmp=$(git describe)
    if [[ "${tmp}" != "${noresm_ver}" ]]; then
        echo "${noresm_dir} exists, but tag ${tmp} is not what is requested: ${noresm_ver}"
        echo "Aborting..."
        exit 3
    fi
    cd "${startdir}"
else
    echo "Cloning out ${noresm_ver} into ${noresm_dir}"
    cd "${srcs}"
    git clone "https://github.com/${noresm_remote}/NorESM" "${noresm_ver}"
    cd "${noresm_ver}"
    git checkout "${noresm_ver}"
    if [[ "${noresm_mv}" == "noresm3" ]]; then
        ./bin/git-fleximod update
    elif [[ "${noresm_mv}" == "noresm2" ]]; then
        ./manage_externals/checkout_externals
    fi
    cd "${startdir}"
fi

# Case settings
resolution="ne16pg3_tn14_ais8gris4" 
casename="n1850GHGGaxg.LM.nor30b27.002.$(date +"%Y%m%d")" 
casepath="${casesdir}/${casename}"
compset="1850_CAM70%LT%NORESM%GHGCAMoslo_CLM60%FATES-NCFB%NORESM_CICE_BLOM%HYB%ECO_MOSART_CISM2%AIS-NOEVOLVE%GRIS-EVOLVE_SWAV_SESP"
refcase="n1850GaxgGHG.LM.nor30b25.528.20260928"
refyear="1701"

if [[ -d "${casepath}" ]]; then
    echo "${casepath} exists, set overwrite to true"
    exit 4
fi

cd "${srcs}/${noresm_ver}/cime/scripts"
./create_newcase --case "${casepath}" --compset "${compset}" --res "${resolution}" \
    --project "${project}" --machine "${machine}" --compiler intel --run-unsupported \
    --user-mods-dir "${noresm_dir}/cime_config/usermods_dirs/cmip7_historybaseGhg" \
    --queue cmip7 # PLEASE NOTE Only for simulations running on reserved nodes!

cd "${casepath}"
./xmlchange NTASKS_OCN=500   #Default in beta28
./xmlchange RUN_TYPE=hybrid
./xmlchange RUN_STARTDATE=0001-01-01
./xmlchange RUN_REFCASE="${refcase}"
./xmlchange RUN_REFDATE="${refyear}-01-01"
# You do not need this line for hybrid run
./xmlchange DRV_RESTART_POINTER="rpointer.cpl.${refyear}-01-01-00000"
./xmlchange GET_REFCASE=TRUE # this one is because we are copying files later into RUNDIR
./xmlchange RUN_REFDIR=/cluster/work/projects/nn9560k/mvertens/archive/${refcase}/rest/${refyear}-01-01-00000/
./xmlchange STOP_OPTION=nyears
./xmlchange STOP_N=10
./xmlchange REST_N=5
./xmlchange REST_OPTION=nyears
./xmlchange RESUBMIT=10 # if you want to run 20 days in 10 days chunks this should be 1.
./xmlchange --subgroup case.run JOB_WALLCLOCK_TIME=16:40:00
# For a long run set this to 01:20:00
./xmlchange --subgroup case.st_archive JOB_WALLCLOCK_TIME=01:30:00
# For a long run set this to 06:20:00
./xmlchange --subgroup case.compress JOB_WALLCLOCK_TIME=04:20:00
./case.setup

# Changes to user_nl_* files go here . these settings will be default in beta26

#CICE updates manually copied from https://github.com/NorESMhub/NorESM_CICE/pull/32/changes
cat <<EOF >> user_nl_cice 
f_siflswdbot       = 'md'
f_sisnmass         = 'md'
f_sispeed          = 'md'
f_siflfwbot        = 'm'
f_siflfwdrain      = 'm'
f_fswabs            = 'x'
f_fresh_ai         = 'x'
f_icedir           = 'x'
f_apeff_ai         = 'x'
f_apond            = 'm'
f_hpond_ai         = 'x'
f_ipond_ai         = 'x'
f_alvl             = 'x'
f_vlvl             = 'x'
f_ardg             = 'm'
f_vrdg             = 'm'
f_rsnwn            = 'x'
f_aicen            = 'm'
f_smassice         = 'm'
f_smassliq         = 'm'
f_rhos_cmp         = 'm'
f_rhos_cnt         = 'm'
f_rsnw             = 'm'
f_rhos_cmp         = 'm'
f_rhos_cnt         = 'm'
EOF

cat <<EOF >> user_nl_cpl
ocn2glc_coupling = .true.
glc_renormalize_smb='on'
EOF

cat <<EOF >> user_nl_cism
which_ho_powerlaw_c = 2
which_ho_babc = 9
calving_init = 0
submarine_melt = 3
EOF


## NOTE!!! These settings are just used for the start of piControl
## REMOVE FOR OTHER SIMULATIONS
cat <<EOF >> user_nl_cism_ais
cisminputfile='/cluster/projects/nn9560k/mdeb/init_spin_511/i1850GAxgGHG.LM.nor3_0b24.511.20260829.cism.ais.r.0041-01-01-00000.nc'
restart=1
EOF

cat <<EOF >> user_nl_cism_gris
cisminputfile='/cluster/projects/nn9560k/mdeb/init_spin_511/relax_i1850GAxgGHG.LM.nor3_0b24.511.20260829.cism.gris.r.0501-01-01-00000.nc'
restart=1
EOF

./pelayout
./preview_namelists
./check_input_data

# Update README.case with source code information:
if [[ "${noresm_mv}" == "noresm3" ]]; then
    cd "$(./xmlquery --value SRCROOT)"
    gdout=$(git describe)
    gsout=$(git status)
    gfmout=$(./bin/git-fleximod status)
    cd "${casepath}"
    echo "${gdout}" >> README.case
    echo "${gsout}" >> README.case
    echo "${gfmout}" >> README.case
fi

# Here should come: ./case.build and ./case.submit
cd "${casepath}"
./case.build
#./case.submit
