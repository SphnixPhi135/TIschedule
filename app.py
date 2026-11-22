import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import date, datetime

from calendar_export import build_ics, infer_dates, people_with_upcoming_talks, upcoming_talks
from mailer import SCHEDULE_URL, build_message, send_messages

st.set_page_config(page_title="Tumor Immunology meeting schedule", page_icon="🦠", layout="wide")

# --- HIDE STREAMLIT BRANDING & FLOATING BADGES ---
hide_elements_css = """
<style>
    /* Hide the top right GitHub menu */
    [data-testid="stToolbar"] {visibility: hidden !important;}
    /* Hide the default Made with Streamlit footer */
    footer {visibility: hidden !important;}
    /* Hide the Streamlit Cloud floating developer badge */
    .viewerBadge_container {display: none !important;}
    .viewerBadge_link {display: none !important;}
</style>
"""
st.markdown(hide_elements_css, unsafe_allow_html=True)


# --- 1. COLOR MAPPINGS & LAB ROSTER ---
PI_COLORS = {
    "Yvette": {"bg": "#5B9BD5", "text": "white"},
    "Juan": {"bg": "#C00000", "text": "white"},
    "Sandra": {"bg": "#ED7D31", "text": "white"},
    "Joke": {"bg": "#FFC000", "text": "black"},
    "Febe": {"bg": "#70AD47", "text": "white"},
    "Jan": {"bg": "#996600", "text": "white"},
    "Reina": {"bg": "#7030A0", "text": "white"},
    "Marjolein": {"bg": "#D81B60", "text": "white"},
    "Krijn": {"bg": "#1F4E79", "text": "white"}
}

PRESENTERS = {
    "Yvette": ["Sofia", "Georgia", "Emma", "Vinicio", "Roos", "Mostafa", "Megan"],
    "Juan": ["Ming", "Konrad", "Leo"],
    "Sandra": ["Remi", "Stan", "Lisi"],
    "Joke": ["Hendrik", "Negisa", "Noah", "Caroline"],
    "Febe": ["Sofie", "Wies", "Maud"],
    "Jan": ["Niamh"],
    "Reina": ["Lotte", "Ola"],
    "Marjolein": ["Irene", "Leoni", "Janneke"],
    "Krijn": ["Marije"]
}

TECHNICIANS = {
    "Yvette": ["Laura", "Katarina"],
    "Juan": ["Marlous"],
    "Sandra": ["Alba"],
    "Joke": ["Joeke"],
    "Febe": ["Susan", "Meggy"],
    "Jan": ["Daan"],
    "Reina": [],
    "Marjolein": ["Kiki", "Richard"]
}

MEMBER_PI_MAP = {}
for pi, members in PRESENTERS.items():
    for m in members: MEMBER_PI_MAP[m] = pi
for pi, members in TECHNICIANS.items():
    for m in members: MEMBER_PI_MAP[m] = pi

@st.cache_data
def load_emails():
    try:
        df_emails = pd.read_csv("members.csv") # Explicitly referencing members.csv
        return dict(zip(df_emails.Name, df_emails.Email))
    except FileNotFoundError:
        return {}

EMAIL_DICT = load_emails()

# --- CONNECT TO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    df = conn.read(worksheet="Schedule", ttl=0)
    df = df.dropna(how='all')
    return df

def save_data(df):
    conn.update(worksheet="Schedule", data=df)
    st.session_state.df = df


SCHEDULE_CHANGED = ("The schedule changed since you opened this page, so nothing was saved. "
                    "Reload the page and try again.")


def apply_changes(changes):
    """Apply [(date, slot, expected_person, new_person)] to a fresh copy of the sheet.

    The page keeps the schedule it loaded when it was opened. Saving that copy
    would undo any edit made since, so re-read the sheet, check each slot
    still holds who the page showed, and only then write. Returns False (and
    saves nothing) if any slot changed meanwhile.
    """
    fresh = load_data()
    dates = fresh["Date"].astype(str).str.strip()
    edits = []
    for date_str, slot, expected, new_person in changes:
        rows = fresh.index[dates == date_str]
        if len(rows) != 1 or str(fresh.at[rows[0], slot]).strip() != expected:
            st.session_state.df = fresh
            return False
        edits.append((rows[0], slot, new_person))
    for row, slot, new_person in edits:
        fresh.at[row, slot] = new_person
    save_data(fresh)
    return True

# --- EMAILS ---
def _smtp_credentials():
    """Return (sender, password, reply_to) from Streamlit secrets, or None."""
    try:
        sender = st.secrets.get("SMTP_USER")
        password = st.secrets.get("SMTP_PASSWORD")
        reply_to = st.secrets.get("REPLY_TO")
    except Exception:
        return None
    if not sender or not password:
        return None
    return sender, password, reply_to


def _deliver(messages):
    """Send already-built messages, swallowing errors as before."""
    creds = _smtp_credentials()
    if not creds or not messages:
        return
    sender, password, _ = creds
    try:
        send_messages(sender, password, messages)
    except Exception:
        pass


def send_swap_email(person_a, person_b, date_a, date_b):
    creds = _smtp_credentials()
    if not creds:
        return
    sender, _, reply_to = creds

    email_a = EMAIL_DICT.get(person_a)
    email_b = EMAIL_DICT.get(person_b)
    if not email_a or not email_b:
        return

    messages = []
    # One personalised message each, rather than both names in a single To:.
    for name, address, own_date, other, other_date in (
        (person_a, email_a, date_b, person_b, date_a),
        (person_b, email_b, date_a, person_a, date_b),
    ):
        text_body = (
            f"Hello {name},\n\n"
            f"Your presentation slot has been swapped with {other}.\n\n"
            f"You are now presenting on {own_date}.\n"
            f"{other} is now presenting on {other_date}.\n\n"
            f"The full schedule is here:\n"
            f"{SCHEDULE_URL}\n"
        )
        html_body = f"""\
<html>
  <body>
    <p>Hello {name},</p>
    <p>Your presentation slot has been swapped with {other}.</p>
    <ul>
      <li>You are now presenting on <b>{own_date}</b></li>
      <li>{other} is now presenting on <b>{other_date}</b></li>
    </ul>
    <p>The full schedule is here:<br>
       <a href="{SCHEDULE_URL}">{SCHEDULE_URL}</a></p>
  </body>
</html>
"""
        messages.append(
            build_message(
                sender=sender,
                recipient=address,
                subject=f"TI meeting: your slot moved to {own_date}",
                text_body=text_body,
                html_body=html_body,
                reply_to=reply_to,
            )
        )

    _deliver(messages)


def send_replacement_email(old_person, new_person, date):
    creds = _smtp_credentials()
    if not creds:
        return
    sender, _, reply_to = creds

    email_old = EMAIL_DICT.get(old_person)
    email_new = EMAIL_DICT.get(new_person)
    if not email_old or not email_new:
        return

    messages = []
    for name, address, intro in (
        (
            new_person,
            email_new,
            f"You are now scheduled to present on {date}, "
            f"taking over from {old_person}.",
        ),
        (
            old_person,
            email_old,
            f"You are no longer scheduled to present on {date}. "
            f"{new_person} will present instead.",
        ),
    ):
        text_body = (
            f"Hello {name},\n\n"
            f"The schedule has been updated.\n\n"
            f"{intro}\n\n"
            f"The full schedule is here:\n"
            f"{SCHEDULE_URL}\n"
        )
        html_body = f"""\
<html>
  <body>
    <p>Hello {name},</p>
    <p>The schedule has been updated.</p>
    <p>{intro}</p>
    <p>The full schedule is here:<br>
       <a href="{SCHEDULE_URL}">{SCHEDULE_URL}</a></p>
  </body>
</html>
"""
        messages.append(
            build_message(
                sender=sender,
                recipient=address,
                subject=f"TI meeting: schedule change for {date}",
                text_body=text_body,
                html_body=html_body,
                reply_to=reply_to,
            )
        )

    _deliver(messages)


# --- INITIALIZE DATA ---
if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

st.title("Tumor Immunology meeting presentation schedule")
st.write("") # Small spacer

# --- 2. NEXT MEETING HIGHLIGHT BANNER ---
current_date = datetime.now().date()
# The sheet shows dates without a year ("11-Jan"). Work the year out from
# row order, so a schedule that runs past New Year is read correctly.
row_dates = dict(zip(df.index, infer_dates(df["Date"].tolist(), current_date)))
upcoming_row = None

# Find the first row that hasn't passed yet
for idx, row in df.iterrows():
    row_date = row_dates.get(idx)
    if row_date is None or row_date < current_date:
        continue

    # Skip if meeting is cancelled
    if 'cancel' in str(row.get('Notes', '')).lower():
        continue

    # Skip rows with nobody presenting (holidays, no meeting)
    if not any(str(row.get(s, "")).strip() not in ("", "nan", "None")
               for s in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]):
        continue

    upcoming_row = row
    break

if upcoming_row is not None:
    st.markdown(f"### Next meeting: **{upcoming_row['Date']}**")
    banner_cols = st.columns(4)
    slots = ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]
    slot_titles = ["Slot 1 (30 min)", "Slot 2 (5 min)", "Slot 3 (5 min)", "Slot 4 (5 min)"]
    
    for col, slot, title in zip(banner_cols, slots, slot_titles):
        presenter = str(upcoming_row.get(slot, "")).strip()
        if presenter and presenter != "nan" and presenter != "None":
            pi = MEMBER_PI_MAP.get(presenter)
            # Use PI colors if found, otherwise default to a dark gray
            bg_color = PI_COLORS[pi]["bg"] if pi else "#444444"
            text_color = PI_COLORS[pi]["text"] if pi else "white"
            
            col.markdown(
                f'<div style="background-color: {bg_color}; color: {text_color}; '
                f'padding: 20px; border-radius: 10px; text-align: center; '
                f'box-shadow: 0px 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;">'
                f'<h3 style="margin: 0; color: {text_color}; padding-bottom: 5px;">{presenter}</h3>'
                f'<p style="margin: 0; font-size: 14px; opacity: 0.9;">{title}</p>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            col.markdown(
                f'<div style="background-color: #262730; color: #888888; '
                f'padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">'
                f'<h3 style="margin: 0; color: #888888; padding-bottom: 5px;">Empty</h3>'
                f'<p style="margin: 0; font-size: 14px; opacity: 0.7;">{title}</p>'
                f'</div>',
                unsafe_allow_html=True
            )
    st.markdown("---")

# --- 3. SWAP OR REASSIGN TOOL ---
with st.expander("Swap or reassign presentation slots", expanded=False):
    
    # 1. Parse schedule to find all valid upcoming slots
    all_slot_entries = []
    scheduled_people = set()

    for idx, row in df.iterrows():
        if pd.notna(row.get('Date')):
            date_str = str(row.get('Date', "")).strip()
            
            # DATE LOCK LOGIC
            row_date = row_dates.get(idx)
            if row_date is not None and row_date < current_date:
                continue  # Skip dates that have passed
            
            # Skip dates marked as cancelled
            if 'cancel' in str(row.get('Notes', '')).lower():
                continue
            
            for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
                presenter = str(row.get(slot, "")).strip()
                if presenter and presenter != "nan" and presenter != "None":
                    slot_display = "Slot 1 (30 min)" if slot == "Slot 1" else f"{slot} (5 min)"
                    label = f"{date_str} - {slot_display}: {presenter}"
                    
                    all_slot_entries.append({"label": label, "idx": idx, "slot": slot, "person": presenter, "date": date_str})
                    scheduled_people.add(presenter)

    if not all_slot_entries:
        st.info("No upcoming schedule data available to swap.")
    else:
        # --- STEP 1: Select Presenter ---
        sorted_presenters = sorted(list(scheduled_people))
        selected_presenter = st.selectbox("1. Select presenter to modify:", ["-- Choose a member --"] + sorted_presenters)

        if selected_presenter != "-- Choose a member --":
            
            # Find this person's specific slots
            person_slots = [e for e in all_slot_entries if e["person"] == selected_presenter]
            person_slot_labels = [e["label"] for e in person_slots]

            # --- STEP 2: Select Specific Slot ---
            selected_slot_label = st.selectbox(f"2. Select the specific slot for {selected_presenter}:", ["-- Choose a slot --"] + person_slot_labels)

            if selected_slot_label != "-- Choose a slot --":
                item_a = next(e for e in person_slots if e["label"] == selected_slot_label)

                # --- STEP 3: Choose Action ---
                action = st.radio("3. What would you like to do?", ["Swap with another member", "Reassign to someone else"])

                # --- STEP 4a: Swap Logic ---
                if action == "Swap with another member":
                    # Show all slots EXCEPT the one currently selected
                    other_slots = [e["label"] for e in all_slot_entries if e["label"] != selected_slot_label]
                    
                    if not other_slots:
                        st.warning("There are no other scheduled members to swap with.")
                    else:
                        choice_b = st.selectbox("4. Select the slot to swap with:", other_slots)

                        if st.button("Confirm swap", type="primary"):
                            item_b = next(e for e in all_slot_entries if e["label"] == choice_b)

                            if apply_changes([
                                (item_a["date"], item_a["slot"], item_a["person"], item_b["person"]),
                                (item_b["date"], item_b["slot"], item_b["person"], item_a["person"]),
                            ]):
                                send_swap_email(item_a['person'], item_b['person'], item_a['date'], item_b['date'])
                                st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully! Email sent.")
                                st.rerun()
                            else:
                                st.error(SCHEDULE_CHANGED)

                # --- STEP 4b: Reassign Logic ---
                elif action == "Reassign to someone else":
                    # Anyone can take the slot, including people who already
                    # have talks, except those already presenting that day.
                    presenting_that_day = {e["person"] for e in all_slot_entries
                                           if e["idx"] == item_a["idx"]}
                    candidates = sorted({m for members in PRESENTERS.values() for m in members}
                                        - presenting_that_day)

                    if not candidates:
                        st.warning("There is nobody else to reassign this slot to.")
                    else:
                        choice_b = st.selectbox("4. Select the new presenter:", candidates)

                        if st.button("Confirm reassignment", type="primary"):
                            new_person = choice_b

                            if apply_changes([(item_a["date"], item_a["slot"], item_a["person"], new_person)]):
                                send_replacement_email(item_a['person'], new_person, item_a['date'])
                                st.success(f"Reassigned slot from **{item_a['person']}** to **{new_person}** successfully! Email sent.")
                                st.rerun()
                            else:
                                st.error(SCHEDULE_CHANGED)

# --- 4. ADD TO CALENDAR ---
with st.expander("Add my presentations to my calendar", expanded=False):
    calendar_rows = df.to_dict("records")
    calendar_today = datetime.now().date()
    calendar_people = people_with_upcoming_talks(calendar_rows, calendar_today)

    if not calendar_people:
        st.write("There are no upcoming presentations in the schedule.")
    else:
        calendar_person = st.selectbox(
            "Choose your name:",
            ["-- Choose a member --"] + calendar_people,
            key="calendar_person",
        )
        if calendar_person != "-- Choose a member --":
            talks = upcoming_talks(calendar_rows, calendar_person, calendar_today)
            st.markdown("\n".join(
                f"- {date.strftime('%A %d %B %Y')}: {label}" for date, label, _ in talks
            ))
            st.download_button(
                "Download calendar file (.ics)",
                data=build_ics(calendar_person, talks).encode("utf-8"),
                file_name=f"TI_meeting_{calendar_person.replace(' ', '_')}.ics",
                mime="text/calendar",
                key="calendar_download",
            )

# --- 5. STYLED TABLE ---
SLOT_COLUMNS = ["Slot 1 (30 min)", "Slot 2 (5 min)", "Slot 3 (5 min)", "Slot 4 (5 min)"]


def style_cells(val):
    pi = MEMBER_PI_MAP.get(str(val).strip())
    if pi:
        bg = PI_COLORS[pi]["bg"]
        text = PI_COLORS[pi]["text"]
        return f"background-color: {bg}; color: {text}; font-weight: 500;"
    return ""


def styled_schedule(source_df):
    """Format a schedule tab for display: tidy columns, colour by PI group."""
    display_df = source_df.reset_index(drop=True)

    display_df["Week"] = pd.to_numeric(display_df["Week"], errors='coerce').fillna(0).astype(int).astype(str).replace("0", "")
    if "Notes" in display_df.columns:
        display_df["Notes"] = display_df["Notes"].fillna("").astype(str).replace(["nan", "None"], "")

    display_df = display_df.rename(columns={
        "Slot 1": "Slot 1 (30 min)",
        "Slot 2": "Slot 2 (5 min)",
        "Slot 3": "Slot 3 (5 min)",
        "Slot 4": "Slot 4 (5 min)"
    })

    # Reorder the columns; only add 'Notes' if it exists in the sheet
    column_order = ["Week", "Date"] + SLOT_COLUMNS
    if "Notes" in display_df.columns:
        column_order.append("Notes")
    display_df = display_df[column_order]

    try:
        return display_df.style.map(style_cells, subset=SLOT_COLUMNS)
    except AttributeError:
        return display_df.style.applymap(style_cells, subset=SLOT_COLUMNS)


# A meeting moves from the current schedule to "Past schedules" the day
# after it takes place. The sheet itself is not changed.
past_rows = [idx for idx in df.index
             if row_dates.get(idx) is not None and row_dates[idx] < current_date]

st.subheader("Current schedule")
upcoming_df = df.drop(index=past_rows)
if upcoming_df.empty:
    st.write("There are no upcoming meetings in the current schedule.")
else:
    st.table(styled_schedule(upcoming_df))

# --- 6. PAST SCHEDULES ---
# Past schedules are grouped by semester: Spring is January to July, Fall is
# August to December. Weeks that have passed in the current schedule appear
# here on their own. Older schedules are tabs in the same spreadsheet; when
# one is archived, add its tab name here (named like "Fall 2026 (archive)").
ARCHIVE_TABS = ["Fall 2026 (archive)"]
SEASONS = ("Spring", "Fall")


def semester_label(meeting_date):
    season = "Spring" if meeting_date.month <= 7 else "Fall"
    return f"{season} {meeting_date.year}"


def semester_sort_key(label):
    """(year, season) so labels sort in time order; unknown labels last."""
    try:
        season, year = label.split()
        return (int(year), SEASONS.index(season))
    except ValueError:
        return (0, 0)


def semester_reference_date(label):
    """A date inside the semester, used to work out the year of its rows."""
    season, year = label.split()
    if season not in SEASONS:
        raise ValueError(label)
    return date(int(year), 4, 1) if season == "Spring" else date(int(year), 10, 1)


past_by_semester = {}
for idx in past_rows:
    past_by_semester.setdefault(semester_label(row_dates[idx]), []).append(idx)
current_schedule_dates = {d for d in row_dates.values() if d is not None}
archive_labels = {tab.replace(" (archive)", ""): tab for tab in ARCHIVE_TABS}
past_labels = sorted(set(archive_labels) | set(past_by_semester),
                     key=semester_sort_key, reverse=True)

with st.expander("Past schedules", expanded=False):
    if not past_labels:
        st.write("There are no past meetings yet.")
    else:
        if len(past_labels) == 1:
            past_label = past_labels[0]
        else:
            past_label = st.selectbox("Choose a schedule:", past_labels, key="archive_tab")

        parts = []   # (rows, their dates)
        if past_label in archive_labels:
            try:
                archive_df = conn.read(worksheet=archive_labels[past_label], ttl=600)
                archive_df = archive_df.dropna(how='all')
            except Exception:
                archive_df = None

            if archive_df is None or archive_df.empty:
                st.write(f"The {past_label} schedule could not be loaded.")
            else:
                try:
                    reference = semester_reference_date(past_label)
                except ValueError:
                    reference = current_date
                archive_dates = infer_dates(archive_df["Date"].tolist(), reference)
                # Keep only meetings that have passed. A date that is also in
                # the current schedule is shown from there instead, since
                # that is the version that has been kept up to date.
                keep = [d is None or (d < current_date and d not in current_schedule_dates)
                        for d in archive_dates]
                parts.append((archive_df[keep],
                              [d for d, k in zip(archive_dates, keep) if k]))

        if past_label in past_by_semester:
            idxs = past_by_semester[past_label]
            parts.append((df.loc[idxs], [row_dates[i] for i in idxs]))

        if parts:
            past_df = pd.concat([rows for rows, _ in parts], ignore_index=True)
            past_df["_date"] = [d for _, dates in parts for d in dates]
            past_df = (past_df.sort_values("_date", kind="stable", na_position="last")
                              .drop(columns="_date"))
            if past_df.empty:
                st.write(f"There are no past meetings in {past_label} yet.")
            else:
                st.markdown(f"**{past_label}**")
                st.table(styled_schedule(past_df))

# --- 7. PIs AND MEMBERS ---
with st.expander("PIs and members", expanded=False):
    pi_names = list(PI_COLORS.keys())
    for i in range(0, len(pi_names), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(pi_names):
                pi = pi_names[i + j]
                colors = PI_COLORS[pi]
                with cols[j]:
                    st.markdown(
                        f'<div style="background-color: {colors["bg"]}; color: {colors["text"]}; '
                        f'padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 10px;">'
                        f'{pi}</div>',
                        unsafe_allow_html=True
                    )
                    pres = PRESENTERS.get(pi, [])
                    tech = TECHNICIANS.get(pi, [])
                    if pres: st.markdown("**Presenters:**\n" + "\n".join([f"- {p}" for p in pres]))
                    if tech: st.markdown("**Technicians:**\n" + "\n".join([f"- {t}" for t in tech]))
                    st.write("")
