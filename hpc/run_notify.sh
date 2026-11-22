#!/usr/bin/env bash
# Change notices for the HPC: runs notify_changes.py through run_reminder.sh
# (same code update and mail settings), logging to ~/tischedule-notify.log.
# Arguments (--dry-run, --test-to ADDRESS, --accept) are passed on.
# Scheduling: see hpc/README.md.
SCRIPT=notify_changes.py LOG="${LOG:-$HOME/tischedule-notify.log}" \
    exec "$(dirname "${BASH_SOURCE[0]}")/run_reminder.sh" "$@"
