# app.py
import streamlit as st
import pandas as pd
import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="Calorie Tracker", layout="wide")

# --------------------------
# Firebase Init
# --------------------------
if not firebase_admin._apps:
    cred_dict = dict(st.secrets["FIREBASE_KEY"])
    # แปลง private_key ให้ \n ถูกต้อง
    if "private_key" in cred_dict:
        cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --------------------------
# Utils
# --------------------------
def get_users():
    users = []
    for doc in db.collection("users").stream():
        data = doc.to_dict()
        data['id'] = doc.id
        data['max_cal'] = data.get('max_cal', 0)  # default 0
        users.append(data)
    return users

def get_logs(user_id):
    logs = []
    for doc in db.collection("logs").where("user_id", "==", user_id).stream():
        data = doc.to_dict()
        data['id'] = doc.id
        logs.append(data)
    if logs:
        return pd.DataFrame(logs)
    else:
        return pd.DataFrame(columns=['date','food','calories','id'])

def add_user(name, max_cal):
    # check duplicate
    if db.collection("users").where("name","==",name).get():
        st.warning("User name already exists!")
        return
    db.collection("users").add({"name":name,"max_cal":max_cal})

def update_max_cal(user_id, max_cal):
    db.collection("users").document(user_id).update({"max_cal": max_cal})

def delete_user(user_id):
    # delete logs first
    logs = db.collection("logs").where("user_id","==",user_id).stream()
    for l in logs:
        db.collection("logs").document(l.id).delete()
    # delete user
    db.collection("users").document(user_id).delete()

def add_log(user_id, food, cal):
    db.collection("logs").add({
        "user_id": user_id,
        "food": food,
        "calories": cal,
        "date": datetime.datetime.now(pytz.timezone("Asia/Bangkok")).isoformat()
    })

def delete_log(log_id):
    db.collection("logs").document(log_id).delete()

# --------------------------
# Sidebar: Add/Edit/Delete User
# --------------------------
st.sidebar.header("Manage Users")
action = st.sidebar.selectbox("Action", ["Add User", "Edit Max Calories", "Delete User"])

users = get_users()
user_options = {u['name']: u['id'] for u in users}

if action == "Add User":
    name = st.sidebar.text_input("User Name")
    max_cal = st.sidebar.number_input("Max Calories", min_value=0)
    if st.sidebar.button("Add"):
        if name.strip():
            add_user(name, max_cal)
            st.sidebar.success(f"User {name} added!")
            st.experimental_rerun()

elif action == "Edit Max Calories":
    selected = st.sidebar.selectbox("Select User", list(user_options.keys()))
    max_cal_new = st.sidebar.number_input("New Max Calories", min_value=0)
    if st.sidebar.button("Update"):
        update_max_cal(user_options[selected], max_cal_new)
        st.sidebar.success(f"{selected} updated!")
        st.experimental_rerun()

elif action == "Delete User":
    selected = st.sidebar.selectbox("Select User", list(user_options.keys()))
    if st.sidebar.button("Delete"):
        if st.sidebar.confirm(f"Confirm delete user {selected}?"):
            delete_user(user_options[selected])
            st.sidebar.success(f"{selected} deleted!")
            st.experimental_rerun()

# --------------------------
# Main Dashboard
# --------------------------
st.title("Calorie Tracker Dashboard")

# Build table
data = []
for u in users:
    logs_df = get_logs(u['id'])
    total_eat = logs_df['calories'].sum() if not logs_df.empty else 0
    remain = u.get('max_cal',0) - total_eat
    data.append({
        "Name": u['name'],
        "Max Cal": u.get('max_cal',0),
        "Eat": total_eat,
        "Remaining": remain
    })

df = pd.DataFrame(data)

# Conditional color
def color_row(row):
    color = 'background-color: #90ee90' if row['Remaining']>=0 else 'background-color: #ff6961'
    return [color]*len(row)

st.dataframe(df.style.apply(color_row, axis=1), use_container_width=True)

# Graph Remaining Calories
st.subheader("Remaining Calories")
import matplotlib.pyplot as plt

plt.figure(figsize=(8,4))
colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']  # first 5 users
plt.bar(df['Name'], df['Remaining'], color=colors[:len(df)])
plt.axhline(0, color='black')
plt.ylabel("Remaining Calories")
st.pyplot(plt)

# --------------------------
# Log Viewer per User
# --------------------------
st.subheader("User Logs")
selected_user = st.selectbox("Select User to view logs", list(user_options.keys()))
logs_df = get_logs(user_options[selected_user])
if not logs_df.empty:
    logs_df['date'] = pd.to_datetime(logs_df['date'])
    # Filter by date
    start_date = st.date_input("Start Date", value=logs_df['date'].min())
    end_date = st.date_input("End Date", value=logs_df['date'].max())
    mask = (logs_df['date'].dt.date >= start_date) & (logs_df['date'].dt.date <= end_date)
    filtered_logs = logs_df.loc[mask]
    st.dataframe(filtered_logs[['date','food','calories']])
    # Delete log
    for idx, row in filtered_logs.iterrows():
        if st.button(f"Delete log {row['food']} ({row['calories']} cal)", key=row['id']):
            delete_log(row['id'])
            st.success("Deleted")
            st.experimental_rerun()
else:
    st.info("No logs for this user yet.")

# --------------------------
# Add new log
# --------------------------
st.subheader("Add Log")
log_user = st.selectbox("User", list(user_options.keys()), key="log_user")
food = st.text_input("Food")
cal = st.number_input("Calories", min_value=0, key="calories")
if st.button("Add Log", key="add_log"):
    add_log(user_options[log_user], food, cal)
    st.success("Log added!")
    st.experimental_rerun()
