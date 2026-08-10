#!/usr/bin/env bash
# Run A — does instrumentation repair change what we measured about PBT?
# Pre-registered in reports/2026-08-08-instrumentation-repair.md
#
# Everything here is held identical to runs/uplanhard50-tlow-uhigh except the Phase 1 code changes.
# caffeinate keeps the machine awake; run.py also asserts its own on darwin. Launch under tmux so
# a closed terminal cannot take the run with it:
#
#   tmux new-session -d -s runA 'bash run_a.sh'
#   tmux attach -t runA          # watch
#   tail -f runs_uplanhard50-fixed.log
#
# --run-id resumes: re-running this script after a kill costs at most one in-flight call.

set -o pipefail
cd "$(dirname "$0")" || exit 1

RUN_ID=uplanhard50-fixed
LOG="runs_${RUN_ID}.log"

caffeinate -dims .venv/bin/python run.py \
  --domain apps \
  --dataset apps_pool_hard.json \
  --run-id "$RUN_ID" \
  --seed 300 \
  --runs 5 \
  --t-model openai-api/azureai/DeepSeek-V3.2 --t-reasoning low \
  --u-model openai-api/azureai/gpt-5.4 --u-reasoning high \
  --gen-strategy u_plans_t_writes \
  --no-progress 2>&1 | tee -a "$LOG"

status=${PIPESTATUS[0]}
echo "run_a.sh finished, exit=${status}" | tee -a "$LOG"
exit "$status"
