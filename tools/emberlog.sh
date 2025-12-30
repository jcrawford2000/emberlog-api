#!/usr/bin/env bash
set -euo pipefail

SESSION="emberlog"
BASE="/srv/emberlog"

branch_of() {
  git -C "$1" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main
}

# Safely check for existing session without tripping `set -e`
set +e
tmux has-session -t "$SESSION" >/dev/null 2>&1
has=$?
set -e

if [ "$has" -eq 0 ]; then
  exec tmux attach -t "$SESSION"
fi

# Make sure our helper scripts exist & are executable
for f in emberlog-api.sh emberlog-notifier.sh emberlog-web.sh; do
  [ -x "$BASE/$f" ] || { echo "Missing or not executable: $BASE/$f"; exit 1; }
done

# Create the session + windows
tmux new-session -d -s "$SESSION" -n "api" -c "$BASE" 

tmux new-window  -t "$SESSION":1 -n "notifier" -c "$BASE" 

tmux new-window  -t "$SESSION":2 -n "web" -c "$BASE" 

# Nice titles
tmux rename-window -t "$SESSION":0 "api"
tmux select-window -t "$SESSION":0
exec tmux attach -t "$SESSION"
