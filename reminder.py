import pandas as pd
from datetime import datetime, timedelta
import os

from mailer import SCHEDULE_URL, build_message, join_names, send_messages

# Your specific Google Sheet ID
SHEET_ID = "1MkHviO7CsmPR65rpV3zT0wSRbVVomsc9j9vlmzc9JdE" 
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

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

# Logic to send or skip the email
if meeting_cancelled:
    print(f"Meeting on {monday_str} is marked as cancelled. Skipping reminders.")
elif presenters:
    # Preserve slot order but drop repeats, so nobody gets two reminders.
    unique_presenters = list(dict.fromkeys(presenters))
    recipients = [(p, emails[p]) for p in unique_presenters if emails.get(p)]
    unreachable = [p for p in unique_presenters if not emails.get(p)]

    if unreachable:
        print(f"WARNING: no email on file for {', '.join(unreachable)} - not reminded.")

    if recipients:
        sender = os.environ.get("SMTP_USER")
        password = os.environ.get("SMTP_PASSWORD")
        reply_to = os.environ.get("REPLY_TO")

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

            messages.append(
                build_message(
                    sender=sender,
                    recipient=address,
                    subject=f"TI meeting: you are presenting on {meeting_date}",
                    text_body=text_body,
                    html_body=html_body,
                    reply_to=reply_to,
                )
            )

        try:
            sent, failures = send_messages(sender, password, messages)
            for address in sent:
                print(f"Reminder sent to {address}")
            for address, error in failures:
                print(f"Failed to send to {address}: {error}")
        except Exception as e:
            print(f"Failed to send email: {e}")
else:
    print(f"No presenters found for {monday_str}.")
