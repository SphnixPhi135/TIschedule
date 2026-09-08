import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Lab Meeting Schedule", layout="wide")

MEMBERS_FILE = "members.csv"

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
    "Febe": ["Sofie", "XiaoFei", "Wies", "Maud", "Angela"],
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
        df_emails = pd.read_csv(MEMBERS_FILE)
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

    msg = MIMEText(f"Hello {person_a} and {person_b},\n\nYour presentation slots have been successfully swapped.\n\n{person_a} is now presenting on: {date_b}\n{person_b} is now presenting on: {date_a}\n\nPlease check the schedule for details.")
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

    msg = MIMEText(f"Hello {old_person} and {new_person},\n\nThe schedule has been updated.\n\n{new_person} will now be presenting on {date} instead of {old_person}.\n\nPlease check the schedule for details.")
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

st.title("📅 Group Meeting Presentation Schedule")

# --- 2. PI LEGEND & ROSTER ---
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

# --- 3. SWAP OR REASSIGN TOOL ---
st.subheader("🔄 Swap or Reassign Presentation Slots")
with st.expander("Click here to change a slot or swap with another member", expanded=False):
    slot_entries = []
    scheduled_people = []
    
    # 1. Identify everyone currently on the schedule
    for idx, row in df.iterrows():
        if pd.notna(row.get('Date')):
            for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
                presenter = str(row.get(slot, "")).strip()
                if presenter and presenter != "nan" and presenter != "None":
                    label = f"{row['Date']} - {slot}: {presenter}"
                    slot_entries.append({"label": label, "idx": idx, "slot": slot, "person": presenter, "date": row['Date']})
                    scheduled_people.append(presenter)
    
    # 2. Build the lists for the dropdown menus
    entry_labels = [e["label"] for e in slot_entries]
    all_members = list(MEMBER_PI_MAP.keys())
    unscheduled_members = [m for m in all_members if m not in scheduled_people]
    unscheduled_labels = [f"Unscheduled: {m}" for m in sorted(unscheduled_members)]
    
    # Target options include both existing slots AND unscheduled members
    target_options = entry_labels + unscheduled_labels
    
    if entry_labels:
        col_a, col_b = st.columns(2)
        with col_a: choice_a = st.selectbox("Select slot to change:", options=entry_labels, index=0)
        with col_b: choice_b = st.selectbox("Swap with slot OR Reassign to:", options=target_options, index=1 if len(entry_labels)>1 else 0)
            
        if st.button("Confirm Change", type="primary"):
            if choice_a == choice_b:
                st.warning("Please choose a different target to make a change.")
            else:
                item_a = next(e for e in slot_entries if e["label"] == choice_a)
                
                if choice_b.startswith("Unscheduled: "):
                    # Handle 1-way REPLACEMENT
                    new_person = choice_b.replace("Unscheduled: ", "")
                    df.at[item_a["idx"], item_a["slot"]] = new_person
                    save_data(df)
                    send_replacement_email(item_a['person'], new_person, item_a['date'])
                    
                    st.success(f"Reassigned slot from **{item_a['person']}** to **{new_person}** successfully! Email sent.")
                    st.rerun()
                else:
                    # Handle 2-way SWAP
                    item_b = next(e for e in slot_entries if e["label"] == choice_b)
                    df.at[item_a["idx"], item_a["slot"]] = item_b["person"]
                    df.at[item_b["idx"], item_b["slot"]] = item_a["person"]
                    save_data(df)
                    send_swap_email(item_a['person'], item_b['person'], item_a['date'], item_b['date'])
                    
                    st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully! Email sent.")
                    st.rerun()
    else:
        st.info("No schedule data available.")

# --- 4. STYLED TABLE ---
st.subheader("📋 Current Schedule")

# 1. Create a display copy so we don't alter the background swapping logic
display_df = df.copy()

# 2. Format the Week column to be a clean integer (removes the .0000)
display_df["Week"] = pd.to_numeric(display_df["Week"], errors='coerce').fillna(0).astype(int).astype(str).replace("0", "")

# 3. Rename the columns directly in the display dataframe
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

# 4. Apply styles pointing to the newly renamed columns
try:
    styled_df = display_df.style.map(style_cells, subset=["Slot 1 (30 min)", "Slot 2 (5 min)", "Slot 3 (5 min)", "Slot 4 (5 min)"])
except AttributeError:
    styled_df = display_df.style.applymap(style_cells, subset=["Slot 1 (30 min)", "Slot 2 (5 min)", "Slot 3 (5 min)", "Slot 4 (5 min)"])

# 5. Use st.table() to create a fully locked, unmovable display
st.table(styled_df)
