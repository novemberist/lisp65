#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ACTION=${1:-dry-run}
SESSION="$ROOT/config/c2-v20-loading-libraries-progress-session.json"
DEPLOY="$ROOT/build/c2.3/v2.0-loading-libraries-progress/deployment.json"

if [ "$ACTION" != dry-run ]; then
  echo "CONTACT-NOT-AUTHORIZED: only dry-run is available" >&2
  exit 2
fi

python3 "$ROOT/tools/host-lisp/c2_v20_loading_libraries_progress_ring.py" check
python3 - "$SESSION" "$DEPLOY" <<'PY'
import json
import pathlib
import sys

session = json.loads(pathlib.Path(sys.argv[1]).read_text())
deploy = json.loads(pathlib.Path(sys.argv[2]).read_text())
assert session["authorization"] == {
    "contact_authorized": False, "D1_D5_open": False, "dry_run_only": True}
assert session["active_interval"]["host_monitor_entries"] == 0
assert session["active_interval"]["host_CPU_stops"] == 0
assert session["future_readback"]["stop_transitions"] == 1
assert deploy["future_contact"]["authorized"] is False
assert deploy["future_contact"]["runner_action_available"] == "dry-run-only"
print("LOADING-LIBRARIES PROGRESS DRY-RUN PASS")
print("contact=no; D1-D5=closed; target samples four commit-last slots")
PY
