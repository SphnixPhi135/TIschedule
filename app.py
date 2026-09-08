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
    "Marjolein": {"bg": "#D81B60", "text": "white"}  # New Group
}

PRESENTERS = {
    "Yvette": ["Shabnam", "Sofia", "Georgia", "Emma", "Vinicio", "Roos", "Mostafa", "Ken"],
    "Juan": ["Maartje", "Ming", "Konrad", "Leo"],
    "Sandra": ["Remi", "Stan", "Lisi"],
    "Joke": ["Hendrik", "Negisa", "Noah", "Caroline"],
    "Febe": ["Sofie", "XiaoFei", "Wies", "Maud", "Angela"],
    "Jan": ["Niamh"],
    "Tanja": ["Nora"],
    "Lotte": ["Lotte"],
    "Marjolein": ["Irene", "Leoni", "Janneke"]
}

TECHNICIANS = {
    "Yvette": ["Fabrizio", "Laura", "Sanne", "Katarina", "Li", "Babet", "Megan"],
    "Juan": ["Marlous"],
    "Sandra": ["Alba"],
    "Joke": ["Joeke"],
    "Febe": ["Susan", "Meggy"],
    "Jan": ["Daan"],
    "Tanja": ["Linda"],
    "Lotte": [],
    "Marjolein": ["Kiki", "Richard"]
}

# Dynamically merge lists for the table styling function
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
    # ttl=0 ensures it fetches the latest live data directly from Google Sheets
    df = conn.read(worksheet="Schedule", ttl=0)
    # Clean up any blank rows from the spreadsheet
    df = df.dropna(how='all')
    return df

def save_data(df):
    # Overwrite the Google Sheet with the new swapped data
    conn.update(worksheet="Schedule", data=df)
    st.session_state.df = df

def send_swap_email(person_a, person_b, date_a, date_b):
    try:
        sender = st.secrets.get("SMTP_USER")
        password = st.secrets.get("SMTP_PASSWORD")
        if not sender or not password:
            st.warning("Email credentials not fully configured in Secrets. Swap complete, but email skipped.")
            return
    except Exception:
        st.warning("Secrets formatting error. Swap complete, but email skipped.")
        return

    email_a = EMAIL_DICT.get(person_a)
    email_b = EMAIL_DICT.get(person_b)
    
    if not email_a or not email_b:
        st.warning("Could not find email addresses for one or both members. Swap completed, but email skipped.")
        return

    msg = MIMEText(f"Hello {person_a} and {person_b},\n\nYour presentation slots have been successfully swapped.\n\n{person_a} is now presenting on: {date_b}\n{person_b} is now presenting on: {date_a}\n\nPlease check the schedule for details.")
    msg['Subject'] = 'Meeting Schedule Swap Confirmation'
    msg['From'] = sender
    msg['To'] = f"{email_a}, {email_b}"

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# --- INITIALIZE DATA ---
if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

st.title("📅 Group Meeting Presentation Schedule")

# --- 2. PI LEGEND & ROSTER ---
st.subheader("🔬 PI Groups & Lab Roster")
with st.expander("View Color Legend, Presenters, and Technicians", expanded=False):
    pi_names = list(PI_COLORS.keys())
    # Create an organized grid of 3 columns
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
                    
                    if pres:
                        st.markdown("**Presenters:**\n" + "\n".join([f"- {p}" for p in pres]))
                    if tech:
                        st.markdown("**Technicians:**\n" + "\n".join([f"- {t}" for t in tech]))
                    
                    st.write("") # Add some vertical spacing

# --- 3. SWAP TOOL ---
st.subheader("🔄 Swap Presentation Slots")
with st.expander("Click here to swap slots with another member", expanded=False):
    slot_entries = []
    for idx, row in df.iterrows():
        # Ensure we are looking at valid dates
        if pd.notna(row.get('Date')):
            for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
                presenter = str(row.get(slot, "")).strip()
                if presenter and presenter != "nan" and presenter != "None":
                    label = f"{row['Date']} - {slot}: {presenter}"
                    slot_entries.append({"label": label, "idx": idx, "slot": slot, "person": presenter, "date": row['Date']})
    
    entry_labels = [e["label"] for e in slot_entries]
    
    if entry_labels:
        col_a, col_b = st.columns(2)
        with col_a: choice_a = st.selectbox("Slot 1 (Your current slot):", options=entry_labels, index=0)
        with col_b: choice_b = st.selectbox("Slot 2 (Slot to swap with):", options=entry_labels, index=1 if len(entry_labels)>1 else 0)
            
        if st.button("Confirm Swap", type="primary"):
            if choice_a != choice_b:
                item_a = next(e for e in slot_entries if e["label"] == choice_a)
                item_b = next(e for e in slot_entries if e["label"] == choice_b)
                
                # Execute the swap in the dataframe
                df.at[item_a["idx"], item_a["slot"]] = item_b["person"]
                df.at[item_b["idx"], item_b["slot"]] = item_a["person"]
                save_data(df)
                
                # Send confirmation email
                send_swap_email(item_a['person'], item_b['person'], item_a['date'], item_b['date'])
                
                st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully! Email sent.")
                st.rerun()
            else:
                st.warning("Please choose two different slots to swap.")
    else:
        st.info("No schedule data available. Please ensure your Google Sheet is correctly formatted and populated.")

# --- 4. STYLED TABLE ---
st.subheader("📋 Current Schedule")

def style_cells(val):
    pi = MEMBER_PI_MAP.get(str(val).strip())
    if pi:
        bg = PI_COLORS[pi]["bg"]
        text = PI_COLORS[pi]["text"]
        return f"background-color: {bg}; color: {text}; font-weight: 500;"
    return ""

try:
    styled_df = df.style.map(style_cells, subset=["Slot 1", "Slot 2", "Slot 3", "Slot 4"])
except AttributeError:
    styled_df = df.style.applymap(style_cells, subset=["Slot 1", "Slot 2", "Slot 3", "Slot 4"])

st.dataframe(styled_df, hide_index=True, use_container_width=True)
