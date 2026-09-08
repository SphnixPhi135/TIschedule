import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

st.set_page_config(page_title="Lab Meeting Schedule", layout="wide")

DATA_FILE = "schedule.csv"
MEMBERS_FILE = "members.csv"

# 1. COLOR MAPPINGS
PI_COLORS = {
    "Yvette": {"bg": "#5B9BD5", "text": "white"},
    "Juan": {"bg": "#C00000", "text": "white"},
    "Sandra": {"bg": "#ED7D31", "text": "white"},
    "Joke": {"bg": "#FFC000", "text": "black"},
    "Febe": {"bg": "#70AD47", "text": "white"},
    "Jan": {"bg": "#996600", "text": "white"},
    "Tanja": {"bg": "#00B0F0", "text": "black"},
    "Lotte": {"bg": "#7030A0", "text": "white"} 
}

MEMBER_PI_MAP = {
    # Yvette
    "Shabnam": "Yvette", "Sofia": "Yvette", "Georgia": "Yvette", "Emma": "Yvette", "Vinicio": "Yvette", 
    "Roos": "Yvette", "Mostafa": "Yvette", "Ken": "Yvette", "Fabrizio": "Yvette", "Laura": "Yvette", 
    "Sanne": "Yvette", "Katarina": "Yvette", "Li": "Yvette", "Babet": "Yvette", "Megan": "Yvette",
    # Juan
    "Maartje": "Juan", "Ming": "Juan", "Konrad": "Juan", "Leo": "Juan", "Marlous": "Juan",
    # Sandra
    "Remi": "Sandra", "Stan": "Sandra", "Lisi": "Sandra", "Alba": "Sandra",
    # Joke
    "Hendrik": "Joke", "Negisa": "Joke", "Noah": "Joke", "Caroline": "Joke", "Joeke": "Joke",
    # Febe
    "Sofie": "Febe", "XiaoFei": "Febe", "Wies": "Febe", "Maud": "Febe", "Angela": "Febe", 
    "Susan": "Febe", "Meggy": "Febe",
    # Jan
    "Niamh": "Jan", "Daan": "Jan",
    # Tanja
    "Nora": "Tanja", "Linda": "Tanja",
    # Lotte (from schedule visual)
    "Lotte": "Lotte"
}

@st.cache_data
def load_emails():
    try:
        df_emails = pd.read_csv(MEMBERS_FILE)
        return dict(zip(df_emails.Name, df_emails.Email))
    except FileNotFoundError:
        return {}

EMAIL_DICT = load_emails()

def send_swap_email(person_a, person_b, date_a, date_b):
    try:
        sender = st.secrets["SMTP_USER"]
        password = st.secrets["SMTP_PASSWORD"]
    except KeyError:
        st.warning("Email credentials not configured in Streamlit Secrets. Swap complete, but email skipped.")
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

def load_data():
    return pd.read_csv(DATA_FILE)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)
    st.session_state.df = df

if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

st.title("📅 Group Meeting Presentation Schedule")

# --- 2. PI COLOR LEGEND ---
st.subheader("🔬 PI Group Legend")
legend_cols = st.columns(len(PI_COLORS))
for col, (pi, colors) in zip(legend_cols, PI_COLORS.items()):
    col.markdown(
        f'<div style="background-color: {colors["bg"]}; color: {colors["text"]}; '
        f'padding: 8px; border-radius: 5px; text-align: center; font-weight: bold; margin-bottom: 20px;">'
        f'{pi}</div>',
        unsafe_allow_html=True
    )

# --- 3. SWAP TOOL ---
st.subheader("🔄 Swap Presentation Slots")
with st.expander("Click here to swap slots with another member", expanded=False):
    slot_entries = []
    for idx, row in df.iterrows():
        for slot in ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]:
            presenter = str(row[slot]).strip()
            if presenter and presenter != "nan":
                label = f"{row['Date']} - {slot}: {presenter}"
                slot_entries.append({"label": label, "idx": idx, "slot": slot, "person": presenter, "date": row['Date']})
    
    entry_labels = [e["label"] for e in slot_entries]
    
    col_a, col_b = st.columns(2)
    with col_a: choice_a = st.selectbox("Slot 1 (Your current slot):", options=entry_labels, index=0)
    with col_b: choice_b = st.selectbox("Slot 2 (Slot to swap with):", options=entry_labels, index=1 if len(entry_labels)>1 else 0)
        
    if st.button("Confirm Swap", type="primary"):
        if choice_a != choice_b:
            item_a = next(e for e in slot_entries if e["label"] == choice_a)
            item_b = next(e for e in slot_entries if e["label"] == choice_b)
            
            df.at[item_a["idx"], item_a["slot"]] = item_b["person"]
            df.at[item_b["idx"], item_b["slot"]] = item_a["person"]
            save_data(df)
            
            send_swap_email(item_a['person'], item_b['person'], item_a['date'], item_b['date'])
            
            st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully! Email sent.")
            st.rerun()

# --- 4. STYLED TABLE ---
st.subheader("📋 Current Schedule")

def style_cells(val):
    pi = MEMBER_PI_MAP.get(str(val).strip())
    if pi:
        bg = PI_COLORS[pi]["bg"]
        text = PI_COLORS[pi]["text"]
        return f"background-color: {bg}; color: {text}; font-weight: 500;"
    return ""

# Apply styles using .map (for newer pandas) or .applymap (for older pandas)
try:
    styled_df = df.style.map(style_cells, subset=["Slot 1", "Slot 2", "Slot 3", "Slot 4"])
except AttributeError:
    styled_df = df.style.applymap(style_cells, subset=["Slot 1", "Slot 2", "Slot 3", "Slot 4"])

st.dataframe(styled_df, hide_index=True, use_container_width=True)
