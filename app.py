# app.py
import streamlit as st
import pandas as pd
import datetime
import pytz
import io
import matplotlib.pyplot as plt
from firebase_admin import credentials, initialize_app, firestore

# ======= TIMEZONE =======
THAI_TZ = pytz.timezone("Asia/Bangkok")

# ======= FIREBASE =======
# แก้ไข credential ให้ st.secrets["FIREBASE_KEY"] เป็น dict
cred_dict = dict(st.secrets["FIREBASE_KEY"])
cred = credentials.Certificate(cred_dict)
try:
    initialize_app(cred)
except ValueError:
    # Already initialized
    pass

db = firestore.client()

# ======= UTILS =======
def now():
    return datetime.datetime.now(THAI_TZ)

def get_users():
    users = db.collection("users").stream()
    return [u.to_dict() for u in users]

def get_logs(user_id=None, start=None, end=None):
    logs_ref = db.collection("logs")
    if user_id:
        logs_ref = logs_ref.where("user_id", "==", user_id)
    if start:
        logs_ref = logs_ref.where("date", ">=", start)
    if end:
        logs_ref = logs_ref.where("date", "<=", end)
    return [l.to_dict() for l in logs_ref.stream()]

def add_user(name, max_cal):
    users_ref = db.collection("users")
    if any(u['name'] == name for u in get_users()):
        st.error("User name already exists!")
        return
    users_ref.add({
        "name": name,
        "max_cal": max_cal,
        "created_at": now()
    })
    st.success(f"User {name} added!")

def delete_user(user_id):
    if st.confirm(f"Confirm delete user?"):
        # Delete user
        db.collection("users").document(user_id).delete()
        # Delete logs
        logs = db.collection("logs").where("user_id", "==", user_id).stream()
        for log in logs:
            log.reference.delete()
        st.success("User and logs deleted.")
        st.experimental_rerun()

def update_max_cal(user_id, new_max):
    db.collection("users").document(user_id).update({"max_cal": new_max})
    st.success("Max Calories updated!")

def add_log(user_id, cal, note=""):
    db.collection("logs").add({
        "user_id": user_id,
        "calories": cal,
        "note": note,
        "date": now()
    })
    st.success("Log added!")

# ======= SIDEBAR =======
st.sidebar.header("User Management")
users = get_users()
user_names = [u["name"] for u in users]
new_name = st.sidebar.text_input("New User Name")
new_max = st.sidebar.number_input("Max Calories", min_value=0, value=2000)
if st.sidebar.button("Add User"):
    if new_name.strip():
        add_user(new_name.strip(), new_max)

selected_user = st.sidebar.selectbox("Select User", [""] + user_names)
if selected_user:
    user_obj = next(u for u in users if u["name"] == selected_user)
    new_max_edit = st.sidebar.number_input("Edit Max Calories", value=user_obj["max_cal"])
    if st.sidebar.button("Update Max Calories"):
        update_max_cal(user_obj["id"], new_max_edit)

    if st.sidebar.button("Delete User"):
        delete_user(user_obj["id"])

# ======= LOGS =======
st.header("Add Log")
if selected_user:
    cal_input = st.number_input("Calories eaten", min_value=0)
    note_input = st.text_input("Note")
    if st.button("Add Log"):
        add_log(user_obj["id"], cal_input, note_input)

# ======= DASHBOARD =======
st.header("Dashboard")
logs = get_logs()
df_logs = pd.DataFrame(logs)
df_users = pd.DataFrame(users)

if not df_users.empty:
    summary = []
    for u in users:
        user_logs = [l['calories'] for l in logs if l['user_id']==u['id']]
        total_eat = sum(user_logs)
        remain = u['max_cal'] - total_eat
        status = "OK" if remain >=0 else "Over Limit"
        summary.append({
            "Name": u['name'],
            "Max Cal": u['max_cal'],
            "Eat": total_eat,
            "Remain": remain,
            "Status": status
        })
    df_dash = pd.DataFrame(summary)

    # Style
    def color_status(val):
        if val == "Over Limit":
            return "background-color: red; color: white"
        elif val == "OK":
            return "background-color: lightgreen"
        else:
            return ""
    st.dataframe(df_dash.style.applymap(color_status, subset=["Status"]))

    # Chart
    fig, ax = plt.subplots()
    colors = ["blue", "orange", "green", "purple", "brown"]
    for i, row in df_dash.head(5).iterrows():
        ax.bar(row["Name"], max(0, row["Remain"]), color=colors[i])
    ax.set_ylabel("Remaining Calories")
    st.pyplot(fig)

    # Export Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df_dash.to_excel(writer, index=False, sheet_name="Dashboard")
        writer.save()
    st.download_button("Export Dashboard Excel", data=buffer, file_name="dashboard.xlsx")

else:
    st.info("No users available.")
