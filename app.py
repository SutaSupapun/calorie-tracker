import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz
import json
import gspread
from google.oauth2.service_account import Credentials

# =======================
# Google Sheets Setup
# =======================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gsheet():
    """Connect to Google Sheets — credentials อ่านจาก st.secrets"""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["sheet_id"]).sheet1
    return sheet

def load_data() -> dict:
    try:
        sheet_id = st.secrets.get("sheet_id", "NOT FOUND")
        has_gcp = "gcp_service_account" in st.secrets
        client_email = st.secrets.get("gcp_service_account", {}).get("client_email", "NOT FOUND") if has_gcp else "NO GCP KEY"
        st.info(f"Debug — sheet_id: {sheet_id} | gcp: {has_gcp} | email: {client_email}")
        sheet = get_gsheet()
        raw = sheet.acell("A1").value
        if raw:
            return json.loads(raw)
    except Exception as e:
        import traceback
        st.error(f"โหลดไม่สำเร็จ: {e}")
        st.code(traceback.format_exc())
    return {}

def save_data(users: dict):
    """บันทึกข้อมูลทั้งหมดลง Google Sheets (เขียน JSON string ลง cell A1)"""
    try:
        sheet = get_gsheet()
        sheet.update("A1", [[json.dumps(users, ensure_ascii=False)]])
    except Exception as e:
        st.error(f"❌ บันทึกข้อมูลไม่สำเร็จ: {e}")

# =======================
# Helper Functions
# =======================
def color_status(val):
    if val == "Over Limit":
        return "background-color: #ff4b4b; color: white"
    elif val == "OK":
        return "background-color: #21c354; color: white"
    return ""

def csv_download(df, filename="export.csv"):
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
    )

def get_today_calories(u, date_str):
    return u.get("logs", {}).get(date_str, 0)

def get_total_calories(u):
    return sum(u.get("logs", {}).values())

def get_remaining(u, date_str=None):
    if date_str:
        total_eat = get_today_calories(u, date_str)
    else:
        total_eat = get_total_calories(u)
    remain = u.get("max_cal", 0) - total_eat
    status = "OK" if remain >= 0 else "Over Limit"
    return total_eat, remain, status

# =======================
# Timezone (ไทย)
# =======================
THAI_TZ = pytz.timezone("Asia/Bangkok")
now = datetime.now(THAI_TZ)
today_str = now.strftime("%Y-%m-%d")

# =======================
# Initialize Data
# =======================
if "users" not in st.session_state:
    st.session_state["users"] = load_data()

if "form_counter" not in st.session_state:
    st.session_state["form_counter"] = 0

if "user_form_counter" not in st.session_state:
    st.session_state["user_form_counter"] = 0

if "deleted_user" not in st.session_state:
    st.session_state["deleted_user"] = False

# =======================
# Page Config
# =======================
st.set_page_config(page_title="🥗 Calorie Tracker", layout="wide")
st.title("🥗 Calorie Tracker")
st.caption(f"วันที่: {now.strftime('%d %B %Y  %H:%M')} (Bangkok Time)")

# =======================
# Sidebar: User Management
# =======================
st.sidebar.header("👤 User Management")

# --- Add New User ---
with st.sidebar.expander("➕ Add New User", expanded=True):
    ufc = st.session_state["user_form_counter"]
    new_user = st.text_input("User name", key=f"new_user_input_{ufc}")
    new_max = st.number_input("Max Calories / day", min_value=0, value=2000, step=50, key=f"new_max_input_{ufc}")
    if st.button("Add User"):
        if not new_user.strip():
            st.sidebar.error("❌ User name cannot be empty!")
        elif new_user.strip() in st.session_state["users"]:
            st.sidebar.error("❌ User name already exists!")
        else:
            st.session_state["users"][new_user.strip()] = {"max_cal": new_max, "logs": {}}
            save_data(st.session_state["users"])
            st.sidebar.success(f"✅ Added user: {new_user.strip()}")
            st.session_state["user_form_counter"] += 1
            st.rerun()

# --- Edit / Delete Existing User ---
if st.session_state["users"]:
    st.sidebar.divider()
    with st.sidebar.expander("✏️ Edit / Delete User"):
        selected = st.selectbox(
            "Select user",
            list(st.session_state["users"].keys()),
            key="sidebar_select",
        )
        edit_max = st.number_input(
            "Max Calories",
            min_value=0,
            value=st.session_state["users"][selected]["max_cal"],
            step=50,
            key="edit_max_input",
        )
        if st.button("💾 Update Max Calories"):
            st.session_state["users"][selected]["max_cal"] = edit_max
            save_data(st.session_state["users"])
            st.success(f"✅ Updated {selected}'s Max Calories to {edit_max}")
            st.rerun()

        st.divider()
        confirm_delete = st.checkbox(f"Confirm delete '{selected}'?", key="confirm_del")
        if st.button("🗑️ Delete User"):
            if confirm_delete:
                del st.session_state["users"][selected]
                save_data(st.session_state["users"])
                st.session_state["deleted_user"] = True
                st.success(f"✅ Deleted user: {selected}")
                st.rerun()
            else:
                st.warning("⚠️ Please check the confirm box first.")

# =======================
# Main: Log Calories
# =======================
st.header("📝 Log Calories")

if not st.session_state["users"]:
    st.info("ยังไม่มีผู้ใช้ กรุณาเพิ่มผู้ใช้ในแถบด้านซ้ายก่อน")
else:
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        lfc = st.session_state["form_counter"]
        if st.session_state["deleted_user"]:
            st.session_state["form_counter"] += 1
            st.session_state["deleted_user"] = False
            lfc = st.session_state["form_counter"]
        log_user = st.selectbox("Select user", list(st.session_state["users"].keys()), key=f"log_user_{lfc}")

    with col2:
        log_date = st.date_input("Date", value=now.date(), key="log_date")

    with col3:
        fc = st.session_state["form_counter"]
    log_cal = st.number_input("Calories eaten", min_value=0, value=0, step=50, key=f"log_cal_{fc}")
    log_note = st.text_input("Note (optional, e.g. 'Lunch - ข้าวผัด')", key=f"log_note_{fc}")

    if st.button("✅ Add Log", type="primary"):
        if log_cal == 0:
            st.warning("⚠️ Calories is 0 — are you sure?")
        date_str = log_date.strftime("%Y-%m-%d")
        user_logs = st.session_state["users"][log_user]["logs"]
        existing = user_logs.get(date_str, 0)
        user_logs[date_str] = existing + log_cal
        save_data(st.session_state["users"])

        notes_key = f"notes_{log_user}"
        if notes_key not in st.session_state:
            st.session_state[notes_key] = {}
        if log_note.strip():
            prev_note = st.session_state[notes_key].get(date_str, "")
            separator = "\n" if prev_note else ""
            st.session_state[notes_key][date_str] = prev_note + separator + log_note.strip()

        st.success(
            f"✅ Logged **{log_cal} cal** for **{log_user}** on {date_str} "
            f"(รวมวันนี้: {user_logs[date_str]} cal)"
        )
        st.session_state["form_counter"] += 1
        st.rerun()

    if log_user:
        logs = st.session_state["users"][log_user].get("logs", {})
        if logs:
            st.subheader(f"📅 Log History: {log_user}")
            log_df = pd.DataFrame(
                [{"Date": d, "Calories": c} for d, c in sorted(logs.items(), reverse=True)]
            )
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info(f"ยังไม่มี log สำหรับ {log_user}")

# =======================
# Dashboard
# =======================
st.header("📊 Dashboard")

if not st.session_state["users"]:
    st.info("ยังไม่มีข้อมูลผู้ใช้")
else:
    view_mode = st.radio(
        "แสดงข้อมูล",
        ["เฉพาะวันนี้", "รวมทุกวัน"],
        horizontal=True,
        key="dash_mode",
    )

    dashboard_data = []
    for name, u in st.session_state["users"].items():
        if view_mode == "เฉพาะวันนี้":
            total, remain, status = get_remaining(u, today_str)
        else:
            total, remain, status = get_remaining(u)
        dashboard_data.append({
            "Name": name,
            "Max Cal": u.get("max_cal", 0),
            "Eaten": total,
            "Remaining": remain,
            "Status": status,
        })

    df_dash = pd.DataFrame(dashboard_data)

    if not df_dash.empty:
        try:
            styled = df_dash.style.map(color_status, subset=["Status"])
        except AttributeError:
            styled = df_dash.style.applymap(color_status, subset=["Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        fig = px.bar(
            df_dash,
            x="Name",
            y=["Max Cal", "Eaten"],
            barmode="group",
            color_discrete_map={"Max Cal": "#42a5f5", "Eaten": "#ff7043"},
            text_auto=True,
        )
        fig.update_layout(
            title=f"Max Cal vs Eaten ({view_mode})",
            legend_title="Type",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
        csv_download(df_dash, filename="calorie_dashboard.csv")
    else:
        st.info("ไม่มีข้อมูลสำหรับแสดง")
