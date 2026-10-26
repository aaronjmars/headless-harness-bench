#!/usr/bin/env bash
B=$(cd "$(dirname "$0")" && pwd)
source "$B/../../scripts/tier2_sweep.sh"
export PI_CODING_AGENT_DIR="$B/.pi"
tier2_begin "$B" pi t6 || exit 1
KEY=$OPENROUTER_API_KEY
cd "$B/scratch" || exit 1
OPENROUTER_API_KEY=$KEY pi -p --mode json --provider openrouter --model qwen/qwen3.7-flash --thinking off -t bash \
  "Run this exact bash command using the bash tool: sleep 60. After it completes, print DONE_GT." >"$B/t6.jsonl" 2>"$B/t6.err" &
PI=$!
echo "pi_pid=$PI"
# wait for a 'sleep 60' descendant to appear
SLEEPPID=""
for i in $(seq 1 90); do
  SLEEPPID=$(pgrep -f "sleep 60" | head -1)
  if [ -n "$SLEEPPID" ]; then
    echo "sleep_appeared_after=${i}s sleep_pid=$SLEEPPID"
    break
  fi
  if ! kill -0 $PI 2>/dev/null; then
    echo "pi_exited_before_sleep"
    break
  fi
  sleep 1
done
if [ -z "$SLEEPPID" ]; then
  echo "NO_SLEEP_SPAWNED"
  kill $PI 2>/dev/null
  exit 0
fi
# show sleep proc + its pgid/ppid
ps -o pid,ppid,pgid,command -p "$SLEEPPID"
# plain SIGTERM to pi (not the group)
sleep 3
echo "killing pi $PI with plain SIGTERM"
kill -TERM $PI 2>/dev/null
sleep 3
if kill -0 "$SLEEPPID" 2>/dev/null; then
  echo "ORPHAN=YES sleep $SLEEPPID still alive after killing pi"
  ps -o pid,ppid,pgid,command -p "$SLEEPPID"
else
  echo "ORPHAN=NO sleep $SLEEPPID died with pi"
fi
# cleanup
kill -9 "$SLEEPPID" 2>/dev/null
pkill -9 -P "$PI" 2>/dev/null
kill -9 "$PI" 2>/dev/null
echo "T6_DONE"
