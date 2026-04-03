import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pytz
import io

# -----------------------------
# TIMEZONE (THAI)
# -----------------------------
TH_TZ = pytz.timezone("Asia/Bangkok")

def today_th():
    return datetime.now(TH_TZ).date()

# -----------------------------
# FIREBASE
# -----------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate(dict(st.secrets["FIREBASE_KEY"]))
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.title("🔥 Calorie Tracker PRO")

# -----------------------------
# ADD USER (NO DUPLICATE)
# -----------------------------
st.sidebar.header("➕ Add User")

new_name = st.sidebar.text_input("Name")
new_max = st.sidebar.number_input("Max Calories", min_value=1, value=2000)

if st.sidebar.button("Add User"):
    if new_name:
        clean_name = new_name.strip().lower()

        existing = db.collection("users").where("name", "==", clean_name).stream()
        if any(existing):
            st.sidebar.error("❌ Name already exists")
        else:
            db.collection("users").add({
                "name": clean_name,
                "max_calories": new_max
            })
            st.sidebar.success("User added")

# -----------------------------
# LOAD USERS
# -----------------------------
users = list(db.collection("users").stream())

if not users:
    st.warning("Add user first")
    st.stop()

user_list = [(u.id, u.to_dict()) for u in users]
names = [u[1]["name"] for u in user_list]

selected_name = st.selectbox("👤 Select User", names)

user_data = next(u for u in user_list if u[1]["name"] == selected_name)
user_id = user_data[0]
max_cal = user_data[1]["max_calories"]

# -----------------------------
# USER SETTINGS
# -----------------------------
st.subheader("⚙️ User Settings")

col1, col2 = st.columns(2)

# EDIT MAX CAL
with col1:
    new_max_cal = st.number_input("Edit Max Calories", value=max_cal)
    if st.button("Update Max Calories"):
        db.collection("users").document(user_id).update({
            "max_calories": new_max_cal
        })
        st.success("Updated!")
        st.st.rerun()()

# DELETE USER WITH CONFIRM
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = False

with col2:
    if not st.session_state.confirm_delete:
        if st.button("🗑 Delete User"):
            st.session_state.confirm_delete = True
    else:
        st.warning("⚠️ Are you sure? This will delete ALL data!")

        col_yes, col_no = st.columns(2)

        with col_yes:
            if st.button("✅ Yes, Delete"):
                records = db.collection("records").where("user_id", "==", user_id).stream()
                for r in records:
                    db.collection("records").document(r.id).delete()

                db.collection("users").document(user_id).delete()

                st.session_state.confirm_delete = False
                st.warning("User deleted")
                st.st.rerun()()

        with col_no:
            if st.button("❌ Cancel"):
                st.session_state.confirm_delete = False

# -----------------------------
# FILTER DATE (THAI TIME)
# -----------------------------
filter_date = st.date_input("📅 Select Date", value=today_th())
filter_date_str = filter_date.isoformat()

# -----------------------------
# ADD RECORD
# -----------------------------
st.subheader("➕ Add Log")

cal = st.number_input("Calories", min_value=0)
note = st.text_input("Note")

if st.button("Add Record"):
    db.collection("records").add({
        "user_id": user_id,
        "record_date": filter_date_str,
        "calories": cal,
        "note": note
    })
    st.success("Saved")
    st.st.rerun()()

# -----------------------------
# LOAD LOGS
# -----------------------------
records = db.collection("records")\
    .where("user_id", "==", user_id)\
    .where("record_date", "==", filter_date_str).stream()

logs = []
for r in records:
    d = r.to_dict()
    d["id"] = r.id
    logs.append(d)

df_logs = pd.DataFrame(logs)

# -----------------------------
# EDIT / DELETE LOG
# -----------------------------
st.subheader("📋 Logs")

if not df_logs.empty:
    for i, row in df_logs.iterrows():
        col1, col2, col3 = st.columns([2,2,1])

        with col1:
            new_cal = st.number_input(f"Cal {i}", value=row["calories"], key=f"cal{i}")
        with col2:
            new_note = st.text_input(f"Note {i}", value=row.get("note",""), key=f"note{i}")
        with col3:
            if st.button("Update", key=f"u{i}"):
                db.collection("records").document(row["id"]).update({
                    "calories": new_cal,
                    "note": new_note
                })
                st.success("Updated")
                st.st.rerun()()

            if st.button("Delete", key=f"d{i}"):
                db.collection("records").document(row["id"]).delete()
                st.warning("Deleted")
                st.st.rerun()()
else:
    st.info("No logs")

# -----------------------------
# SUMMARY
# -----------------------------
total = df_logs["calories"].sum() if not df_logs.empty else 0
remain = max_cal - total
percent = max(0, (remain / max_cal) * 100)

st.subheader("📊 Summary")
st.write(f"{total}/{max_cal} kcal")
st.write(f"Remaining: {remain} ({percent:.1f}%)")
st.progress(percent / 100)

# -----------------------------
# DASHBOARD (ALL USERS)
# -----------------------------
st.subheader("📊 Dashboard (All Users)")

all_records = db.collection("records").stream()
summary = {}

for r in all_records:
    d = r.to_dict()
    uid = d["user_id"]
    summary[uid] = summary.get(uid, 0) + d["calories"]

dashboard = []
for u in user_list:
    uid, data = u
    total_u = summary.get(uid, 0)
    remain_u = data["max_calories"] - total_u
    percent_u = max(0, remain_u / data["max_calories"] * 100)

    dashboard.append({
        "name": data["name"],
        "total": total_u,
        "remain": remain_u,
        "%": percent_u
    })

df_dash = pd.DataFrame(dashboard)

st.dataframe(df_dash)

fig = px.bar(df_dash, x="name", y="%", text=df_dash["%"].round(1))
st.plotly_chart(fig)

# -----------------------------
# EXPORT EXCEL
# -----------------------------
st.subheader("📤 Export Excel")

if st.button("Download Excel"):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_logs.to_excel(writer, index=False)

    st.download_button(
        label="Download",
        data=output.getvalue(),
        file_name="calories.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
