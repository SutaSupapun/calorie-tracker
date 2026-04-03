import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import datetime
import pytz

# =======================
# Helper Functions
# =======================
def color_status(val):
    if val == "Over Limit":
        return "background-color: red; color: white"
    elif val == "OK":
        return "background-color: lightgreen"
    else:
        return ""

def excel_download(df, filename="export.csv"):
    csv_data = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv"
    )

def get_remaining(u):
    total_eat = sum(u.get('logs', {}).values())
    remain = u.get('max_cal', 0) - total_eat
    status = "OK" if remain >= 0 else "Over Limit"
    return total_eat, remain, status

# =======================
# Reset Timezone (ไทย)
# =======================
THAI_TZ = pytz.timezone('Asia/Bangkok')
st.session_state['now'] = datetime.now(THAI_TZ)

# =======================
# Initialize Data
# =======================
if "users" not in st.session_state:
    st.session_state["users"] = {}  # {username: {"max_cal": int, "logs": {date: cal}}}

# =======================
# Sidebar: Add / Edit / Delete User
# =======================
st.sidebar.header("User Management")
new_user = st.sidebar.text_input("New user name")
new_max = st.sidebar.number_input("Max Calories", min_value=0, value=2000, step=50)
if st.sidebar.button("Add User"):
    if not new_user:
        st.sidebar.error("User name cannot be empty!")
    elif new_user in st.session_state["users"]:
        st.sidebar.error("User name already exists!")
    else:
        st.session_state["users"][new_user] = {"max_cal": new_max, "logs": {}}
        st.sidebar.success(f"Added user {new_user}")

if st.session_state["users"]:
    selected = st.sidebar.selectbox("Select user", list(st.session_state["users"].keys()))
    edit_max = st.sidebar.number_input("Edit Max Calories", min_value=0, value=st.session_state["users"][selected]["max_cal"], step=50)
    if st.sidebar.button("Update Max Calories"):
        st.session_state["users"][selected]["max_cal"] = edit_max
        st.sidebar.success(f"Updated {selected}'s Max Calories")
    if st.sidebar.button("Delete User"):
        confirm_delete = st.sidebar.checkbox(f"Confirm delete user {selected}?")
        if confirm_delete:
            del st.session_state["users"][selected]
            st.sidebar.success(f"Deleted user {selected}")

# =======================
# Main: Log Calories
# =======================
st.header("Calorie Tracker Logs")
if st.session_state["users"]:
    user_list = list(st.session_state["users"].keys())
    log_user = st.selectbox("Select user to log", user_list)
    log_date = st.date_input("Date", datetime.now(THAI_TZ))
    log_cal = st.number_input("Calories eaten", min_value=0, value=0, step=50)
    if st.button("Add Log"):
        date_str = log_date.strftime("%Y-%m-%d")
        st.session_state["users"][log_user]["logs"][date_str] = log_cal
        st.success(f"Logged {log_cal} calories for {log_user} on {date_str}")
else:
    st.info("No users. Add users in sidebar.")

# =======================
# Dashboard
# =======================
st.header("Dashboard")
dashboard_data = []
for name, u in st.session_state["users"].items():
    total, remain, status = get_remaining(u)
    dashboard_data.append({
        "Name": name,
        "Max Cal": u.get("max_cal", 0),
        "Eat": total,
        "Remaining": remain,
        "Status": status
    })

df_dash = pd.DataFrame(dashboard_data)
if not df_dash.empty:
    # ใช้ st.table แทน st.dataframe + Styler
    st.table(df_dash)

    # Plot remaining calories
    fig = px.bar(df_dash.head(5), x="Name", y="Remaining", color="Name",
                 color_discrete_sequence=px.colors.qualitative.Pastel,
                 text="Remaining")
    fig.update_layout(title="Remaining Calories (Top 5 Users)")
    st.plotly_chart(fig)

    # Export Excel
    excel_download(df_dash, filename="calorie_dashboard.csv")
else:
    st.info("No user data to display")
