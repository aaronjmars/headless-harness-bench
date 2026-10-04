#!/usr/bin/env bash
# T6 re-run: SIGTERM `eve invoke` while the docker sandbox runs `sleep 120`, then check
# the host process tree AND the sandbox container for a surviving sleep.
# Usage: PROJ=/path/to/fresh-eve-project OPENROUTER_API_KEY=... ./run_t6.sh
OUT=$(cd "$(dirname "$0")" && pwd); : "${PROJ:?set PROJ}"
cd "$PROJ" || exit 1
LOG="$OUT/t6-rerun.out"
echo "containers before: $(docker ps --format '{{.ID}} {{.Image}}' | tr '\n' ';')"
./node_modules/.bin/eve invoke "Use your bash tool to run exactly this command and wait for it to finish: sleep 120 && echo SLEPT_T6" >"$LOG" 2>&1 &
EP=$!
echo "invoke_pid=$EP pgid=$(ps -o pgid= -p $EP | tr -d ' ')"
for i in $(seq 1 120); do
  grep -q 'starting sandbox command: sleep 120' "$LOG" && { echo "sleep_started_after=${i}s"; break; }
  kill -0 $EP 2>/dev/null || { echo "invoke_exited_before_sleep"; break; }
  sleep 1
done
sleep 3
C=$(docker ps --format '{{.ID}} {{.Image}}' | awk '/eve/ {print $1; exit}')
echo "sandbox_container=$C"
echo "=== in-container processes before cancel ==="; docker top "$C" -o pid,args 2>/dev/null | grep -E 'sleep|PID'
echo "=== host descendants of invoke before cancel ==="; pgrep -fl 'sleep 120' | grep -v pgrep || echo none
echo "=== SIGTERM to eve invoke $EP only ==="
kill -TERM $EP
# poll once a second: is eve alive, is the sandbox sleep alive, is the container up
for t in $(seq 1 60); do
  sleep 1
  e=dead; kill -0 $EP 2>/dev/null && e=alive
  z=gone; docker top "$C" -o args 2>/dev/null | grep -q 'sleep 120' && z=running
  k=gone; docker ps --format '{{.ID}}' | grep -q "^$C" && k=up
  echo "t+${t}s eve=$e sandbox_sleep=$z container=$k"
  [ $e = dead ] && [ $z = gone ] && [ $k = gone ] && break
done
wait $EP; echo "invoke rc=$?"
pgrep -fl 'sleep 120' | grep -v pgrep || echo "no host sleep"
echo T6_DONE
