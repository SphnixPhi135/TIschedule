"""Shared email helpers for the TI meeting schedule.

Standard library only, so both app.py (Streamlit) and reminder.py (GitHub
Actions) can use it.

The mail is sent from a gmail.com account to amsterdamumc.nl recipients, so
it is external mail arriving at a Microsoft 365 tenant. These helpers avoid
the patterns that push such mail into the junk folder:

  * one message per recipient, instead of everyone in a single To: header,
    which looks like a bulk blast (and leaks the recipient list)
  * multipart/alternative with a real plain-text part, not HTML only
  * a From display name and a Reply-To pointing at a work address
  * the schedule URL shown as visible text, not hidden behind link text

Message-ID is deliberately left unset: Gmail's submission server generates
one on a gmail.com domain, which is better than a GitHub runner hostname.
"""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr, formatdate

SCHEDULE_URL = "https://cnbxbsxr7ezak5cyfe4c5e.streamlit.app/"
SENDER_NAME = "TI Meeting Schedule"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

# Used when neither the REPLY_TO env var nor the Streamlit secret is set, so
# replies reach a human inside the institution rather than the Gmail sender.
DEFAULT_REPLY_TO = "v.a.melogallegos@amsterdamumc.nl"


def join_names(names):
    """Format a list of names for prose: 'A', 'A and B', 'A, B and C'."""
    names = list(names)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def build_message(sender, recipient, subject, text_body, html_body, reply_to=None):
    """Build one multipart/alternative message addressed to a single person."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((SENDER_NAME, sender))
    msg["To"] = recipient
    msg["Reply-To"] = reply_to or DEFAULT_REPLY_TO
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def send_messages(sender, password, messages):
    """Send each message over one SMTP connection.

    Returns (sent_addresses, failures), where failures is a list of
    (address, error) pairs. A failure for one recipient does not stop the
    rest. Raises only if the connection or login itself fails.
    """
    sent, failures = [], []
    if not messages:
        return sent, failures

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(sender, password)
        for msg in messages:
            address = msg["To"]
            try:
                server.send_message(msg)
                sent.append(address)
            except smtplib.SMTPException as exc:
                failures.append((address, str(exc)))
    return sent, failures
