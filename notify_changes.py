"""Email presenters when their upcoming talks change in the schedule.

Runs on the HPC every 10 minutes (see hpc/README.md). It reads the Schedule
tab, compares it with the copy it last notified about, and emails each person
whose upcoming talks changed: a swap or reassignment in the app, an edit made
directly in the sheet, or a meeting marked as cancelled. Mail settings are
the same environment variables as reminder.py.

A change is only sent once it has been seen on two runs in a row, so a sheet
that is still being edited by hand does not trigger half-finished emails.

When more than NOTIFY_MAX_PEOPLE people (default 8) would get an email, for
example after a whole new schedule is pasted in, nothing is sent: check the
change, then run with --accept to take it as the new starting point.

Options:
    --dry-run       show what would be sent; change nothing
    --test-to ADDR  send every email to ADDR instead of the presenters
    --accept        take the current schedule as notified, without sending

The first run only records the schedule. Exits with status 1 if something
failed or needs a person to look at it.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from calendar_export import infer_dates
from mailer import SCHEDULE_URL, SMTP_HOST, SMTP_PORT, build_message, send_messages
from reminder import url as SHEET_CSV_URL

SLOTS = ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]
KIND = {"Slot 1": "30-minute presentation"}   # the other slots are 5-minute


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-to", metavar="ADDRESS")
    parser.add_argument("--accept", action="store_true")
    return parser.parse_args()


def clean(value):
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def snapshot(df, today):
    """{iso date: {"label", "cancelled", "talks": {name: kind}}} for meetings from today on."""
    rows = df.to_dict("records")
    dates = infer_dates([r.get("Date", "") for r in rows], today)
    snap = {}
    for row, day in zip(rows, dates):
        if day is None or day < today:
            continue
        talks = {}
        for slot in SLOTS:
            name = clean(row.get(slot))
            if name:
                talks[name] = KIND.get(slot, "5-minute presentation")
        snap[day.isoformat()] = {
            "label": clean(row.get("Date")),
            "cancelled": "cancel" in clean(row.get("Notes")).lower(),
            "talks": talks,
        }
    return snap


def upcoming(snap, today):
    return {d: m for d, m in snap.items() if d >= today.isoformat()}


def changes(old, new, today):
    """{name: [sentence, ...]} for everyone whose upcoming talks changed."""
    old, new = upcoming(old, today), upcoming(new, today)
    out = {}
    for iso in sorted(set(old) | set(new)):
        before = old.get(iso, {"cancelled": False, "talks": {}})
        after = new.get(iso, {"cancelled": False, "talks": {}})
        when = datetime.strptime(iso, "%Y-%m-%d").strftime("%A %d %B").replace(" 0", " ")
        if after["cancelled"] and not before["cancelled"]:
            for name in after["talks"]:
                out.setdefault(name, []).append(f"The meeting on {when} has been cancelled.")
            continue
        was = {} if before["cancelled"] else before["talks"]
        now = {} if after["cancelled"] else after["talks"]
        for name in sorted(set(was) | set(now)):
            a, b = was.get(name), now.get(name)
            if a == b:
                continue
            if a and b:
                line = f"You now give a {b} on {when}, instead of a {a}."
            elif b:
                line = f"You are now presenting on {when} ({b})."
            else:
                line = f"You are no longer presenting on {when}."
            out.setdefault(name, []).append(line)
    return out


def build_messages(changed, emails, sender, reply_to, test_to):
    messages, unreachable = [], []
    for name, lines in changed.items():
        address = emails.get(name)
        if not address:
            unreachable.append(name)
            continue
        text_body = (f"Hello {name},\n\nThe TI meeting schedule has changed:\n\n"
                     + "".join(f"- {line}\n" for line in lines)
                     + f"\nThe full schedule is here:\n{SCHEDULE_URL}\n\nBest,\nVinicio\n")
        items = "".join(f"<li>{line}</li>" for line in lines)
        html_body = (f"<html><body><p>Hello {name},</p><p>The TI meeting schedule has changed:</p>"
                     f"<ul>{items}</ul><p>The full schedule is here:<br>"
                     f'<a href="{SCHEDULE_URL}">{SCHEDULE_URL}</a></p>'
                     f"<p>Best,<br>Vinicio</p></body></html>")
        subject = "TI meeting: your presentation schedule has changed"
        if test_to:
            print(f"TEST: email for {name} <{address}> goes to {test_to}")
            address, subject = test_to, f"[TEST] {subject}"
        messages.append(build_message(sender=sender or "not-configured@example.invalid",
                                      recipient=address, subject=subject,
                                      text_body=text_body, html_body=html_body,
                                      reply_to=reply_to))
    return messages, unreachable


def main():
    args = parse_args()
    state_dir = Path(os.environ.get("TISCHEDULE_STATE")
                     or Path.home() / ".local/state/tischedule")
    notified_file, pending_file = state_dir / "notified.json", state_dir / "pending.json"
    today = (date.fromisoformat(os.environ["TISCHEDULE_TODAY"])
             if os.environ.get("TISCHEDULE_TODAY") else date.today())

    def save(path, snap):
        if not args.dry_run:
            state_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(snap, indent=1, sort_keys=True))
            tmp.replace(path)

    def clear_pending():
        if not args.dry_run and pending_file.exists():
            pending_file.unlink()

    df = pd.read_csv(os.environ.get("SCHEDULE_CSV") or SHEET_CSV_URL,
                     dtype=str, keep_default_na=False)
    current = snapshot(df, today)
    if not current:
        print("ERROR: no upcoming meetings found in the schedule; not changing anything.")
        return 1

    if args.accept or not notified_file.exists():
        save(notified_file, current)
        clear_pending()
        print("Recorded the current schedule as the starting point. Nothing sent.")
        return 0

    notified = json.loads(notified_file.read_text())
    changed = changes(notified, current, today)
    if not changed:
        clear_pending()
        print("No changes.")
        return 0

    pending = json.loads(pending_file.read_text()) if pending_file.exists() else None
    if pending is None or upcoming(pending, today) != upcoming(current, today):
        save(pending_file, current)
        print(f"Change seen for {', '.join(changed)}; sending on the next run "
              f"if the schedule stays the same.")
        return 0

    limit = int(os.environ.get("NOTIFY_MAX_PEOPLE") or 8)
    if len(changed) > limit:
        print(f"WARNING: {len(changed)} people would get an email (limit {limit}), "
              f"so nothing was sent. If this is a new schedule, run with --accept. "
              f"People affected: {', '.join(changed)}")
        return 1

    emails = pd.read_csv("members.csv").set_index("Name")["Email"].to_dict()
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    host = os.environ.get("SMTP_HOST") or SMTP_HOST
    port = int(os.environ.get("SMTP_PORT") or SMTP_PORT)
    security = (os.environ.get("SMTP_SECURITY") or "ssl").lower()
    messages, unreachable = build_messages(changed, emails, sender,
                                           os.environ.get("REPLY_TO"), args.test_to)
    if unreachable:
        print(f"WARNING: no email on file for {', '.join(unreachable)} - not notified.")

    if args.dry_run:
        print(f"DRY RUN: would send {len(messages)} email(s) via {host}:{port} ({security}):")
        for msg in messages:
            print(f"  To: {msg['To']}")
            print("    " + msg.get_body(("plain",)).get_content().replace("\n", "\n    "))
        return 0

    if messages and not sender:
        print("ERROR: no sender address. Set SMTP_FROM (or SMTP_USER).")
        return 1
    try:
        sent, failures = send_messages(os.environ.get("SMTP_USER"),
                                       os.environ.get("SMTP_PASSWORD"), messages,
                                       host=host, port=port, security=security)
    except Exception as e:
        print(f"Failed to send via {host}:{port} ({security}): {e}")
        return 1
    for address in sent:
        print(f"Change notice sent to {address}")
    for address, error in failures:
        print(f"Failed to send to {address}: {error}")

    # Record the change even if one address failed, so the others are not
    # emailed again; the failure is in the log for a person to follow up.
    save(notified_file, current)
    clear_pending()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
