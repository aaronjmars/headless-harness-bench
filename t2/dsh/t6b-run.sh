#!/bin/bash
D=$(cd "$(dirname "$0")" && pwd)
source "$D/../../scripts/tier2_sweep.sh"
tier2_begin "$D" dsh t6 || exit 1
export DSH_HOME="$D/home"
cd "$D/fixture" || exit 1
rm -f /tmp/t6_marker_9z
T6='Run exactly this one bash command: touch /tmp/t6_marker_9z && sleep 137. After it finishes, print DONE_T6.'
OPENROUTER_API_KEY=$OPENROUTER_API_KEY DSH_HOME=$D/home DSH_PERMISSION_MODE=danger-full-access \
  npx @deepseek-ai/dsh@0.1.6-alpha.2 --profile headless --json "$T6" >"$D/t6.jsonl" 2>"$D/t6.err" &
NPXPID=$!
echo "launched pid=$NPXPID"
# Gate: wait until bash child actually starts the command (marker file), max 60s
for _ in $(seq 1 120); do
  [ -f /tmp/t6_marker_9z ] && break
  sleep 0.5
done
[ -f /tmp/t6_marker_9z ] && echo "MARKER: bash child ran (command started)" || echo "MARKER: NEVER (model did not run it)"
# real child = process literally named 'sleep' with arg 137 (excludes node launcher)
realpids="$(pgrep -x sleep)"
echo "=== BEFORE KILL: real 'sleep 137' child? ==="
found_before=NO
for p in $realpids; do
  a=$(ps -o args= -p "$p" 2>/dev/null)
  case "$a" in "sleep 137"*)
    echo "PID $p -> $a"
    found_before=YES
    ;;
  esac
done
[ "$found_before" = YES ] || echo "no sleep137 child found"
# kill launcher (SIGTERM) - reap ladder should propagate to child
kill -TERM "$NPXPID" 2>/dev/null
echo "sent SIGTERM to launcher at $(date +%T)"
sleep 5
echo "=== AFTER TERM(+5s): launcher alive? ==="
kill -0 "$NPXPID" 2>/dev/null && echo yes || echo no
echo "=== AFTER TERM(+5s): orphaned 'sleep 137'? ==="
found_after=NO
for p in $(pgrep -x sleep); do
  a=$(ps -o args= -p "$p" 2>/dev/null)
  case "$a" in "sleep 137"*)
    echo "ORPHAN PID $p -> $a"
    found_after=YES
    ;;
  esac
done
[ "$found_after" = YES ] && echo "RESULT: ORPHAN SURVIVES" || echo "RESULT: NONE (child reaped)"
