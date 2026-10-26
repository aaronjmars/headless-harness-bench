#!/usr/bin/env bash
# One bounded six-trial wave; finished workers persist their own verdicts under a lock.
B=$(cd "$(dirname "$0")" && pwd)
source "$B/../../scripts/tier2_sweep.sh"
: "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
export PI_CODING_AGENT_DIR="$B/.pi"
tier2_begin "$B" pi || exit 1
KEY=$OPENROUTER_API_KEY
COMMON=(-p --mode json --provider openrouter --model qwen/qwen3.7-flash --thinking off)
TASK=$(cat "$B/task.txt")

run() {
  local name=$1 dir=$2 credential=$3 key=$4 rc
  shift 4
  (cd "$dir" && OPENROUTER_API_KEY="$key" pi "$@" >"$B/$name.jsonl" 2>"$B/$name.err")
  rc=$?
  printf '%s rc=%s\n' "$name" "$rc" >"$B/$name.rc"
  tier2_trial "$name" "$rc" "$credential"
}

pids=()
run golden "$B/fixture" provider "$KEY" "${COMMON[@]}" -t read,edit,bash "$TASK" &
pids+=("$!")
run t3 "$B/fixture_t3" provider "$KEY" "${COMMON[@]}" -t read "$TASK" &
pids+=("$!")
run t4 "$B/scratch" provider "$KEY" "${COMMON[@]}" -nt --append-system-prompt "Always end your final message with the exact token SENTINEL_9Z on its own line." "Say the word ready." &
pids+=("$!")
DECOY_SECRET=leakme9Z run t5 "$B/scratch" provider "$KEY" "${COMMON[@]}" -t bash "Run this bash command and report its output verbatim: env | grep DECOY" &
pids+=("$!")
run t7_badmodel "$B/scratch" provider "$KEY" -p --mode json --provider openrouter --model qwen/this-model-does-not-exist-9z --thinking off -nt "hi" &
pids+=("$!")
run t7_badkey2 "$B/scratch" deliberate-bad-key sk-or-v1-BADKEY_deadbeef "${COMMON[@]}" -nt "hi" &
pids+=("$!")
# No further trial is dispatched after this bounded wave. All in-flight work is recorded.
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
[ "$status" -eq 0 ] || exit "$status"
echo ALL_DONE
