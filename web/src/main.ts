const jobspyBlock = `cd ~/Projects/sisyphus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/search_profile.template.yaml config/search_profile.local.yaml
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 -c "from lib.search_profile import load_profile; load_profile('$JOB_SEARCH_PROFILE')"

# daily
source .venv/bin/activate
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"`;

const fitBlock = `cd ~/Projects/sisyphus
./corpofit --interactive
# or: python3 fit/scripts/corpofit.py --interactive`;

const jobspyEl = document.getElementById("jobspy-commands");
const fitEl = document.getElementById("fit-commands");

if (jobspyEl) jobspyEl.textContent = jobspyBlock;
if (fitEl) fitEl.textContent = fitBlock;
