import streamlit as st
import pandas as pd
import datetime
import pytz
import matplotlib.pyplot as plt
from firebase_admin import credentials, initialize_app, firestore

# --- Firebase initialization ---
cred_dict = dict(st.secrets["FIREBASE_KEY"])
cred = credentials.Certificate(cred_dict)
try:
    initialize_app(cred)
except ValueError:
    # Already initialized
    pass
db = firestore.client()

# --- Set timezone ---
tz = pytz.timezone("Asia/Bangkok")

st.title("🍎 Calorie Tracker Dashboard")

# --- Sidebar: User management ---
st.sidebar.header("User Management")
users_ref = db.collection("users")
users_docs = users_ref.stream()
users = [u.to_dict() for u in users_docs]

user_names = [u.get("name") for u in users]
new_name = st.sidebar.text_input("Add new user (unique)")
new_max = st.sidebar.number_input("Max Calories", min_value=0, value=2000)
if st.sidebar.button("Add User"):
    if new_name.strip() == "":
        st.sidebar.error("Name cannot be empty")
    elif new_name in user_names:
        st.sidebar.error("Name already exists")
    else:
        users_ref.add({"name": new_name, "max_cal": new_max})
        st.experimental_rerun()

# Select user to delete or edit
selected = st.sidebar.selectbox("Select User", [""] + user_names)
if selected:
    user_doc = None
    for u in users_ref.stream():
        if u.to_dict()["name"] == selected:
            user_doc = u
            break
    if user_doc:
        edit_max = st.sidebar.number_input("Edit Max Calories", min_value=0, value=user_doc.to_dict().get("max_cal",2000))
        if st.sidebar.button("Update Max Calories"):
            user_doc.reference.update({"max_cal": edit_max})
            st.sidebar.success("Max Calories updated")
            st.experimental_rerun()

        if st.sidebar.button("Delete User"):
            if st.sidebar.confirm(f"Confirm delete user {selected}?"):
                # Delete all logs of this user
                logs_ref = db.collection("logs").where("user", "==", selected)
                for log in logs_ref.stream():
                    log.reference.delete()
                # Delete user
                user_doc.reference.delete()
                st.sidebar.success(f"User {selected} deleted")
                st.experimental_rerun()

# --- Sidebar: Filter logs ---
st.sidebar.header("Filter Logs")
start_date = st.sidebar.date_input("Start date", datetime.date.today() - datetime.timedelta(days=7))
end_date = st.sidebar.date_input("End date", datetime.date.today())

# --- Logs table ---
logs_ref = db.collection("logs").where("date", ">=", datetime.datetime.combine(start_date, datetime.time.min, tzinfo=tz))\
                                 .where("date", "<=", datetime.datetime.combine(end_date, datetime.time.max, tzinfo=tz))
logs = [l.to_dict() for l in logs_ref.stream()]
df_logs = pd.DataFrame(logs)
if not df_logs.empty:
    st.subheader("📋 Logs")
    st.dataframe(df_logs)
    if st.button("Export Logs to Excel"):
        df_logs.to_excel("logs.xlsx", index=False)
        st.success("Logs exported to logs.xlsx")
else:
    st.info("No logs found for selected date range")

# --- Dashboard ---
st.subheader("📊 Dashboard")
dash_data = []
for u in users:
    user_name = u.get("name")
    max_cal = u.get("max_cal",0)
    # Sum eat
    total_eat = sum(l.get("calories",0) for l in logs if l.get("user")==user_name)
    remain = max_cal - total_eat
    status = "OK" if remain >= 0 else "Over Limit"
    dash_data.append({
        "Name": user_name,
        "Max Cal": max_cal,
        "Eat": total_eat,
        "Remain": remain,
        "Status": status
    })

df_dash = pd.DataFrame(dash_data)

# Apply coloring
def color_status(val):
    if val == "Over Limit":
        return "background-color: red; color: white"
    elif val == "OK":
        return "background-color: lightgreen"
    else:
        return ""

if not df_dash.empty and "Status" in df_dash.columns:
    st.dataframe(df_dash.style.applymap(color_status, subset=["Status"]))
else:
    st.info("No user data to display in dashboard")

# --- Chart: Remaining calories ---
st.subheader("📉 Remaining Calories (Top 5 Users)")
if not df_dash.empty:
    top5 = df_dash.head(5)
    colors = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd"]
    plt.figure(figsize=(8,4))
    plt.bar(top5["Name"], top5["Remain"], color=colors[:len(top5)])
    plt.axhline(0, color="black", linewidth=0.8)
    plt.ylabel("Remaining Calories")
    st.pyplot(plt)
