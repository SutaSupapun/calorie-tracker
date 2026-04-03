import streamlit as st
import pandas as pd
import datetime
import pytz
import firebase_admin
from firebase_admin import credentials, firestore

# ======= Firebase Setup =======
cred_dict = dict(st.secrets["FIREBASE_KEY"])
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ======= Timezone =======
tz = pytz.timezone("Asia/Bangkok")
today = datetime.datetime.now(tz).date()

# ======= Session State =======
if "users" not in st.session_state:
    st.session_state.users = {}  # key: username, value: {"max_cal": int, "logs": []}

if "logs" not in st.session_state:
    st.session_state.logs = []  # list of {"user": str, "cal": int, "date": date, "action": str}

# ======= Sidebar: Manage Users =======
st.sidebar.header("Manage Users")

# Add user
new_user = st.sidebar.text_input("Add new user")
new_max = st.sidebar.number_input("Max Calories", min_value=0, value=2000)
if st.sidebar.button("Add User"):
    if new_user.strip() == "":
        st.sidebar.error("User name cannot be empty!")
    elif new_user in st.session_state.users:
        st.sidebar.error("User already exists!")
    else:
        st.session_state.users[new_user] = {"max_cal": new_max, "logs": []}
        st.sidebar.success(f"User {new_user} added!")

# Edit Max Calories
selected_user = st.sidebar.selectbox("Select user to edit Max Calories", list(st.session_state.users.keys()))
if selected_user:
    new_max_input = st.sidebar.number_input(
        f"New Max Calories for {selected_user}", 
        min_value=0, 
        value=st.session_state.users[selected_user]["max_cal"]
    )
    if st.sidebar.button("Update Max Calories"):
        st.session_state.users[selected_user]["max_cal"] = new_max_input
        st.sidebar.success(f"{selected_user} Max Calories updated!")

# Delete user with confirm
delete_user = st.sidebar.selectbox("Select user to delete", list(st.session_state.users.keys()))
confirm_delete = st.sidebar.checkbox(f"Confirm delete user {delete_user}?")
if confirm_delete:
    if st.sidebar.button("Delete User"):
        del st.session_state.users[delete_user]
        # Remove logs
        st.session_state.logs = [l for l in st.session_state.logs if l["user"] != delete_user]
        st.sidebar.success(f"User {delete_user} deleted!")
        st.experimental_rerun()

# ======= Sidebar: Add Calorie Log =======
st.sidebar.header("Add Calorie Log")
log_user = st.sidebar.selectbox("User", list(st.session_state.users.keys()), key="log_user")
log_cal = st.sidebar.number_input("Calories eaten", min_value=0)
log_date = st.sidebar.date_input("Date", today)
if st.sidebar.button("Add Log"):
    st.session_state.logs.append({
        "user": log_user,
        "cal": log_cal,
        "date": log_date,
        "action": "add"
    })
    st.sidebar.success("Log added!")

# ======= Sidebar: Filter Logs =======
st.sidebar.header("Filter Logs")
filter_date = st.sidebar.date_input("Filter by date", today)
filtered_logs = [l for l in st.session_state.logs if l["date"] == filter_date]

# ======= Dashboard =======
st.header("Calorie Dashboard")
dashboard = []
colors = ["#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd"]  # up to 5 users different colors

for idx, (user, data) in enumerate(st.session_state.users.items()):
    total_eat = sum(l["cal"] for l in st.session_state.logs if l["user"] == user)
    remain = data["max_cal"] - total_eat
    status = "OK" if remain >= 0 else "Over Limit"
    dashboard.append({
        "Name": user,
        "Max Cal": data["max_cal"],
        "Eat": total_eat,
        "Remaining": remain,
        "Status": status,
        "Color": colors[idx % len(colors)]
    })

df_dash = pd.DataFrame(dashboard)
st.dataframe(df_dash.style.apply(lambda x: ["background-color: red" if v=="Over Limit" else "background-color: lightgreen" for v in x], subset=["Status"]))

# ======= Bar Chart Remaining Calories =======
st.subheader("Remaining Calories")
import matplotlib.pyplot as plt

plt.figure(figsize=(8,4))
plt.bar(
    df_dash["Name"], 
    df_dash["Remaining"], 
    color=[c if r>=0 else "red" for r, c in zip(df_dash["Remaining"], df_dash["Color"])]
)
plt.axhline(0, color="black")
plt.ylabel("Remaining Calories")
st.pyplot(plt)

# ======= Logs Table =======
st.subheader(f"Logs on {filter_date}")
df_logs = pd.DataFrame(filtered_logs)
if not df_logs.empty:
    st.dataframe(df_logs)
else:
    st.info("No logs for selected date")

# ======= Export Excel =======
st.subheader("Export Logs to Excel")
if st.button("Export Logs"):
    export_df = pd.DataFrame(st.session_state.logs)
    export_df.to_excel("calorie_logs.xlsx", index=False)
    st.success("Exported to calorie_logs.xlsx")
