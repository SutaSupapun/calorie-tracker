# app.py
import streamlit as st
from firebase_admin import credentials, initialize_app, firestore
import json
import pandas as pd
from datetime import datetime
import pytz

# ---------------------------
# Firebase Initialization
# ---------------------------
try:
    cred_dict = json.loads(st.secrets["FIREBASE_KEY"])
except Exception as e:
    st.error(f"Firebase credential error: {e}")
    st.stop()

cred = credentials.Certificate(cred_dict)
initialize_app(cred)
db = firestore.client()

# ---------------------------
# Timezone
# ---------------------------
tz = pytz.timezone("Asia/Bangkok")
def now():
    return datetime.now(tz)

# ---------------------------
# Helpers
# ---------------------------
def get_users():
    return [doc.to_dict() for doc in db.collection("users").stream()]

def get_logs(user_id=None, start_date=None, end_date=None):
    logs_ref = db.collection("logs")
    if user_id:
        logs_ref = logs_ref.where("user_id", "==", user_id)
    if start_date:
        logs_ref = logs_ref.where("date", ">=", start_date)
    if end_date:
        logs_ref = logs_ref.where("date", "<=", end_date)
    return [doc.to_dict() for doc in logs_ref.stream()]

def add_user(name, max_cal):
    existing = db.collection("users").where("name", "==", name).get()
    if existing:
        st.error("User name already exists!")
        return False
    db.collection("users").add({"name": name, "max_cal": max_cal})
    st.success(f"User {name} added")
    return True

def update_max_cal(user_doc_id, new_max):
    db.collection("users").document(user_doc_id).update({"max_cal": new_max})
    st.success("Max calories updated!")

def delete_user(user_doc_id):
    # delete user logs first
    logs = db.collection("logs").where("user_id", "==", user_doc_id).stream()
    for log in logs:
        db.collection("logs").document(log.id).delete()
    db.collection("users").document(user_doc_id).delete()
    st.success("User and all logs deleted!")

# ---------------------------
# Sidebar - Add User
# ---------------------------
st.sidebar.header("Add User")
with st.sidebar.form("add_user"):
    name = st.text_input("Name")
    max_cal = st.number_input("Max Calories", min_value=0, value=2000)
    submitted = st.form_submit_button("Add User")
    if submitted:
        add_user(name, max_cal)

# ---------------------------
# Sidebar - Select User to Edit / Delete
# ---------------------------
st.sidebar.header("Manage Users")
users = get_users()
user_map = {u['name']: u for u in users}
selected_user_name = st.sidebar.selectbox("Select User", [""] + [u['name'] for u in users])

if selected_user_name:
    user_data = user_map[selected_user_name]
    st.sidebar.subheader("Edit Max Calories")
    new_max = st.sidebar.number_input(
        "Max Calories",
        min_value=0,
        value=user_data["max_cal"]
    )
    if st.sidebar.button("Update Max"):
        # Find doc ID
        doc_id = db.collection("users").where("name", "==", selected_user_name).get()[0].id
        update_max_cal(doc_id, new_max)

    st.sidebar.subheader("Delete User")
    if st.sidebar.button("Delete User"):
        if st.confirm(f"Are you sure you want to delete {selected_user_name}? This will remove all their logs!"):
            doc_id = db.collection("users").where("name", "==", selected_user_name).get()[0].id
            delete_user(doc_id)

# ---------------------------
# Log Food Intake
# ---------------------------
st.header("Add Food Log")
with st.form("log_food"):
    user_log_name = st.selectbox("User", [u['name'] for u in users])
    calories = st.number_input("Calories", min_value=0, value=0)
    date = st.date_input("Date", value=now())
    submitted = st.form_submit_button("Add Log")
    if submitted:
        # Get user ID
        user_doc_id = db.collection("users").where("name", "==", user_log_name).get()[0].id
        db.collection("logs").add({
            "user_id": user_doc_id,
            "user_name": user_log_name,
            "calories": calories,
            "date": datetime.combine(date, datetime.min.time())
        })
        st.success("Log added!")

# ---------------------------
# Filter Logs
# ---------------------------
st.header("View Logs")
filter_user = st.selectbox("Filter User", ["All"] + [u['name'] for u in users])
start_date = st.date_input("Start Date", value=None)
end_date = st.date_input("End Date", value=None)

logs = get_logs(
    None if filter_user == "All" else user_map[filter_user]["name"],
    start_date=start_date,
    end_date=end_date
)
if logs:
    df_logs = pd.DataFrame(logs)
    st.dataframe(df_logs)
else:
    st.info("No logs found for the filter")

# ---------------------------
# Dashboard
# ---------------------------
st.header("Dashboard")
data = []
for u in users:
    # Get user logs
    doc_id = db.collection("users").where("name", "==", u['name']).get()[0].id
    user_logs = get_logs(doc_id)
    total_eat = sum([l['calories'] for l in user_logs])
    remaining = u['max_cal'] - total_eat
    data.append({
        "Name": u['name'],
        "Max Cal": u['max_cal'],
        "Eat": total_eat,
        "Remaining": remaining,
        "Status": "Over Limit" if remaining < 0 else "OK"
    })

df = pd.DataFrame(data)
st.dataframe(df.style.applymap(
    lambda v: "background-color: red; color: white" if isinstance(v, str) and v=="Over Limit"
    else ("background-color: green; color: white" if isinstance(v, str) and v=="OK" else ""),
    subset=["Status"]
))

# ---------------------------
# Remaining Calories Chart
# ---------------------------
st.subheader("Remaining Calories Chart")
import plotly.express as px

colors = px.colors.qualitative.Set1  # 5 distinct colors
fig = px.bar(
    df.head(5),
    x="Name",
    y="Remaining",
    color="Name",
    color_discrete_sequence=colors,
    text="Remaining",
    labels={"Remaining": "Remaining Calories"}
)
fig.update_traces(
    marker_color=["red" if r < 0 else "green" for r in df.head(5)["Remaining"]],
    textposition="outside"
)
st.plotly_chart(fig)

# ---------------------------
# Export Excel
# ---------------------------
st.subheader("Export Logs")
if st.button("Export Excel"):
    if logs:
        excel_file = "logs_export.xlsx"
        pd.DataFrame(logs).to_excel(excel_file, index=False)
        st.success(f"Excel exported: {excel_file}")
    else:
        st.info("No logs to export")
