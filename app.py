import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from zoneinfo import ZoneInfo
import io

# -----------------------------
# CONFIG
# -----------------------------
TH_TZ = ZoneInfo("Asia/Bangkok")

def today_th():
    return datetime.now(TH_TZ).date().isoformat()

# -----------------------------
# FIREBASE INIT
# -----------------------------
@st.cache_resource
def init_firestore():
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(st.secrets["FIREBASE_KEY"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = init_firestore()

# -----------------------------
# HELPERS
# -----------------------------
def get_users():
    docs = db.collection("users").stream()
    return [(d.id, d.to_dict()) for d in docs]

def add_user(name, max_cal):
    name = name.strip().lower()
    existing = db.collection("users").where("name", "==", name).stream()
    if any(existing):
        return False
    db.collection("users").add({
        "name": name,
        "max_calories": max_cal
    })
    return True

def delete_user(user_id):
    # delete records first
    records = db.collection("records").where("user_id", "==", user_id).stream()
    for r in records:
        db.collection("records").document(r.id).delete()
    db.collection("users").document(user_id).delete()

def add_record(user_id, date_str, cal, note):
    db.collection("records").add({
        "user_id": user_id,
        "record_date": date_str,
        "calories": cal,
        "note": note
    })

def get_records(user_id, date_str):
    docs = db.collection("records")\
        .where("user_id", "==", user_id)\
        .where("record_date", "==", date_str).stream()

    data = []
    for d in docs:
        row = d.to_dict()
        row["id"] = d.id
        data.append(row)
    return pd.DataFrame(data)

def update_record(doc_id, cal, note):
    db.collection("records").document(doc_id).update({
        "calories": cal,
        "note": note
    })

def delete_record(doc_id):
    db.collection("records").document(doc_id).delete()

def get_dashboard(users):
    all_records = db.collection("records").stream()
    summary = {}

    for r in all_records:
        d = r.to_dict()
        uid = d["user_id"]
        summary[uid] = summary.get(uid, 0) + d["calories"]

    rows = []
    for uid, data in users:
        total = summary.get(uid, 0)
        max_cal = data["max_calories"]
        remain = max_cal - total
        percent = (remain / max_cal * 100) if max_cal > 0 else 0

        rows.append({
            "name": data["name"],
            "total": total,
            "remain": remain,
            "%": max(0, percent)
        })

    return pd.DataFrame(rows)

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Calorie Tracker", layout="wide")
st.title("🔥 Calorie Tracker PRO")

# -----------------------------
# SIDEBAR - ADD USER
# -----------------------------
st.sidebar.header("➕ Add User")
name = st.sidebar.text_input("Name")
max_cal = st.sidebar.number_input("Max Calories", min_value=1, value=2000)

if st.sidebar.button("Add User"):
    if name:
        if add_user(name, max_cal):
            st.sidebar.success("User added")
            st.rerun()
        else:
            st.sidebar.error("Name already exists")

# -----------------------------
# LOAD USERS
# -----------------------------
users = get_users()

if not users:
    st.warning("Add user first")
    st.stop()

user_names = [u[1]["name"] for u in users]
selected_name = st.selectbox("👤 Select User", user_names)

user_id, user_data = next(u for u in users if u[1]["name"] == selected_name)
max_cal = user_data["max_calories"]

# -----------------------------
# USER SETTINGS
# -----------------------------
st.subheader("⚙️ User Settings")

col1, col2 = st.columns(2)

with col1:
    new_max = st.number_input("Edit Max Calories", value=max_cal)
    if st.button("Update Max"):
        db.collection("users").document(user_id).update({
            "max_calories": new_max
        })
        st.success("Updated")
        st.rerun()

# confirm delete
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = False

with col2:
    if not st.session_state.confirm_delete:
        if st.button("🗑 Delete User"):
            st.session_state.confirm_delete = True
    else:
        st.warning("Delete ALL data?")
        c1, c2 = st.columns(2)

        with c1:
            if st.button("Yes"):
                delete_user(user_id)
                st.session_state.confirm_delete = False
                st.rerun()

        with c2:
            if st.button("Cancel"):
                st.session_state.confirm_delete = False

# -----------------------------
# FILTER DATE
# -----------------------------
date_selected = st.date_input("📅 Date", value=datetime.now(TH_TZ).date())
date_str = date_selected.isoformat()

# -----------------------------
# ADD RECORD
# -----------------------------
st.subheader("➕ Add Log")

cal = st.number_input("Calories", min_value=0)
note = st.text_input("Note")

if st.button("Add"):
    add_record(user_id, date_str, cal, note)
    st.rerun()

# -----------------------------
# LOG TABLE
# -----------------------------
df = get_records(user_id, date_str)

st.subheader("📋 Logs")

if not df.empty:
    for i, row in df.iterrows():
        c1, c2, c3 = st.columns([2,2,1])

        with c1:
            cal_edit = st.number_input("Cal", value=row["calories"], key=f"cal{i}")
        with c2:
            note_edit = st.text_input("Note", value=row.get("note",""), key=f"note{i}")
        with c3:
            if st.button("Update", key=f"u{i}"):
                update_record(row["id"], cal_edit, note_edit)
                st.rerun()
            if st.button("Delete", key=f"d{i}"):
                delete_record(row["id"])
                st.rerun()
else:
    st.info("No logs")

# -----------------------------
# SUMMARY
# -----------------------------
total = df["calories"].sum() if not df.empty else 0
remain = max_cal - total
percent = (remain / max_cal * 100) if max_cal > 0 else 0

st.subheader("📊 Summary")
st.metric("Used", f"{total}/{max_cal}")
st.metric("Remaining", f"{remain}")
st.progress(max(0, percent) / 100)

# -----------------------------
# DASHBOARD
# -----------------------------
st.subheader("📊 Dashboard")

df_dash = get_dashboard(users)

st.dataframe(df_dash)

fig = px.bar(df_dash, x="name", y="%", text=df_dash["%"].round(1))
st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# EXPORT
# -----------------------------
st.subheader("📤 Export Excel")

if not df.empty:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)

    st.download_button(
        "Download Excel",
        data=output.getvalue(),
        file_name="calories.xlsx"
    )
