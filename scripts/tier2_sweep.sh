#!/usr/bin/env bash
# Source from an active Tier-2 launcher. The Python owner locks concurrent ledger updates.
TIER2_SWEEP_TOOL=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tier2_sweep.py

tier2_begin() {
  TIER2_OUT=$1 TIER2_SUBJECT=$2 TIER2_SINGLE=${3:-}
  TIER2_SWEEP=$(python3 "$TIER2_SWEEP_TOOL" start) || return 1
  export TIER2_SWEEP TIER2_OUT TIER2_SUBJECT TIER2_SWEEP_TOOL
  trap 'tier2_finalize "$?"' EXIT
}

tier2_trial() {
  local name=$1 rc=$2 credential=${3:-provider}
  python3 "$TIER2_SWEEP_TOOL" trial --sweep "$TIER2_SWEEP" --out "$TIER2_OUT" \
    --subject "$TIER2_SUBJECT" --name "$name" --rc "$rc" --credential "$credential"
}

tier2_finalize() {
  local rc=$1
  trap - EXIT
  if [ -n "$TIER2_SINGLE" ]; then
    tier2_trial "$TIER2_SINGLE" "$rc" || rc=1
  fi
  python3 "$TIER2_SWEEP_TOOL" finish --sweep "$TIER2_SWEEP" --out "$TIER2_OUT" --rc "$rc" || rc=1
  exit "$rc"
}
