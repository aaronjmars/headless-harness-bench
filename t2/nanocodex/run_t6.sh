#!/usr/bin/env bash
# T6: SIGTERM nanocodex (not its group) while its shell tool runs `sleep 129`; check for an orphan.
# Usage: NX=/path/to/nanocodex WORK=/tmp/dir OPENROUTER_API_KEY=... ./run_t6.sh
OUT=$(cd "$(dirname "$0")" && pwd); : "${NX:?set NX}" "${WORK:?set WORK}"
command mkdir -p "$WORK/home/.codex" "$WORK/scratch"; cd "$WORK/scratch" || exit 1
env HOME="$WORK/home" CODEX_HOME="$WORK/home/.codex" NANOCODEX_COMPUTER=off OPENAI_API_KEY="$OPENROUTER_API_KEY" "$NX" run \
  --api-base-url https://openrouter.ai/api/v1 --responses-transport https --store-responses false --websocket-warmup false \
  --mcp-defaults false --mcp-codex-config false --rollouts false --subagents false --image-generation false --web-search false \
  --memory false --model mimo-v2.6-pro --model-id-prefix xiaomi --thinking low --cwd "$WORK/scratch" \
  "Use the shell to run exactly this command and wait for it: sleep 129. After it finishes print DONE_GT." >"$OUT/t6.jsonl" 2>"$OUT/t6.err" &
NXP=$!
echo "nx_pid=$NXP nx_pgid=$(ps -o pgid= -p $NXP | tr -d ' ')"
REAL=""
for i in $(seq 1 90); do
  for c in $(pgrep -f "sleep 129"); do
    [ "$c" = "$NXP" ] && continue
    [ "$(ps -o comm= -p "$c" 2>/dev/null | tr -d ' ')" = "sleep" ] && { REAL=$c; break; }
  done
  [ -n "$REAL" ] && { echo "real_sleep_after=${i}s pid=$REAL"; break; }
  kill -0 $NXP 2>/dev/null || { echo "nx_exited_before_sleep"; break; }
  sleep 1
done
[ -z "$REAL" ] && { echo "NO_SLEEP_SPAWNED"; kill $NXP 2>/dev/null; exit 0; }
ps -o pid,ppid,pgid,command -p "$REAL"
SP=$(ps -o pgid= -p "$REAL" | tr -d ' '); PP=$(ps -o pgid= -p $NXP | tr -d ' ')
echo "sleep_pgid=$SP nx_pgid=$PP same_group=$([ "$SP" = "$PP" ] && echo yes || echo no)"
sleep 2
echo "=== plain SIGTERM to nanocodex $NXP only ==="
kill -TERM $NXP
sleep 3
kill -0 $NXP 2>/dev/null && echo "nx still alive 3s after SIGTERM" || echo "nx exited"
if kill -0 "$REAL" 2>/dev/null; then echo "ORPHAN=YES sleep $REAL survived"; ps -o pid,ppid,pgid,command -p "$REAL"; else echo "ORPHAN=NO sleep $REAL died with nanocodex"; fi
kill -9 "$REAL" 2>/dev/null; kill -9 $NXP 2>/dev/null
echo T6_DONE
