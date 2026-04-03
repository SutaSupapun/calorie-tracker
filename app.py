import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
import io

# -------------------------
# Firebase init
# -------------------------
if not firebase_admin._apps:
    cred_dict = st.secrets["FIREBASE_KEY"]
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -------------------------
# Helpers
# -------------------------
TZ = pytz.timezone("Asia/Bangkok")

def get_users():
    users_ref = db.collection("users").stream()
    return [(u.id, u.to_dict()) for u in users_ref]

def get_logs(user_id=None, start_date=None, end_date=None):
    logs_ref = db.collection("records")
    if user_id:
        logs_ref = logs_ref.where("user_id", "==", user_id)
    logs = []
    for doc in logs_ref.stream():
        data = doc.to_dict()
        data["timestamp"] = data["timestamp"].astimezone(TZ)
        if start_date and data["timestamp"] < start_date:
            continue
        if end_date and data["timestamp"] > end_date:
            continue
        logs.append(data)
    return logs

def add_log(user_id, calories, note=""):
    db.collection("records").add({
        "user_id": user_id,
        "calories": calories,
        "note": note,
        "timestamp": datetime.now(TZ)
    })

def update_max_cal(user_id, max_cal):
    db.collection("users").document(user_id).update({"max_calories": max_cal})

def delete_user(user_id):
    # Delete user logs first
    logs_ref = db.collection("records").where("user_id", "==", user_id).stream()
    for doc in logs_ref:
        doc.reference.delete()
    # Delete user
    db.collection("users").document(user_id).delete()

def create_user(name, max_cal):
    # Check duplicate name
    existing = db.collection("users").where("name", "==", name).stream()
    if any(True for _ in existing):
        st.error("User name already exists!")
        return None
    db.collection("users").add({
        "name": name,
        "max_calories": max_cal
    })

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
        rows.append({
            "Name": data["name"],
            "Max Cal": max_cal,
            "Eat": total,
            "Remaining": remain
        })
    df = pd.DataFrame(rows)
    df["Remaining"] = df["Remaining"].astype(int)
    return df.sort_values(by="Remaining")

# -------------------------
# Sidebar: Add User / Log
# -------------------------
st.sidebar.header("👤 User Management")
users = get_users()

# Create user
st.sidebar.subheader("Add New User")
new_name = st.sidebar.text_input("Name")
new_max = st.sidebar.number_input("Max Calories", min_value=0, step=100)
if st.sidebar.button("Add User"):
    if new_name.strip():
        create_user(new_name.strip(), new_max)
        st.experimental_rerun()

# Add log
st.sidebar.subheader("Add Log")
log_user = st.sidebar.selectbox("Select User", [u[1]["name"] for u in users])
log_cal = st.sidebar.number_input("Calories", min_value=0, step=50, key="logcal")
log_note = st.sidebar.text_input("Note")
if st.sidebar.button("Add Log Entry"):
    user_id = [u[0] for u in users if u[1]["name"] == log_user][0]
    add_log(user_id, log_cal, log_note)
    st.experimental_rerun()

# -------------------------
# Sidebar: Edit / Delete User
# -------------------------
st.sidebar.subheader("Edit / Delete User")
sel_user = st.sidebar.selectbox("Select User", [u[1]["name"] for u in users], key="edituser")
user_id = [u[0] for u in users if u[1]["name"] == sel_user][0]
user_data = [u[1] for u in users if u[1]["name"] == sel_user][0]

new_max_edit = st.sidebar.number_input("Max Calories", value=user_data["max_calories"], step=100)
if st.sidebar.button("Update Max Calories"):
    update_max_cal(user_id, new_max_edit)
    st.success("Updated max calories")
    st.experimental_rerun()

if st.sidebar.button("Delete User"):
    if st.sidebar.checkbox("Confirm Delete User"):
        delete_user(user_id)
        st.success("User deleted")
        st.experimental_rerun()

# -------------------------
# Main Dashboard
# -------------------------
st.title("🍽️ Calorie Tracker Dashboard")

# Dashboard table
df_dash = get_dashboard(users)

# Conditional formatting for Remaining
def highlight_remaining(row):
    color = 'red' if row['Remaining'] < 0 else 'green'
    return ['color: {}'.format(color) if col == 'Remaining' else '' for col in row.index]

st.subheader("📊 User Summary")
st.dataframe(df_dash.style.apply(highlight_remaining, axis=1), use_container_width=True)

# Plot remaining top 5
st.subheader("📈 Remaining Calories (Top 5)")
df_top5 = df_dash.head(5)
colors = ["#2ca02c" if x >= 0 else "#d62728" for x in df_top5["Remaining"]]

fig = px.bar(
    df_top5,
    x="Name",
    y="Remaining",
    text="Remaining",
    color="Remaining",
    color_discrete_sequence=colors
)
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# -------------------------
# Logs + Filter + Export
# -------------------------
st.subheader("📝 Logs")
start_date = st.date_input("Start Date")
end_date = st.date_input("End Date")
logs = get_logs(start_date=datetime.combine(start_date, datetime.min.time(), TZ),
                end_date=datetime.combine(end_date, datetime.max.time(), TZ))

df_logs = pd.DataFrame(logs)
if not df_logs.empty:
    df_logs["timestamp"] = df_logs["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    st.dataframe(df_logs)
    # Export
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_logs.to_excel(writer, index=False, sheet_name="Logs")
    st.download_button(
        label="📥 Export Logs to Excel",
        data=output.getvalue(),
        file_name="calorie_logs.xlsx"
    )
else:
    st.info("No logs in selected date range.")
