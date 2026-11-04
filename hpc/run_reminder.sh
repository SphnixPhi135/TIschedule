#!/usr/bin/env bash
# Friday reminder runner for the HPC.
#
# Updates the code from GitHub, loads the mail settings, then runs
# reminder.py. Any arguments (--dry-run, --test-to ADDRESS) are passed on.
# Setup and scheduling: see hpc/README.md.
#
# Settings that can be overridden from the environment:
#   REPO_DIR        the clone of this repository   (default: this script's repo)
#   TISCHEDULE_ENV  mail settings file             (default: ~/.config/tischedule/env)
#   PYTHON          Python with pandas installed   (default: $REPO_DIR/.venv/bin/python)
#   LOG             log file when not run by hand  (default: ~/tischedule-reminder.log)

set -uo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
TISCHEDULE_ENV="${TISCHEDULE_ENV:-$HOME/.config/tischedule/env}"
PYTHON="${PYTHON:-$REPO_DIR/.venv/bin/python}"
LOG="${LOG:-$HOME/tischedule-reminder.log}"

# Run by hand: print to the terminal. Run by cron/scrontab: append to the log.
if [ ! -t 1 ]; then
    exec >>"$LOG" 2>&1
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') reminder run on $(hostname) ==="

cd "$REPO_DIR" || { echo "ERROR: cannot enter $REPO_DIR"; exit 1; }

# Use the latest schedule code and member list. If GitHub can't be reached,
# still send with the local copy: a stale members.csv beats no reminders.
if ! git pull --ff-only --quiet origin main; then
    echo "WARNING: could not update from GitHub; using the local copy."
fi

if [ ! -r "$TISCHEDULE_ENV" ]; then
    echo "ERROR: mail settings not found at $TISCHEDULE_ENV (see hpc/README.md)."
    exit 1
fi
set -a
# shellcheck source=/dev/null
. "$TISCHEDULE_ENV"
set +a

if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python not found at $PYTHON (see hpc/README.md)."
    exit 1
fi

"$PYTHON" reminder.py "$@"
status=$?
echo "=== finished with status $status ==="
exit "$status"
