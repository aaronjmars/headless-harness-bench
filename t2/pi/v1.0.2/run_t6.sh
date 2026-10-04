#!/usr/bin/env bash
OUT=$(cd "$(dirname "$0")" && pwd); : "${PI:?set PI}" "${WORK:?set WORK}"
export PI_CODING_AGENT_DIR=$WORK/.pi
KEY=$OPENROUTER_API_KEY
cd "$WORK/scratch"
OPENROUTER_API_KEY=$KEY "$PI" -p --mode json --provider openrouter --model qwen/qwen3.7-flash --thinking off -t bash \
  "Use the bash tool to run exactly this command: sleep 129. After it finishes print DONE_GT." >"$OUT/t6.jsonl" 2>"$OUT/t6.err" &
PI=$!
echo "pi_pid=$PI pi_pgid=$(ps -o pgid= -p $PI|tr -d ' ')"
# find the REAL sleep: matches 'sleep 129', is NOT pi, comm is exactly 'sleep'
REAL=""
for i in $(seq 1 90); do
  for c in $(pgrep -f "sleep 129"); do
    [ "$c" = "$PI" ] && continue
    cm=$(ps -o comm= -p $c 2>/dev/null | tr -d ' ')
    [ "$cm" = "sleep" ] && { REAL=$c; break; }
  done
  [ -n "$REAL" ] && { echo "real_sleep_after=${i}s pid=$REAL"; break; }
  kill -0 $PI 2>/dev/null || { echo "pi_exited_before_sleep"; break; }
  sleep 1
done
[ -z "$REAL" ] && { echo "NO_SLEEP_SPAWNED"; kill $PI 2>/dev/null; exit 0; }
echo "=== real sleep proc + ancestry ==="
ps -o pid,ppid,pgid,command -p $REAL
SP=$(ps -o pgid= -p $REAL|tr -d ' '); PP=$(ps -o pgid= -p $PI|tr -d ' ')
echo "sleep_pgid=$SP pi_pgid=$PP same_group=$([ "$SP" = "$PP" ]&&echo yes||echo no)"
# confirm pi is an ancestor of REAL
a=$REAL; anc="no"; for _ in 1 2 3 4 5 6; do a=$(ps -o ppid= -p $a 2>/dev/null|tr -d ' '); [ -z "$a" ]&&break; [ "$a" = "$PI" ]&&{ anc="yes"; break; }; done
echo "pi_is_ancestor_of_sleep=$anc"
sleep 2
echo "=== plain SIGTERM to pi $PI only (kill -TERM \$PI, not the group) ==="
kill -TERM $PI 2>/dev/null
sleep 3
if kill -0 $REAL 2>/dev/null; then
  echo "ORPHAN=YES real sleep $REAL survived pi SIGTERM -> needs tree-kill"
  ps -o pid,ppid,pgid,command -p $REAL
else
  echo "ORPHAN=NO real sleep $REAL died when pi got SIGTERM"
fi
kill -9 $REAL 2>/dev/null; pkill -9 -P $PI 2>/dev/null; kill -9 $PI 2>/dev/null
echo "T6_DONE"
