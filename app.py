# app.py
import streamlit as st
from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import pytz
import pandas as pd
import plotly.express as px

# ---------------------------
# Timezone
# ---------------------------
TH_TZ = pytz.timezone("Asia/Bangkok")

# ---------------------------
# Firebase Initialization
# ---------------------------
try:
    cred_dict = dict(st.secrets["FIREBASE_KEY"])  # Convert AttrDict -> dict
except Exception as e:
    st.error(f"Firebase credential error: {e}")
    st.stop()

cred = credentials.Certificate(cred_dict)
initialize_app(cred)
db = firestore.client()

# ---------------------------
# Helper Functions
# ---------------------------
def get_users():
    return [doc.to_dict() for doc in db.collection("users").stream()]

def add_user(name, max_cal):
    users_ref = db.collection("users")
    # Check duplicate
    if any(u['name'] == name for u in get_users()):
        st.error("User name already exists!")
        return False
    users_ref.add({"name": name, "max_cal": max_cal, "created_at": datetime.now(TH_TZ)})
    return True

def delete_user(user_id):
    # Delete user + all logs
    db.collection("logs").where("user_id", "==", user_id).stream()
    logs_ref = db.collection("logs")
    for log in logs_ref.where("user_id", "==", user_id).stream():
        logs_ref.document(log.id).delete()
    db.collection("users").document(user_id).delete()

def update_max_cal(user_id, new_max):
    db.collection("users").document(user_id).update({"max_cal": new_max})

def add_log(user_id, calories, note=""):
    db.collection("logs").add({
        "user_id": user_id,
        "calories": calories,
        "note": note,
        "created_at": datetime.now(TH_TZ)
    })

def get_logs(user_id=None, start_date=None, end_date=None):
    logs_ref = db.collection("logs")
    query = logs_ref
    if user_id:
        query = query.where("user_id", "==", user_id)
    logs = [doc.to_dict() for doc in query.stream()]
    df = pd.DataFrame(logs)
    if df.empty:
        return df
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(TH_TZ)
    if start_date:
        df = df[df['created_at'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['created_at'] <= pd.to_datetime(end_date)]
    return df

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Calorie Tracker", layout="wide")
st.title("🍽️ Calorie Tracker Dashboard")

menu = ["Dashboard", "Manage Users", "Add Log", "Logs", "Export Excel"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------------------
# Dashboard
# ---------------------------
if choice == "Dashboard":
    st.subheader("Dashboard Overview")
    users = get_users()
    data = []
    for u in users:
        logs = get_logs(u['id'] if 'id' in u else None)
        total_eat = logs['calories'].sum() if not logs.empty else 0
        remain = u['max_cal'] - total_eat
        data.append({
            "Name": u['name'],
            "Max Cal": u['max_cal'],
            "Eat": total_eat,
            "Remaining": remain
        })
    df = pd.DataFrame(data)
    if not df.empty:
        df['Status'] = df['Remaining'].apply(lambda x: "OK" if x >=0 else "Over Limit")
        st.dataframe(df.style.apply(lambda x: ["background-color: #ff9999" if v=="Over Limit" else "background-color: #99ff99" for v in x], subset=['Status']))
        # Graph
        fig = px.bar(df.head(5), x='Name', y='Remaining', color='Name', text='Remaining',
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No users to display.")

# ---------------------------
# Manage Users
# ---------------------------
elif choice == "Manage Users":
    st.subheader("Manage Users")
    users = get_users()
    for u in users:
        col1, col2, col3, col4 = st.columns([2,2,2,1])
        with col1:
            st.write(u['name'])
        with col2:
            new_max = st.number_input(f"Max Cal {u['name']}", min_value=0, value=u['max_cal'], key=f"max_{u['name']}")
        with col3:
            if st.button("Update Max", key=f"upd_{u['name']}"):
                update_max_cal(u['id'], new_max)
                st.success(f"{u['name']}'s Max Cal updated.")
        with col4:
            if st.button("Delete", key=f"del_{u['name']}"):
                if st.confirm(f"Confirm delete user {u['name']}?"):
                    delete_user(u['id'])
                    st.success(f"User {u['name']} deleted.")
                    st.experimental_rerun()

# ---------------------------
# Add Log
# ---------------------------
elif choice == "Add Log":
    st.subheader("Add Calorie Log")
    users = get_users()
    user_dict = {u['name']: u['id'] for u in users}
    selected_user = st.selectbox("User", user_dict.keys())
    calories = st.number_input("Calories", min_value=0)
    note = st.text_input("Note")
    if st.button("Add Log"):
        add_log(user_dict[selected_user], calories, note)
        st.success("Log added!")

# ---------------------------
# Logs
# ---------------------------
elif choice == "Logs":
    st.subheader("View Logs")
    users = get_users()
    user_dict = {u['name']: u['id'] for u in users}
    selected_user = st.selectbox("User (optional)", ["All"] + list(user_dict.keys()))
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    uid = None if selected_user=="All" else user_dict[selected_user]
    df_logs = get_logs(uid, start_date, end_date)
    st.dataframe(df_logs)

# ---------------------------
# Export Excel
# ---------------------------
elif choice == "Export Excel":
    st.subheader("Export Logs to Excel")
    users = get_users()
    all_logs = []
    for u in users:
        logs = get_logs(u['id'])
        if not logs.empty:
            logs['User'] = u['name']
            all_logs.append(logs)
    if all_logs:
        df_export = pd.concat(all_logs)
        excel_file = "logs.xlsx"
        df_export.to_excel(excel_file, index=False)
        with open(excel_file, "rb") as f:
            st.download_button("Download Excel", f, file_name=excel_file)
    else:
        st.info("No logs to export.")
