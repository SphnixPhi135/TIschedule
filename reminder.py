import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os

# Your specific Google Sheet ID
SHEET_ID = "1MkHviO7CsmPR65rpV3zT0wSRbVVomsc9j9vlmzc9JdE" 
url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

# Fetch the live schedule and the email list
df = pd.read_csv(url)
emails = pd.read_csv("members.csv").set_index("Name")["Email"].to_dict()

# Calculate the date string for the upcoming Monday
today = datetime.now()
next_monday = today + timedelta(days=(7 - today.weekday() + 0) % 7)
monday_str = next_monday.strftime("%d-%b").lstrip("0") # Formats to match "14-Sep" etc.

# Find presenters scheduled for that specific Monday
presenters = []
for idx, row in df.iterrows():
    if row["Date"] == monday_str:
        for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
            if pd.notna(row[slot]) and str(row[slot]).strip() != "":
                presenters.append(str(row[slot]).strip())

# If there are presenters, prepare and send the email
if presenters:
    recipient_emails = [emails.get(p) for p in presenters if emails.get(p)]
    
    if recipient_emails:
        sender = os.environ.get("SMTP_USER")
        password = os.environ.get("SMTP_PASSWORD")
        
        msg = MIMEText(f"Hello,\n\nThis is a friendly reminder that you are scheduled to present at the group meeting this coming Monday ({monday_str}).\n\nBest,\nVinicio")
        msg['Subject'] = 'Upcoming Presentation Reminder'
        msg['From'] = sender
        msg['To'] = ", ".join(recipient_emails)

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender, password)
                server.send_message(msg)
            print(f"Successfully sent reminder to {recipient_emails}")
        except Exception as e:
            print(f"Failed to send email: {e}")
