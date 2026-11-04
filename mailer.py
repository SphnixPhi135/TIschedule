"""Shared email helpers for the TI meeting schedule.

Standard library only, so both app.py (Streamlit) and reminder.py (GitHub
Actions) can use it.

By default mail goes out through Gmail. The Friday reminder can instead be
sent through an institutional SMTP relay (see hpc/README.md), which makes it
internal mail for amsterdamumc.nl recipients. Either way, these helpers avoid
the message-level patterns that push mail into the junk folder:

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

# How to secure the SMTP connection:
#   "ssl"      TLS from the first byte (Gmail on 465)
#   "starttls" plain connection upgraded to TLS (typically port 587 or 25)
#   "none"     no encryption (only for an internal relay that does not
#              offer STARTTLS)
SMTP_SECURITY_MODES = ("ssl", "starttls", "none")

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


def send_messages(login_user, password, messages,
                  host=SMTP_HOST, port=SMTP_PORT, security="ssl"):
    """Send each message over one SMTP connection.

    Logs in only when both login_user and password are given, so an
    institutional relay that trusts the sending machine needs neither.

    Returns (sent_addresses, failures), where failures is a list of
    (address, error) pairs. A failure for one recipient does not stop the
    rest. Raises only if the connection or login itself fails.
    """
    if security not in SMTP_SECURITY_MODES:
        raise ValueError(
            f"Unknown SMTP security mode {security!r}; "
            f"expected one of {', '.join(SMTP_SECURITY_MODES)}"
        )

    sent, failures = [], []
    if not messages:
        return sent, failures

    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port)
    else:
        server = smtplib.SMTP(host, port)

    with server:
        if security == "starttls":
            server.starttls()
        if login_user and password:
            server.login(login_user, password)
        for msg in messages:
            address = msg["To"]
            try:
                server.send_message(msg)
                sent.append(address)
            except smtplib.SMTPException as exc:
                failures.append((address, str(exc)))
    return sent, failures
