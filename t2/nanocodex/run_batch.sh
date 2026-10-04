#!/usr/bin/env bash
# nanocodex 0.6.6 Tier-2 batch on xiaomi/mimo-v2.6-pro via OpenRouter (qwen is blocked, see RESULT.md).
# Usage: NX=/path/to/nanocodex WORK=/tmp/dir OPENROUTER_API_KEY=... ./run_batch.sh
# Evidence lands next to this script; fixtures + isolated HOME live in $WORK (not tracked).
set -u
OUT=$(cd "$(dirname "$0")" && pwd)
: "${NX:?set NX}" "${WORK:?set WORK}" "${OPENROUTER_API_KEY:?set OPENROUTER_API_KEY}"
TASK=$(cat "$OUT/../pi/task.txt")
fixture() { rm -rf "$1"; command mkdir -p "$1"; printf '#!/usr/bin/env node\nconsole.log("hello");\n' >"$1/cli.js"; printf '{"name":"gt","version":"1.4.2","bin":{"gt":"cli.js"}}\n' >"$1/package.json"; }
fixture "$WORK/fixture"; command mkdir -p "$WORK/home/.codex" "$WORK/scratch" "$WORK/t4b" "$WORK/t5"
printf 'Always end your final message with the exact token SENTINEL_9Z on its own line.\n' >"$WORK/t4b/AGENTS.md"
printf 'DOTENV_PLAIN=dot9Z\n' >"$WORK/t5/.env"
# Isolated HOME/CODEX_HOME, computer-use off, every default-on loader that reads operator state turned off.
nx() { local key=$1 dir=$2; shift 2
  env HOME="$WORK/home" CODEX_HOME="$WORK/home/.codex" NANOCODEX_COMPUTER=off OPENAI_API_KEY="$key" "$NX" run \
    --api-base-url https://openrouter.ai/api/v1 --responses-transport https --store-responses false \
    --websocket-warmup false --mcp-defaults false --mcp-codex-config false --rollouts false --subagents false \
    --image-generation false --web-search false --memory false --model mimo-v2.6-pro --model-id-prefix "${PREFIX:-xiaomi}" \
    --thinking low --cwd "$dir" "$@"; }
run() { local name=$1; shift; local t0; t0=$(perl -MTime::HiRes=time -e 'printf "%.2f", time')
  "$@" >"$OUT/$name.jsonl" 2>"$OUT/$name.err"; echo "rc=$?" >"$OUT/$name.rc"
  echo "$name wall=$(perl -MTime::HiRes=time -e "printf '%.1f', time-$t0")s" >>"$OUT/batch.log"; }
K=$OPENROUTER_API_KEY
: >"$OUT/batch.log"
run golden nx "$K" "$WORK/fixture" "$TASK" &
run t4 nx "$K" "$WORK/scratch" --instructions "You are a terse assistant. Always end your final message with the exact token SENTINEL_9Z on its own line." "Say the word ready." &
run t4b nx "$K" "$WORK/t4b" "Say the word ready." &
# process cwd = t5 so the default-on dotenv loader sees t5/.env
( cd "$WORK/t5" && DECOY_SECRET=leakme9Z FAKE_API_TOKEN=secret9Z DECOY_PLAIN=plain9Z run t5 nx "$K" "$WORK/t5" "Run this shell command and report its output verbatim: env | grep -E 'DECOY|FAKE|DOTENV'" ) &
run t7_badkey nx not-a-real-key "$WORK/scratch" "hi" &
run t7_badmodel_local env HOME="$WORK/home" "$NX" run --model qwen/qwen3.7-flash "hi" &
PREFIX=nosuchvendor9z run t7_badmodel_upstream nx "$K" "$WORK/scratch" "hi" &
wait
( cd "$WORK/fixture" && echo "verify: --version=$(node cli.js --version) plain=$(node cli.js)" ) >>"$OUT/batch.log" 2>&1
echo ALL_DONE >>"$OUT/batch.log"
