import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Lab Meeting Schedule", layout="wide")

DATA_FILE = "schedule.csv"

# Pre-defined list of members to ensure consistent spelling
MEMBERS = sorted([
    "Caroline", "Emma", "Georgia", "Hendrik", "Konrad", "Leo", 
    "Lisi", "Lotte", "Maud", "Ming", "Mostafa", "Negisa", 
    "Niamh", "Noah", "Nora", "Remi", "Roos", "Sofia", 
    "Sofie", "Stan", "Vinicio", "Wies"
])

SLOT_COLS = ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        # Initial sample layout matching your table structure
        initial_data = {
            "Week": [35, 36, 37, 38],
            "Date": ["31-Aug", "7-Sep", "14-Sep", "21-Sep"],
            "Slot 1": ["Hendrik", "Wies", "Negisa", "Niamh"],
            "Slot 2": ["Sofie", "Nora", "Emma", "Vinicio"],
            "Slot 3": ["Maud", "Sofia", "Lotte", "Ming"],
            "Slot 4": ["Mostafa", "Remi", "Konrad", "Caroline"],
            "Notes": ["", "", "", ""]
        }
        df = pd.DataFrame(initial_data)
        df.to_csv(DATA_FILE, index=False)
        return df

def save_data(df):
    df.to_csv(DATA_FILE, index=False)
    st.session_state.df = df

if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

st.title("📅 Group Meeting Presentation Schedule")
st.markdown("Swap presentation dates below or update notes directly.")

# ----------------------------------------------------
# 1. SWAP PRESENTER TOOL
# ----------------------------------------------------
st.subheader("🔄 Swap Presentation Slots")

with st.expander("Click here to swap slots with another member", expanded=False):
    # Melt dataframe to list every presentation slot with its date and current presenter
    slot_entries = []
    for idx, row in df.iterrows():
        for slot in SLOT_COLS:
            presenter = str(row[slot]).strip()
            if presenter and presenter != "nan":
                label = f"{row['Date']} (Week {row['Week']}) - {slot}: {presenter}"
                slot_entries.append({"label": label, "idx": idx, "slot": slot, "person": presenter})
    
    entry_labels = [e["label"] for e in slot_entries]
    
    col_a, col_b = st.columns(2)
    with col_a:
        choice_a = st.selectbox("Slot 1 (Your current slot):", options=entry_labels, index=0)
    with col_b:
        # Default to a different entry if possible
        default_b = 1 if len(entry_labels) > 1 else 0
        choice_b = st.selectbox("Slot 2 (Slot to swap with):", options=entry_labels, index=default_b)
        
    if st.button("Confirm Swap", type="primary"):
        if choice_a == choice_b:
            st.warning("Please choose two different slots to swap.")
        else:
            item_a = next(e for e in slot_entries if e["label"] == choice_a)
            item_b = next(e for e in slot_entries if e["label"] == choice_b)
            
            # Execute swap
            df.at[item_a["idx"], item_a["slot"]] = item_b["person"]
            df.at[item_b["idx"], item_b["slot"]] = item_a["person"]
            
            save_data(df)
            st.success(f"Swapped **{item_a['person']}** and **{item_b['person']}** successfully!")
            st.rerun()

# ----------------------------------------------------
# 2. INTERACTIVE SCHEDULE TABLE
# ----------------------------------------------------
st.subheader("📋 Current Schedule")

column_config = {
    "Week": st.column_config.NumberColumn("Week", disabled=True),
    "Date": st.column_config.TextColumn("Date", disabled=True),
    "Notes": st.column_config.TextColumn("Notes / Cancellations", width="large")
}

# Attach dropdown selection for each slot column
for slot in SLOT_COLS:
    column_config[slot] = st.column_config.SelectboxColumn(
        slot,
        options=MEMBERS,
        required=True
    )

edited_df = st.data_editor(
    df,
    column_config=column_config,
    use_container_width=True,
    num_rows="fixed",
    hide_index=True
)

# Button to commit table modifications if edited directly in cells
if st.button("Save Table Changes"):
    save_data(edited_df)
    st.success("Schedule updated successfully!")
    st.rerun()

# Download option
csv_export = df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Download Schedule as CSV",
    data=csv_export,
    file_name="lab_meeting_schedule.csv",
    mime="text/csv"
)
