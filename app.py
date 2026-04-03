import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import pytz
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

st.set_page_config(page_title="Calorie Tracker", layout="wide")
st.title("Calorie Tracker App")

# ===== FIREBASE =====
cred_dict = dict(st.secrets["FIREBASE_KEY"])
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ===== TIMEZONE =====
tz = pytz.timezone("Asia/Bangkok")

# ======= GET USERS =======
def get_users():
    users = db.collection("users").stream()
    user_list = []
    for u in users:
        u_dict = u.to_dict()
        u_dict["id"] = u.id
        u_dict["max_cal"] = u_dict.get("max_cal", 2000)
        user_list.append(u_dict)
    return user_list

users = get_users()

# ======= GET LOGS =======
def get_logs():
    logs = db.collection("logs").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    log_list = []
    for l in logs:
        l_dict = l.to_dict()
        l_dict["id"] = l.id
        log_list.append(l_dict)
    return log_list

logs = get_logs()

# ======= SIDEBAR USER MANAGEMENT =======
st.sidebar.header("User Management")
new_name = st.sidebar.text_input("New User Name")
new_max = st.sidebar.number_input("Max Calories", min_value=1, value=2000)

if st.sidebar.button("Add User"):
    if new_name.strip() == "":
        st.sidebar.error("Name cannot be empty")
    elif any(u['name']==new_name for u in users):
        st.sidebar.error("User name already exists")
    else:
        db.collection("users").add({"name": new_name, "max_cal": new_max})
        st.sidebar.success(f"User {new_name} added")
        st.experimental_rerun()

selected = st.sidebar.selectbox("Select User", [""] + [u['name'] for u in users])

if selected:
    user_obj = next(u for u in users if u['name']==selected)
    new_max_edit = st.sidebar.number_input("Edit Max Calories", value=user_obj.get("max_cal",2000))
    if st.sidebar.button("Update Max Calories"):
        db.collection("users").document(user_obj['id']).update({"max_cal": new_max_edit})
        st.sidebar.success("Updated Max Calories")
        st.experimental_rerun()
    if st.sidebar.button("Delete User"):
        if st.sidebar.confirm(f"Confirm delete user {selected}?"):
            # delete logs first
            for l in logs:
                if l.get("user_id")==user_obj['id']:
                    db.collection("logs").document(l['id']).delete()
            # delete user
            db.collection("users").document(user_obj['id']).delete()
            st.sidebar.success(f"User {selected} deleted")
            st.experimental_rerun()

# ======= LOG ENTRY =======
st.header("Log Entry")
log_user = st.selectbox("User", [u['name'] for u in users])
log_cal = st.number_input("Calories", min_value=0)
log_note = st.text_input("Note")
if st.button("Add Log"):
    user_obj = next(u for u in users if u['name']==log_user)
    db.collection("logs").add({
        "user_id": user_obj['id'],
        "calories": log_cal,
        "note": log_note,
        "timestamp": datetime.now(tz)
    })
    st.success("Log added")
    st.experimental_rerun()

# ======= LOG TABLE =======
st.header("Logs")
filter_date = st.date_input("Filter by date")
filtered_logs = [l for l in logs if l.get("timestamp").date()==filter_date]
df_logs = pd.DataFrame(filtered_logs)
if not df_logs.empty:
    df_logs["User"] = df_logs["user_id"].apply(lambda uid: next((u['name'] for u in users if u['id']==uid), "Unknown"))
    df_logs["Time"] = df_logs["timestamp"].apply(lambda t: t.astimezone(tz).strftime("%H:%M"))
    df_logs = df_logs[["User","calories","note","Time"]]
    st.dataframe(df_logs)

    # Export Excel
    excel_bytes = df_logs.to_excel(index=False)
    st.download_button("Export Excel", data=excel_bytes, file_name="logs.xlsx")
else:
    st.info("No logs for selected date")

# ======= DASHBOARD =======
st.header("Dashboard")
summary = []
for u in users:
    user_logs = [l['calories'] for l in logs if l.get('user_id')==u['id']]
    total_eat = sum(user_logs)
    remain = u.get('max_cal', 2000) - total_eat
    status = "OK" if remain >= 0 else "Over Limit"
    summary.append({
        "Name": u.get('name', "Unknown"),
        "Max Cal": u.get('max_cal', 2000),
        "Eat": total_eat,
        "Remain": remain,
        "Status": status
    })
df_dash = pd.DataFrame(summary)

# Table with colored status
def color_status(val):
    if val=="Over Limit":
        return "background-color: red; color: white"
    elif val=="OK":
        return "background-color: lightgreen"
    else:
        return ""
st.dataframe(df_dash.style.applymap(color_status, subset=["Status"]))

# Bar chart
fig, ax = plt.subplots()
colors = ["blue","orange","green","purple","brown"]
for i, row in df_dash.head(5).iterrows():
    ax.bar(row["Name"], max(0,row["Remain"]), color=colors[i%len(colors)])
ax.set_ylabel("Remaining Calories")
st.pyplot(fig)
