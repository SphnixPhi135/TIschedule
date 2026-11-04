"""Send the Friday reminder to everyone presenting at the coming Monday's meeting.

Runs on the HPC (see hpc/README.md) or as the GitHub Action. The mail server
is configured through environment variables, defaulting to Gmail:

    SMTP_HOST      mail server (default smtp.gmail.com)
    SMTP_PORT      port (default 465)
    SMTP_SECURITY  ssl | starttls | none (default ssl)
    SMTP_FROM      address the mail is sent from (default SMTP_USER)
    SMTP_USER      login, only if the server needs one
    SMTP_PASSWORD  password, only if the server needs one
    REPLY_TO       where replies go (default DEFAULT_REPLY_TO in mailer.py)

Options:
    --dry-run       show what would be sent, without connecting to a server
    --test-to ADDR  send every reminder to ADDR instead of the presenters

Exits with status 1 if any reminder could not be sent.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

from mailer import (SCHEDULE_URL, SMTP_HOST, SMTP_PORT, build_message,
                    join_names, send_messages)

# Your specific Google Sheet ID
SHEET_ID = "1MkHviO7CsmPR65rpV3zT0wSRbVVomsc9j9vlmzc9JdE"
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be sent, without sending")
    parser.add_argument("--test-to", metavar="ADDRESS",
                        help="send every reminder to ADDRESS instead")
    return parser.parse_args()


def main():
    args = parse_args()

    # Fetch the live schedule and the email list
    df = pd.read_csv(url)
    emails = pd.read_csv("members.csv").set_index("Name")["Email"].to_dict()

    # Calculate the date string for the upcoming Monday
    today = datetime.now()
    next_monday = today + timedelta(days=(7 - today.weekday() + 0) % 7)
    monday_str = next_monday.strftime("%d-%b").lstrip("0")

    # Find presenters scheduled for that specific Monday
    presenters = []
    meeting_cancelled = False

    for idx, row in df.iterrows():
        if row["Date"] == monday_str:
            # Check if the notes column contains 'cancel'
            if 'cancel' in str(row.get('Notes', '')).lower():
                meeting_cancelled = True
                break

            for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
                if pd.notna(row[slot]) and str(row[slot]).strip() != "":
                    presenters.append(str(row[slot]).strip())

    if meeting_cancelled:
        print(f"Meeting on {monday_str} is marked as cancelled. Skipping reminders.")
        return 0
    if not presenters:
        print(f"No presenters found for {monday_str}.")
        return 0

    # Preserve slot order but drop repeats, so nobody gets two reminders.
    unique_presenters = list(dict.fromkeys(presenters))
    recipients = [(p, emails[p]) for p in unique_presenters if emails.get(p)]
    unreachable = [p for p in unique_presenters if not emails.get(p)]

    if unreachable:
        print(f"WARNING: no email on file for {', '.join(unreachable)} - not reminded.")
    if not recipients:
        return 0

    login_user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or login_user
    reply_to = os.environ.get("REPLY_TO")
    host = os.environ.get("SMTP_HOST") or SMTP_HOST
    port = int(os.environ.get("SMTP_PORT") or SMTP_PORT)
    security = (os.environ.get("SMTP_SECURITY") or "ssl").lower()

    if not sender and not args.dry_run:
        print("ERROR: no sender address. Set SMTP_FROM (or SMTP_USER).")
        return 1

    # Readable date for the body; monday_str stays the sheet's own format.
    meeting_date = next_monday.strftime("%A %d %B").replace(" 0", " ")

    messages = []
    for name, address in recipients:
        others = [p for p in unique_presenters if p != name]
        if others:
            co_text = f"You are presenting alongside {join_names(others)}."
        else:
            co_text = "You are the only presenter scheduled for that meeting."

        text_body = (
            f"Hello {name},\n\n"
            f"This is a reminder that you are scheduled to present at the "
            f"Tumor Immunology meeting on {meeting_date}.\n\n"
            f"{co_text}\n\n"
            f"The full schedule is here:\n"
            f"{SCHEDULE_URL}\n\n"
            f"Best,\n"
            f"Vinicio\n"
        )

        html_body = f"""\
<html>
  <body>
    <p>Hello {name},</p>
    <p>This is a reminder that you are scheduled to present at the
       Tumor Immunology meeting on <b>{meeting_date}</b>.</p>
    <p>{co_text}</p>
    <p>The full schedule is here:<br>
       <a href="{SCHEDULE_URL}">{SCHEDULE_URL}</a></p>
    <p>Best,<br>Vinicio</p>
  </body>
</html>
"""

        subject = f"TI meeting: you are presenting on {meeting_date}"
        if args.test_to:
            # Keep the real presenter's greeting so the test shows exactly
            # what each person would get; only the destination changes.
            print(f"TEST: reminder for {name} <{address}> goes to {args.test_to}")
            address = args.test_to
            subject = f"[TEST] {subject}"

        messages.append(
            build_message(
                sender=sender or "not-configured@example.invalid",
                recipient=address,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                reply_to=reply_to,
            )
        )

    if args.dry_run:
        print(f"DRY RUN: would send {len(messages)} reminder(s) for {monday_str} "
              f"via {host}:{port} ({security}) from {sender or '(no sender set)'}:")
        for msg in messages:
            print(f"  To: {msg['To']} | Subject: {msg['Subject']}")
        print("\n--- first message, plain-text part ---")
        print(messages[0].get_body(("plain",)).get_content())
        return 0

    try:
        sent, failures = send_messages(login_user, password, messages,
                                       host=host, port=port, security=security)
    except Exception as e:
        print(f"Failed to send email via {host}:{port} ({security}): {e}")
        return 1

    for address in sent:
        print(f"Reminder sent to {address}")
    for address, error in failures:
        print(f"Failed to send to {address}: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
