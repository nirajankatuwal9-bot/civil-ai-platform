import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import re
from difflib import SequenceMatcher
from google import genai
from pdf2image import convert_from_path
import io
import base64
import bcrypt

# ================= CONFIG =================

st.set_page_config(
    page_title="Civil Engineering AI Platform",
    page_icon="🏗️",
    layout="wide"
)

GEMINI_MODEL = "gemini-1.5-flash"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ================= FOLDERS =================

os.makedirs("data", exist_ok=True)
os.makedirs("assignment_files", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)

# ================= DATABASE =================

conn = sqlite3.connect("data/lecturer.db", check_same_thread=False)
c = conn.cursor()

# USERS
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT,
    semester_id INTEGER
)
""")

# SEMESTERS
c.execute("""
CREATE TABLE IF NOT EXISTS semesters(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")

# SUBJECTS
c.execute("""
CREATE TABLE IF NOT EXISTS subjects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    semester_id INTEGER
)
""")

# ASSIGNMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS assignments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    subject_id INTEGER,
    deadline TEXT,
    question_file TEXT
)
""")

# SUBMISSIONS
c.execute("""
CREATE TABLE IF NOT EXISTS submissions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER,
    student_id INTEGER,
    submission_time TEXT,
    submission_file TEXT,
    marks TEXT,
    ai_summary TEXT
)
""")

conn.commit()

# ================= PASSWORD HELPERS =================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, hashed):
    return bcrypt.checkpw(p.encode(), hashed.encode())

# ================= DEFAULT LECTURER =================

admin_check = pd.read_sql_query(
    "SELECT * FROM users WHERE username='admin'",
    conn
)

if admin_check.empty:
    c.execute(
        "INSERT INTO users(username,password,role) VALUES(?,?,?)",
        ("admin", hash_password("admin123"), "lecturer")
    )
    conn.commit()

# ================= SESSION =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================= LOGIN =================

if not st.session_state.logged_in:

    st.title("🏗️ Civil Engineering AI Platform")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):

        df = pd.read_sql_query(
            "SELECT * FROM users WHERE username=?",
            conn,
            params=(user,)
        )

        if not df.empty and check_password(pw, df.iloc[0]["password"]):
            st.session_state.logged_in = True
            st.session_state.user_id = df.iloc[0]["id"]
            st.session_state.role = df.iloc[0]["role"]
            st.session_state.username = df.iloc[0]["username"]
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ================= LOGOUT =================

st.sidebar.write(f"👤 {st.session_state.username} ({st.session_state.role})")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

role = st.session_state.role

# ================= AI FUNCTIONS =================

def vision_grade(pdf_path, rubric):
    images = convert_from_path(pdf_path)
    parts = [{"text": f"""
You are a strict civil engineering professor.

MODEL ANSWER:
{rubric}

Return exactly:
FINAL_MARKS: X/10
FEEDBACK:
- bullet points
"""}]

    for img in images[:3]:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(buffer.getvalue()).decode()
            }
        })

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[{"role": "user", "parts": parts}]
    )

    return response.text

def extract_marks(text):
    m = re.search(r"FINAL_MARKS:\s*(\d+)/10", text)
    return int(m.group(1)) if m else None

# ==========================================================
# ===================== LECTURER ============================
# ==========================================================

if role == "lecturer":

    tabs = st.tabs(["Semesters", "Subjects", "Assignments", "Submissions & AI", "Analytics"])

    # SEMESTERS
    with tabs[0]:
        name = st.text_input("New Semester")
        if st.button("Add Semester"):
            c.execute("INSERT INTO semesters(name) VALUES(?)", (name,))
            conn.commit()
            st.success("Added")
        st.dataframe(pd.read_sql_query("SELECT * FROM semesters", conn))

    # SUBJECTS
    with tabs[1]:
        sems = 
