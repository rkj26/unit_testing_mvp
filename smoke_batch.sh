#!/usr/bin/env bash
# Pre-flight smoke for the 2x2x2 batch: 2 tasks, 2 runs, live models, all eight cells IN PARALLEL.
# Exercises what mock cannot — a real provider, a real harness clock — and answers the question the
# scale batch depends on: does eight-wide parallelism rate-limit the endpoint?
# The inspect cache is OFF: a cached cell replays a prior completion and tests nothing.
#
#   bash smoke_batch.sh              # launches 8 tmux sessions, returns immediately
#   bash smoke_batch.sh --status     # progress + rate-limit check
#
# 16 cores here, so 8 runs x MAX_CONN network + EXEC_WORKERS harness threads each is the envelope.
# MAX_CONN is deliberately below the per-run default of 12: eight of those is 96 concurrent calls.

set -o pipefail
cd "$(dirname "$0")" || exit 1

PREFIX=smokev2
MAX_CONN=4
EXEC_WORKERS=2
CELLS=(c1 c2 c3 c4 c5 c6 c7 c8)

if [ "$1" = "--status" ]; then
  for c in "${CELLS[@]}"; do
    log="runs_${PREFIX}-${c}.log"
    printf '%-12s %-9s warns=%-4s %s\n' "$c" \
      "$(tmux has-session -t "${PREFIX}-$c" 2>/dev/null && echo running || echo done)" \
      "$(grep -c '\[warn\]' "$log" 2>/dev/null || echo 0)" \
      "$(tail -1 "$log" 2>/dev/null | cut -c1-60)"
  done
  echo "--- rate-limit / throttle hits across all cells ---"
  grep -ihE "rate.?limit|429|too many requests|throttl" runs_${PREFIX}-c*.log 2>/dev/null | sort | uniq -c | head
  exit 0
fi

T="openai-api/azureai/DeepSeek-V3.2"
U="openai-api/azureai/gpt-5.4"
COMMON=(--domain apps --dataset apps_pool_hard.json --limit 2 --runs 2 --seed 900
        --no-progress --no-inspect-cache --t-model "$T" --t-reasoning low
        --max-conn "$MAX_CONN" --exec-workers "$EXEC_WORKERS")
UPLAN=(--u-model "$U" --u-reasoning high --gen-strategy u_plans_t_writes)
BLIND=(--gen-strategy blind_t)

launch() {
  local c="$1"; shift
  local id="${PREFIX}-${c}" log="runs_${PREFIX}-${c}.log"
  tmux kill-session -t "$id" 2>/dev/null
  tmux new-session -d -s "$id" \
    "caffeinate -dims .venv/bin/python run.py --run-id '$id' $(printf '%q ' "${COMMON[@]}" "$@") 2>&1 | tee -a '$log'; echo \"=== $id exit=\${PIPESTATUS[0]} \$(date -u +%H:%M:%SZ) ===\" >> '$log'"
  echo "launched $id"
}

launch c1 "${BLIND[@]}"
launch c2 "${BLIND[@]}" --code-aware-search
launch c3 "${UPLAN[@]}"
launch c4 "${UPLAN[@]}" --code-aware-search
launch c5 "${BLIND[@]}" --self-critique
launch c6 "${BLIND[@]}" --self-critique --code-aware-search
launch c7 "${UPLAN[@]}" --self-critique
launch c8 "${UPLAN[@]}" --self-critique --code-aware-search

echo "8 sessions up. Watch: bash smoke_batch.sh --status"
