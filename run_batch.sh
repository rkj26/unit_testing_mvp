#!/usr/bin/env bash
# The 2x2x2 batch: gen_strategy x code-aware-search x self-critique, 50 tasks, 10 runs each.
# One tmux session per cell, each under its own caffeinate. Cache stays ON so --run-id resume is
# cheap; the monitor prompts changed on 2026-08-09 so nothing stale can hit.
#
#   bash run_batch.sh            # launch all eight
#   bash run_batch.sh --status   # progress, warnings, throttling
#   bash run_batch.sh r1 r5      # launch a subset
#
# Cells are ordered so each adds ONE thing to the one before it: stopping early still leaves a
# coherent series rather than a half-filled grid.

set -o pipefail
cd "$(dirname "$0")" || exit 1

PREFIX=b1
MAX_CONN=4
EXEC_WORKERS=1
RUNS=${RUNS:-10}
SEED=300
CELLS=(r1 r5 r2 r6 r3 r7 r4 r8)
NICENESS=${NICENESS:-10}
# Unit budget derives from call timeout. Code-aware adds a sandboxed search plus a per-candidate
# gate to every unit; 120s starves blind_t (36 timeouts) while u_plans absorbs it (3). Matched here
# so the timeout cannot be confounded with the treatment.
T_TIMEOUT=${T_TIMEOUT:-420}
DOCKER_IMAGE=${DOCKER_IMAGE:-python:3.12-slim}

T="openai-api/azureai/DeepSeek-V3.2"
U="openai-api/azureai/gpt-5.4"
COMMON=(--domain apps --dataset apps_pool_hard.json --runs "$RUNS" --seed "$SEED"
        --no-progress --t-model "$T" --t-reasoning low --t-timeout "$T_TIMEOUT"
        --max-conn "$MAX_CONN" --exec-workers "$EXEC_WORKERS"
        --pbt-isolation docker --docker-image "$DOCKER_IMAGE")
UPLAN=(--u-model "$U" --u-reasoning high --gen-strategy u_plans_t_writes)
BLIND=(--gen-strategy blind_t)

cell_args() {
  case "$1" in
    r1) echo "${BLIND[@]}" ;;
    r2) echo "${BLIND[@]} --code-aware-search" ;;
    r3) echo "${UPLAN[@]}" ;;
    r4) echo "${UPLAN[@]} --code-aware-search" ;;
    r5) echo "${BLIND[@]} --self-critique" ;;
    r6) echo "${BLIND[@]} --self-critique --code-aware-search" ;;
    r7) echo "${UPLAN[@]} --self-critique" ;;
    r8) echo "${UPLAN[@]} --self-critique --code-aware-search" ;;
    *)  echo "unknown cell $1" >&2; return 1 ;;
  esac
}

if [ "$1" = "--status" ]; then
  for c in "${CELLS[@]}"; do
    id="${PREFIX}-${c}"; log="runs_${id}.log"; d="runs/${id}"
    done_runs=$(ls -d "$d"/run_*/metrics.json 2>/dev/null | wc -l | tr -d ' ')
    printf '%-8s %-9s runs=%-6s warns=%-5s %s\n' "$c" \
      "$(tmux has-session -t "$id" 2>/dev/null && echo running || echo stopped)" \
      "${done_runs}/${RUNS}" \
      "$(grep -c '\[warn\]' "$log" 2>/dev/null | tr -d ' ')" \
      "$(grep -oE '^\[[0-9:]+\] run [0-9]+: [a-z]+' "$log" 2>/dev/null | tail -1)"
  done
  echo "--- throttling across all cells ---"
  grep -ihE "rate.?limit|429|too many requests|throttl" runs_${PREFIX}-*.log 2>/dev/null | wc -l
  exit 0
fi

[ $# -gt 0 ] && CELLS=("$@")

for c in "${CELLS[@]}"; do
  args=$(cell_args "$c") || exit 1
  id="${PREFIX}-${c}"; log="runs_${id}.log"
  tmux kill-session -t "$id" 2>/dev/null
  tmux new-session -d -s "$id" \
    "nice -n ${NICENESS} caffeinate -dims .venv/bin/python run.py --run-id '$id' $(printf '%q ' "${COMMON[@]}") $args 2>&1 | tee -a '$log'; echo \"=== $id exit=\${PIPESTATUS[0]} \$(date -u +%FT%TZ) ===\" >> '$log'"
  echo "launched $id  ($args)"
done

echo "watch: bash run_batch.sh --status"
