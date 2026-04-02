import streamlit as st
import pandas as pd
import plotly.express as px
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import date
import json

# --- Firebase Setup ---
if not firebase_admin._apps:
    cred = credentials.Certificate(st.secrets["FIREBASE_KEY"])
    firebase_admin.initialize_app(cred)

db = firestore.client()

st.title("Calorie Tracker (Cloud)")

# --- Add User ---
st.sidebar.header("Add User")
new_name = st.sidebar.text_input("Name")
new_max = st.sidebar.number_input("Max Calories", min_value=1, value=2000)

if st.sidebar.button("Add User"):
    if new_name:
        db.collection("users").add({
            "name": new_name,
            "max_calories": new_max
        })
        st.sidebar.success("User added")

# --- Load Users ---
users = db.collection("users").stream()
user_list = [(u.id, u.to_dict()) for u in users]

if not user_list:
    st.warning("Please add a user first")
    st.stop()

names = [u[1]["name"] for u in user_list]
selected_name = st.selectbox("Select User", names)

user_data = next(u for u in user_list if u[1]["name"] == selected_name)
user_id = user_data[0]
max_cal = user_data[1]["max_calories"]

# --- Log Calories ---
st.subheader("Log Calories")
cal = st.number_input("Calories", min_value=0)

if st.button("Add Record"):
    db.collection("records").add({
        "user_id": user_id,
        "record_date": date.today().isoformat(),
        "calories": cal
    })
    st.success("Saved")

# --- Today Summary ---
records = db.collection("records")\
    .where("user_id", "==", user_id)\
    .where("record_date", "==", date.today().isoformat()).stream()

total = sum([r.to_dict()["calories"] for r in records])
remain = max_cal - total
percent = max(0, (remain / max_cal) * 100)

st.subheader("Today")
st.write(f"{total}/{max_cal} kcal")
st.write(f"Remaining: {remain} ({percent:.1f}%)")

# --- History ---
records_all = db.collection("records")\
    .where("user_id", "==", user_id).stream()

history = {}
for r in records_all:
    d = r.to_dict()["record_date"]
    history[d] = history.get(d, 0) + r.to_dict()["calories"]

if history:
    df = pd.DataFrame([
        {"date": k, "total": v, "remain": max_cal-v, "percent": max(0,(max_cal-v)/max_cal*100)}
        for k,v in sorted(history.items())
    ])

    st.subheader("History")
    st.dataframe(df)

    fig = px.bar(df, x="date", y="percent", text=df["percent"].round(1))
    st.plotly_chart(fig)
