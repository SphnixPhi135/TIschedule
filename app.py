import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

st.set_page_config(page_title="Tumor Immunology Meeting Schedule", layout="wide")

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
    msg['From'] = f"Vinicio Melo <{sender}>"
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
    msg['From'] = f"Vinicio Melo <{sender}>"
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
    slot_entries = []
    scheduled_people = []
    
    # 1. Identify everyone currently on the schedule
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
                    
                    slot_entries.append({"label": label, "idx": idx, "slot": slot, "person": presenter, "date": date_str})
                    scheduled_people.append(presenter)
    
    # 2. Build the lists for the dropdown menus
    entry_labels = [e["label"] for e in slot_entries]
    
    all_presenters = []
    for members in PRESENTERS.values():
        all_presenters.extend(members)
        
    unscheduled_presenters = [m for m in all_presenters if m not in scheduled_people]
    unscheduled_labels = [f"Unscheduled: {m}" for m in sorted(unscheduled_presenters)]
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
                    new_person = choice_b.replace("Unscheduled: ", "")
                    df.at[item_a["idx"], item_a["slot"]] = new_person
                    save_data(df)
                    send_replacement_email(item_a['person'], new_person, item_a['date'])
                    
                    st.success(f"Reassigned slot from **{item_a['person']}** to **{new_person}** successfully! Email sent.")
                    st.rerun()
                else:
                    item_b = next(e for e in slot_entries if e["label"] == choice_b)
                    df.at[item_a["idx"], item_a["slot"]] = item_b["person"]
                    df.at[item_b["idx"], item_b["slot"]] = item_a["person"]
                    save_data(df)
                    send_swap_email(item_a['person'], item_b['person'], item_a['date'], item_b['date'])
                    
                    st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully! Email sent.")
                    st.rerun()
    else:
        st.info("No upcoming schedule data available to swap.")

# --- 5. STYLED TABLE ---
st.subheader("📋 Current Schedule")

display_df = df.copy()

display_df["Week"] = pd.to_numeric(display_df["Week"], errors='coerce').fillna(0).astype(int).astype(str).replace("0", "")
if "Notes" in display_df.columns:
    display_df["Notes"] = display_df["Notes"].fillna("").astype(str).replace(["nan", "None"], "")

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
