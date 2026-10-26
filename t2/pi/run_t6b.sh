#!/usr/bin/env bash
B=$(cd "$(dirname "$0")" && pwd)
source "$B/../../scripts/tier2_sweep.sh"
export PI_CODING_AGENT_DIR="$B/.pi"
tier2_begin "$B" pi t6b || exit 1
KEY=$OPENROUTER_API_KEY
cd "$B/scratch" || exit 1
OPENROUTER_API_KEY=$KEY pi -p --mode json --provider openrouter --model qwen/qwen3.7-flash --thinking off -t bash \
  "Use the bash tool to run exactly: sleep 60 && echo LATE_GT. Then print DONE_GT." >"$B/t6b.jsonl" 2>"$B/t6b.err" &
PI=$!
echo "pi_pid=$PI pi_pgid=$(ps -o pgid= -p $PI | tr -d ' ')"
SLEEPPID=""
for i in $(seq 1 90); do
  SLEEPPID=$(pgrep -x sleep | head -1)
  [ -n "$SLEEPPID" ] && {
    echo "sleep_appeared_after=${i}s"
    break
  }
  kill -0 $PI 2>/dev/null || {
    echo "pi_exited_before_sleep"
    break
  }
  sleep 1
done
[ -z "$SLEEPPID" ] && {
  echo "NO_SLEEP_SPAWNED"
  kill $PI 2>/dev/null
  exit 0
}
echo "=== sleep proc (before kill) ==="
ps -o pid,ppid,pgid,command -p "$SLEEPPID"
SLEEP_PGID=$(ps -o pgid= -p "$SLEEPPID" | tr -d ' ')
PI_PGID=$(ps -o pgid= -p $PI | tr -d ' ')
echo "sleep_pgid=$SLEEP_PGID pi_pgid=$PI_PGID same_group=$([ "$SLEEP_PGID" = "$PI_PGID" ] && echo yes || echo no)"
sleep 2
echo "=== plain SIGTERM to pi $PI only ==="
kill -TERM $PI 2>/dev/null
sleep 3
if kill -0 "$SLEEPPID" 2>/dev/null; then
  echo "ORPHAN=YES sleep $SLEEPPID survived pi SIGTERM (needs tree-kill)"
  ps -o pid,ppid,pgid,command -p "$SLEEPPID"
else
  echo "ORPHAN=NO sleep $SLEEPPID terminated with pi"
fi
kill -9 "$SLEEPPID" 2>/dev/null
pkill -9 -P "$PI" 2>/dev/null
kill -9 "$PI" 2>/dev/null
echo "T6_DONE"
