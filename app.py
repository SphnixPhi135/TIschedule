import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

st.set_page_config(page_title="Tumor Immunology Meeting Schedule", page_icon="🦠", layout="wide")

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
    "Tanja": {"bg": "#00B0F0", "text": "black"},
    "Lotte": {"bg": "#7030A0", "text": "white"},
    "Marjolein": {"bg": "#D81B60", "text": "white"}
}

PRESENTERS = {
    "Yvette": ["Sofia", "Georgia", "Emma", "Vinicio", "Roos", "Mostafa"],
    "Juan": ["Ming", "Konrad", "Leo"],
    "Sandra": ["Remi", "Stan", "Lisi"],
    "Joke": ["Hendrik", "Negisa", "Noah", "Caroline"],
    "Febe": ["Sofie", "Wies", "Maud"],
    "Jan": ["Niamh"],
    "Tanja": ["Nora"],
    "Lotte": ["Lotte"],
    "Marjolein": ["Irene", "Leoni", "Janneke"]
}

TECHNICIANS = {
    "Yvette": ["Laura", "Katarina", "Megan"],
    "Juan": ["Marlous"],
    "Sandra": ["Alba"],
    "Joke": ["Joeke"],
    "Febe": ["Susan", "Meggy"],
    "Jan": ["Daan"],
    "Tanja": ["Linda"],
    "Lotte": [],
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

# --- EMAILS ---
def send_swap_email(person_a, person_b, date_a, date_b):
    try:
        sender = st.secrets.get("SMTP_USER")
        password = st.secrets.get("SMTP_PASSWORD")
        if not sender or not password: return
    except Exception: return

    email_a = EMAIL_DICT.get(person_a)
    email_b = EMAIL_DICT.get(person_b)
    if not email_a or not email_b: return

    html_content = f"""
    <html>
      <body>
        <p>Hello {person_a} and {person_b},</p>
        <p>Your presentation slots have been successfully swapped.</p>
        <ul>
          <li><b>{person_a}</b> is now presenting on: {date_b}</li>
          <li><b>{person_b}</b> is now presenting on: {date_a}</li>
        </ul>
        <p>Please check the <a href="https://cnbxbsxr7ezak5cyfe4c5e.streamlit.app/">schedule</a> for details.</p>
      </body>
    </html>
    """
    msg = MIMEText(html_content, 'html')
    msg['Subject'] = 'Meeting Schedule Swap Confirmation'
    msg['From'] = sender
    msg['To'] = f"{email_a}, {email_b}"
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception: pass

def send_replacement_email(old_person, new_person, date):
    try:
        sender = st.secrets.get("SMTP_USER")
        password = st.secrets.get("SMTP_PASSWORD")
        if not sender or not password: return
    except Exception: return

    email_old = EMAIL_DICT.get(old_person)
    email_new = EMAIL_DICT.get(new_person)
    if not email_old or not email_new: return

    html_content = f"""
    <html>
      <body>
        <p>Hello {old_person} and {new_person},</p>
        <p>The <a href="https://cnbxbsxr7ezak5cyfe4c5e.streamlit.app/">schedule</a> has been updated.</p>
        <p><b>{new_person}</b> will now be presenting on {date} instead of {old_person}.</p>
        <p>Please check the <a href="https://cnbxbsxr7ezak5cyfe4c5e.streamlit.app/">schedule</a> for details.</p>
      </body>
    </html>
    """
    msg = MIMEText(html_content, 'html')
    msg['Subject'] = 'Meeting Schedule Reassignment'
    msg['From'] = sender
    msg['To'] = f"{email_old}, {email_new}"
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception: pass


# --- INITIALIZE DATA ---
if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

st.title("📅 Tumor Immunology Meeting Presentation Schedule")
st.write("") # Small spacer

# --- 2. NEXT MEETING HIGHLIGHT BANNER ---
current_date = datetime.now().date()
current_year = current_date.year
upcoming_row = None

# Find the first row that hasn't passed yet
for idx, row in df.iterrows():
    if pd.notna(row.get('Date')):
        date_str = str(row.get('Date', "")).strip()
        
        # Skip if meeting is cancelled
        if 'cancel' in str(row.get('Notes', '')).lower():
            continue
            
        try:
            row_date = datetime.strptime(f"{date_str}-{current_year}", "%d-%b-%Y").date()
            if row_date >= current_date:
                upcoming_row = row
                break
        except ValueError:
            pass

if upcoming_row is not None:
    st.markdown(f"### 📢 Next Meeting: **{upcoming_row['Date']}**")
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

# --- 3. PI LEGEND & ROSTER ---
st.subheader("🔬 PI Groups & Lab Roster")
with st.expander("View Color Legend, Presenters, and Technicians", expanded=False):
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

# --- 4. SWAP OR REASSIGN TOOL ---
st.subheader("🔄 Swap or Reassign Presentation Slots")
with st.expander("Click here to change a slot or swap with another member", expanded=False):
    
    # 1. Parse schedule to find all valid upcoming slots
    all_slot_entries = []
    scheduled_people = set()

    for idx, row in df.iterrows():
        if pd.notna(row.get('Date')):
            date_str = str(row.get('Date', "")).strip()
            
            # DATE LOCK LOGIC
            try:
                row_date = datetime.strptime(f"{date_str}-{current_year}", "%d-%b-%Y").date()
                if row_date < current_date:
                    continue  # Skip dates that have passed
            except ValueError:
                pass 
            
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
        selected_presenter = st.selectbox("1. Select Presenter to modify:", ["-- Choose a member --"] + sorted_presenters)

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

                        if st.button("Confirm Swap", type="primary"):
                            item_b = next(e for e in all_slot_entries if e["label"] == choice_b)
                            
                            # Execute Swap
                            df.at[item_a["idx"], item_a["slot"]] = item_b["person"]
                            df.at[item_b["idx"], item_b["slot"]] = item_a["person"]
                            save_data(df)
                            send_swap_email(item_a['person'], item_b['person'], item_a['date'], item_b['date'])
                            
                            st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully! Email sent.")
                            st.rerun()

                # --- STEP 4b: Reassign Logic ---
                elif action == "Reassign to someone else":
                    # Build list of unscheduled members
                    all_lab_members = []
                    for members in PRESENTERS.values():
                        all_lab_members.extend(members)
                        
                    unscheduled = [m for m in all_lab_members if m not in scheduled_people]
                    unscheduled_sorted = sorted(unscheduled)
                    
                    if not unscheduled_sorted:
                        st.warning("All lab members are currently scheduled.")
                    else:
                        choice_b = st.selectbox("4. Select the new presenter:", unscheduled_sorted)

                        if st.button("Confirm Reassignment", type="primary"):
                            new_person = choice_b
                            
                            # Execute Reassignment
                            df.at[item_a["idx"], item_a["slot"]] = new_person
                            save_data(df)
                            send_replacement_email(item_a['person'], new_person, item_a['date'])
                            
                            st.success(f"Reassigned slot from **{item_a['person']}** to **{new_person}** successfully! Email sent.")
                            st.rerun()

# --- 5. STYLED TABLE ---
st.subheader("📋 Current Schedule")

display_df = df.copy()

display_df["Week"] = pd.to_numeric(display_df["Week"], errors='coerce').fillna(0).astype(int).astype(str).replace("0", "")
if "Notes" in display_df.columns:
    display_df["Notes"] = display_df["Notes"].fillna("").astype(str).replace(["nan", "None"], "")

# 1. Load Pending data early so we can inject it into the main schedule
try:
    df_pending = conn.read(worksheet="Pending", ttl=0)
    df_pending = df_pending.dropna(how='all')
except Exception:
    df_pending = pd.DataFrame(columns=["Name", "Date"])

# 2. Map missed presentations by their dates
missed_mapping = {}
if not df_pending.empty:
    for idx, row in df_pending.iterrows():
        m_date = str(row.get("Date", "")).strip()
        m_name = str(row.get("Name", "")).strip()
        if m_date and m_name:
            if m_date not in missed_mapping:
                missed_mapping[m_date] = []
            missed_mapping[m_date].append(m_name)

# 3. Dynamically add the new "Missed Presentations" column to the display dataframe
display_df["Missed Presentations"] = display_df["Date"].astype(str).str.strip().apply(
    lambda d: ", ".join(missed_mapping.get(d, []))
)

display_df = display_df.rename(columns={
    "Slot 1": "Slot 1 (30 min)",
    "Slot 2": "Slot 2 (5 min)",
    "Slot 3": "Slot 3 (5 min)",
    "Slot 4": "Slot 4 (5 min)"
})

def style_cells(val):
    pi = MEMBER_PI_MAP.get(str(val).strip())
    if pi:
        bg = PI_COLORS[pi]["bg"]
        text = PI_COLORS[pi]["text"]
        return f"background-color: {bg}; color: {text}; font-weight: 500;"
    return ""

try:
    styled_df = display_df.style.map(style_cells, subset=["Slot 1 (30 min)", "Slot 2 (5 min)", "Slot 3 (5 min)", "Slot 4 (5 min)"])
except AttributeError:
    styled_df = display_df.style.applymap(style_cells, subset=["Slot 1 (30 min)", "Slot 2 (5 min)", "Slot 3 (5 min)", "Slot 4 (5 min)"])

st.table(styled_df)

# --- 6. MISSED PRESENTATIONS (PENDING FOR NEXT YEAR) ---
st.markdown("---")
st.subheader("🚩 Missed Presentations (Next Year Planning)")

# Display the running list publicly below the header
if not df_pending.empty:
    # Temporarily convert the text dates to real datetime objects for accurate sorting
    df_pending_display = df_pending.copy()
    df_pending_display['SortDate'] = pd.to_datetime(df_pending_display['Date'], errors='coerce')
    
    # Sort chronologically (earliest first/ascending)
    df_pending_display = df_pending_display.sort_values(by='SortDate', ascending=True)
    
    # Drop the temporary sorting column and clean up empty cells before displaying
    display_pending = df_pending_display.drop(columns=['SortDate']).fillna("")
    
    # Apply the PI group colors to the Name column
    def style_pending_names(val):
        pi = MEMBER_PI_MAP.get(str(val).strip())
        if pi:
            bg = PI_COLORS[pi]["bg"]
            text = PI_COLORS[pi]["text"]
            return f"background-color: {bg}; color: {text}; font-weight: 500;"
        return ""

    try:
        styled_pending = display_pending.style.map(style_pending_names, subset=["Name"])
    except AttributeError:
        styled_pending = display_pending.style.applymap(style_pending_names, subset=["Name"])
    
    # Render the styled dataframe
    st.dataframe(styled_pending, hide_index=True, use_container_width=True)
else:
    st.info("No missed presentations reported yet.")

# Admin controls locked behind a password
with st.expander("Admin: Report a missed presentation", expanded=False):
    admin_password = st.text_input("Enter Admin Password to unlock:", type="password")
    
    # Check if the entered password matches the one in Streamlit Secrets
    if admin_password == st.secrets.get("ADMIN_PASSWORD"):
        st.success("Admin controls unlocked.")
        
        # 1. Scan the schedule to find members who had a past presentation, and log their dates
        past_schedules_dict = {} 
        
        for idx, row in df.iterrows():
            if pd.notna(row.get('Date')):
                date_str = str(row.get('Date', "")).strip()
                try:
                    row_date = datetime.strptime(f"{date_str}-{current_year}", "%d-%b-%Y").date()
                    
                    # Only look at dates that have already passed or are today
                    if row_date <= current_date:
                        formatted_date = row_date.strftime("%d-%b-%Y")
                        
                        for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
                            presenter = str(row.get(slot, "")).strip()
                            if presenter and presenter not in ["nan", "None"]:
                                # Add the presenter and their specific date to the dictionary
                                if presenter not in past_schedules_dict:
                                    past_schedules_dict[presenter] = set()
                                past_schedules_dict[presenter].add(formatted_date)
                except ValueError:
                    pass
        
        if not past_schedules_dict:
            st.warning("No past scheduled presenters found in the schedule.")
        else:
            # 2. Populate dropdown ONLY with people who actually have past scheduled dates
            valid_presenters = sorted(list(past_schedules_dict.keys()))
            missed_person = st.selectbox("Select member who did not present:", ["-- Choose a member --"] + valid_presenters)
            
            # 3. Show the dates specific to that chosen person
            if missed_person != "-- Choose a member --":
                # Retrieve the dates from our dictionary and sort them (most recent first)
                past_person_dates = sorted(list(past_schedules_dict[missed_person]), key=lambda d: datetime.strptime(d, "%d-%b-%Y"), reverse=True)
                
                missed_date = st.selectbox(f"Select the missed presentation date for {missed_person}:", ["-- Choose a date --"] + past_person_dates)
                
                if st.button("Save to Pending List", type="primary"):
                    if missed_date == "-- Choose a date --":
                        st.warning("Please select a valid past date.")
                    else:
                        # Create the new entry using the selected past date
                        new_row = pd.DataFrame([{
                            "Name": missed_person, 
                            "Date": missed_date
                        }])
                        
                        # Append to existing list and save back to Google Sheets
                        updated_pending = pd.concat([df_pending, new_row], ignore_index=True)
                        conn.update(worksheet="Pending", data=updated_pending)
                        
                        st.success(f"Added **{missed_person}** on **{missed_date}** to the pending list!")
                        st.rerun()
    elif admin_password != "":
        st.error("Incorrect password.")
