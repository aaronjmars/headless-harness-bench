#!/usr/bin/env bash
# Pi 1.0.2 rerun of the Tier-2 batch. Usage: PI=/path/to/pi WORK=/tmp/dir ./run_batch.sh [extra pi flags]
# Evidence lands next to this script; fixtures + .pi state live in $WORK (not tracked).
set -u
OUT=$(cd "$(dirname "$0")" && pwd)
: "${PI:?set PI}" "${WORK:?set WORK}" "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
export PI_CODING_AGENT_DIR=$WORK/.pi
COMMON=(-p --mode json --provider openrouter --model qwen/qwen3.7-flash "$@")
TASK=$(cat "$OUT/../task.txt")
fixture() { rm -rf "$1"; command mkdir -p "$1"; printf '#!/usr/bin/env node\nconsole.log("hello");\n' >"$1/cli.js"; printf '{"name":"gt","version":"1.4.2","bin":{"gt":"cli.js"}}\n' >"$1/package.json"; }
fixture "$WORK/fixture"; fixture "$WORK/fixture_t3"; command mkdir -p "$WORK/scratch"
run() { local name=$1 dir=$2; shift 2; local t0; t0=$(date +%s.%N 2>/dev/null || date +%s)
  ( cd "$dir" && "$@" >"$OUT/$name.jsonl" 2>"$OUT/$name.err"; echo "rc=$?" >"$OUT/$name.rc" )
  echo "$name wall=$(echo "$(date +%s.%N 2>/dev/null || date +%s) - $t0" | bc)s" >>"$OUT/batch.log"; }
: >"$OUT/batch.log"
run golden "$WORK/fixture" "$PI" "${COMMON[@]}" -t read,edit,bash "$TASK" &
run t3 "$WORK/fixture_t3" "$PI" "${COMMON[@]}" -t read "$TASK" &
run t4 "$WORK/scratch" "$PI" "${COMMON[@]}" -nt --append-system-prompt "Always end your final message with the exact token SENTINEL_9Z on its own line." "Say the word ready." &
run t5 "$WORK/scratch" env DECOY_SECRET=leakme9Z "$PI" "${COMMON[@]}" -t bash "Run this bash command and report its output verbatim: env | grep DECOY" &
run t7_badmodel "$WORK/scratch" "$PI" -p --mode json --provider openrouter --model qwen/this-model-does-not-exist-9z "$@" -nt "hi" &
run t7_badkey "$WORK/scratch" env OPENROUTER_API_KEY=not-a-real-key "$PI" "${COMMON[@]}" -nt "hi" &
wait
( cd "$WORK/fixture" && echo "verify: --version=$(node cli.js --version) plain=$(node cli.js)" ) >>"$OUT/batch.log" 2>&1
echo ALL_DONE >>"$OUT/batch.log"
