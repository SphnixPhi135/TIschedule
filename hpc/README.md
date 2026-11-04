# Sending the Friday reminders from the HPC

The reminders can be sent from the HPC through Amsterdam UMC's own mail relay,
from `v.a.melogallegos@amsterdamumc.nl`. They then arrive as internal mail,
which is far less likely to land in junk than mail from the Gmail account.

The HPC pulls the latest code from GitHub each Friday and runs
`reminder.py`. GitHub only stores the code.

Only the Friday reminders move. The swap and reassignment emails are sent by
the Streamlit app, which runs on Streamlit's servers outside the hospital
network and cannot reach the relay, so those still go out through Gmail.

## 1. Ask HPC support

Send them something like this:

> Hello,
>
> I'd like to run a small weekly script on the HPC that sends about four
> reminder emails every Friday morning to colleagues at @amsterdamumc.nl, for
> our group's meeting schedule. Could you tell me:
>
> 1. Is there an SMTP relay I can use from the HPC? What is its host name and
>    port, and does it support STARTTLS?
> 2. Can mail sent through it use my address, v.a.melogallegos@amsterdamumc.nl,
>    as the sender, so that it passes the domain's SPF/DMARC checks? If it
>    needs a login, could I get a service account rather than using my own
>    password?
> 3. Can I schedule a weekly job, with `cron` on a login node or `scrontab`?
> 4. Can that job reach the internet (HTTPS to docs.google.com and
>    github.com)? The script reads a Google Sheet and updates itself from
>    GitHub.
>
> Thank you,
> Vinicio

## 2. One-time setup on the HPC

Log in to the HPC, then:

```bash
# Get the code
git clone https://github.com/SphnixPhi135/TIschedule.git ~/TIschedule
cd ~/TIschedule

# Python with pandas (needs Python 3.9 or newer; if `python3 --version` is
# older, load a newer one first, e.g. `module load Python`)
python3 -m venv .venv
.venv/bin/pip install pandas

# Mail settings, kept outside the repository
mkdir -p ~/.config/tischedule
cp hpc/tischedule.env.example ~/.config/tischedule/env
chmod 600 ~/.config/tischedule/env
nano ~/.config/tischedule/env      # fill in SMTP_HOST etc. from HPC support
```

## 3. Test it

Nothing goes to the presenters in these two steps.

```bash
# Reads the schedule and shows what would be sent. Sends nothing.
~/TIschedule/hpc/run_reminder.sh --dry-run

# Sends every reminder to you only, with "[TEST]" in the subject.
~/TIschedule/hpc/run_reminder.sh --test-to v.a.melogallegos@amsterdamumc.nl
```

After the second command, check that the test emails arrived **in your inbox,
not junk**. That confirms the relay works and the mail counts as internal.

If there is no meeting next Monday (none scheduled, or marked cancelled),
both commands say so and send nothing. Test in a week with presenters.

## 4. Schedule it

Every Friday at 09:00 (HPC local time). Use whichever one HPC support allows.

**cron** — run `crontab -e` and add:

```
0 9 * * 5 $HOME/TIschedule/hpc/run_reminder.sh
```

**scrontab** (Slurm) — run `scrontab -e` and add:

```
#SCRON --time=00:10:00
#SCRON --job-name=ti-reminder
0 9 * * 5 $HOME/TIschedule/hpc/run_reminder.sh
```

Your cluster may also require `#SCRON --partition=...` or `#SCRON --account=...`
lines; HPC support will know.

## 5. Switch off the GitHub Action

Otherwise everyone gets two reminders. Once the test in step 3 worked, and
before the first Friday the HPC job runs:

GitHub → the TIschedule repository → **Actions** → **Send Friday Reminders**
→ **⋯** (top right) → **Disable workflow**.

This is reversible: **Enable workflow** in the same place switches the Gmail
reminders back on if the HPC ever stops working.

## Checking it worked

Scheduled runs write to `~/tischedule-reminder.log`:

```bash
tail -n 20 ~/tischedule-reminder.log
```

Each run starts with a dated `===` line and ends with
`=== finished with status 0 ===` when everything was sent. Status `1` means
something failed, and the lines above it say what.

If the HPC can't reach GitHub on a Friday, the log shows a warning and the
reminders still go out with the last copy of the code.
