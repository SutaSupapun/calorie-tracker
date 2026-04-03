import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz

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
    """คืนค่า calories ของวันที่ระบุเท่านั้น"""
    return u.get("logs", {}).get(date_str, 0)

def get_total_calories(u):
    """คืนค่า calories รวมทุกวัน"""
    return sum(u.get("logs", {}).values())

def get_remaining(u, date_str=None):
    """
    คำนวณ remaining สำหรับ dashboard
    - ถ้าส่ง date_str → ใช้เฉพาะวันนั้น
    - ถ้าไม่ส่ง → รวมทุกวัน
    """
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
    st.session_state["users"] = {}

if "form_counter" not in st.session_state:
    st.session_state["form_counter"] = 0

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
    new_user = st.text_input("User name", key="new_user_input")
    new_max = st.number_input("Max Calories / day", min_value=0, value=2000, step=50, key="new_max_input")
    if st.button("Add User"):
        if not new_user.strip():
            st.sidebar.error("❌ User name cannot be empty!")
        elif new_user.strip() in st.session_state["users"]:
            st.sidebar.error("❌ User name already exists!")
        else:
            st.session_state["users"][new_user.strip()] = {"max_cal": new_max, "logs": {}}
            st.sidebar.success(f"✅ Added user: {new_user.strip()}")
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
            st.success(f"✅ Updated {selected}'s Max Calories to {edit_max}")
            st.rerun()

        st.divider()
        # ✅ FIX: checkbox ต้องอยู่ก่อน button
        confirm_delete = st.checkbox(f"Confirm delete '{selected}'?", key="confirm_del")
        if st.button("🗑️ Delete User"):
            if confirm_delete:
                del st.session_state["users"][selected]
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
        log_user = st.selectbox("Select user", list(st.session_state["users"].keys()), key="log_user")

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

        # ✅ FIX: บวกสะสม ไม่ทับค่าเดิม
        existing = user_logs.get(date_str, 0)
        user_logs[date_str] = existing + log_cal

        # เก็บ notes แยก
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
        st.session_state["form_counter"] += 1  # ✅ clear Calories & Note
        st.rerun()

    # --- แสดง Log History ของ user ที่เลือก ---
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
    # Toggle: ดูรวมทุกวัน หรือ เฉพาะวันนี้
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

        dashboard_data.append(
            {
                "Name": name,
                "Max Cal": u.get("max_cal", 0),
                "Eaten": total,
                "Remaining": remain,
                "Status": status,
            }
        )

    df_dash = pd.DataFrame(dashboard_data)

    if not df_dash.empty:
        # ✅ FIX: ใช้ st.dataframe + Styler เพื่อแสดงสีได้
        try:
            # pandas >= 2.1
            styled = df_dash.style.map(color_status, subset=["Status"])
        except AttributeError:
            # pandas < 2.1 fallback
            styled = df_dash.style.applymap(color_status, subset=["Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Bar chart
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

        # Export
        csv_download(df_dash, filename="calorie_dashboard.csv")
    else:
        st.info("ไม่มีข้อมูลสำหรับแสดง")
