#!/bin/bash
D=$(cd "$(dirname "$0")" && pwd)
source "$D/../../scripts/tier2_sweep.sh"
tier2_begin "$D" dsh t6 || exit 1
export DSH_HOME="$D/home"
cd "$D/fixture" || exit 1
T6='Run this exact bash command (it will take a while, that is expected): sleep 60. After it completes, print DONE_T6.'
OPENROUTER_API_KEY=$OPENROUTER_API_KEY DSH_HOME=$D/home DSH_PERMISSION_MODE=danger-full-access \
  npx @deepseek-ai/dsh@0.1.6-alpha.2 --profile headless --json "$T6" >"$D/t6.jsonl" 2>"$D/t6.err" &
NPXPID=$!
echo "launched npx pid=$NPXPID"
# wait until the sleep 60 child appears (max 60s)
for _ in $(seq 1 120); do
  pgrep -f "sleep 60" >/dev/null && break
  sleep 0.5
done
echo "=== BEFORE KILL: sleep procs ==="
pgrep -fl "sleep 60" || echo "no sleep yet"
# find the actual node dsh process(es) in this DSH_HOME
echo "=== dsh node procs ==="
pgrep -fl "dsh@0.1.6-alpha.2|deepseek-ai/dsh" | grep -v grep || true
# SIGTERM the whole process group of npx
kill -TERM -"$NPXPID" 2>/dev/null || kill -TERM "$NPXPID" 2>/dev/null
echo "sent SIGTERM to $NPXPID at $(date +%T)"
sleep 4
echo "=== AFTER TERM(+4s): npx alive? ==="
kill -0 "$NPXPID" 2>/dev/null && echo "yes" || echo "no"
echo "=== AFTER TERM(+4s): sleep 60 orphan? ==="
pgrep -fl "sleep 60" || echo "NONE (reaped)"
sleep 3
echo "=== +7s: sleep 60 orphan? ==="
pgrep -fl "sleep 60" || echo "NONE (reaped)"
echo "=== +7s: any lingering dsh node? ==="
pgrep -fl "deepseek-ai/dsh" | grep -v grep || echo "NONE"
