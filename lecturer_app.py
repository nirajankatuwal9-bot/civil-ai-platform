import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import re
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

DB_PATH = "data/lecturer.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# USERS
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT,
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
    try:
        return bcrypt.checkpw(p.encode(), hashed.encode())
    except:
        return False

# ================= DEFAULT LECTURER =================

admin_exists = pd.read_sql_query(
    "SELECT * FROM users WHERE username='admin'",
    conn
)

if admin_exists.empty:
    c.execute("""
    INSERT INTO users(full_name, username, password, role, semester_id)
    VALUES(?,?,?,?,?)
    """, (
        "Administrator",
        "admin",
        hash_password("admin123"),
        "lecturer",
        None
    ))
    conn.commit()

# ================= SESSION =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.username = None

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

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

if role == "student":

    tabs = st.tabs(["Assignments", "My Results"])

    # ================= ASSIGNMENTS =================
    with tabs[0]:

        student_info = pd.read_sql_query(
            "SELECT semester_id FROM users WHERE id=?",
            conn,
            params=(st.session_state.user_id,)
        )

        if student_info.empty:
            st.warning("You are not assigned to a semester.")
            st.stop()

        sem_id = student_info.iloc[0]["semester_id"]

        if sem_id is None:
            st.warning("You are not assigned to a semester.")
            st.stop()

        sem_id = int(sem_id)

        assignments = pd.read_sql_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=?
        ORDER BY assignments.id DESC
        """, conn, params=(sem_id,))

        if assignments.empty:
            st.info("No assignments available for your semester.")
        else:
            for _, row in assignments.iterrows():
                with st.expander(f"{row['title']} (Due: {row['deadline']})"):

                    if row["question_file"] and os.path.exists(row["question_file"]):
                        with open(row["question_file"], "rb") as f:
                            st.download_button(
                                "Download Assignment",
                                f,
                                file_name=os.path.basename(row["question_file"]),
                                key=f"download_{row['id']}"
                            )

                    existing_submission = pd.read_sql_query("""
                    SELECT * FROM submissions
                    WHERE assignment_id=? AND student_id=?
                    """, conn, params=(row["id"], st.session_state.user_id))

                    if not existing_submission.empty:
                        st.success("✅ You have already submitted this assignment.")

                        marks = existing_submission.iloc[0]["marks"]
                        if marks:
                            st.metric("Marks Awarded", marks)

                    else:
                        uploaded = st.file_uploader(
                            "Upload Your PDF",
                            type=["pdf"],
                            key=f"upload_{row['id']}"
                        )

                        if st.button("Submit Assignment", key=f"submit_{row['id']}"):

                            if uploaded:
                                file_path = f"submission_files/{st.session_state.username}_{row['id']}_{uploaded.name}"

                                with open(file_path, "wb") as f:
                                    f.write(uploaded.getbuffer())

                                c.execute("""
                                INSERT INTO submissions(
                                    assignment_id,
                                    student_id,
                                    submission_time,
                                    submission_file,
                                    marks
                                )
                                VALUES(?,?,?,?,?)
                                """, (
                                    row["id"],
                                    st.session_state.user_id,
                                    str(datetime.now()),
                                    file_path,
                                    ""
                                ))

                                conn.commit()
                                st.success("✅ Assignment submitted successfully.")
                                st.rerun()
                            else:
                                st.warning("Please upload a PDF before submitting.")

    # ================= RESULTS =================
    with tabs[1]:

        results = pd.read_sql_query("""
        SELECT assignments.title, submissions.marks
        FROM submissions
        JOIN assignments ON submissions.assignment_id = assignments.id
        WHERE submissions.student_id=?
        ORDER BY submissions.id DESC
        """, conn, params=(st.session_state.user_id,))

        if results.empty:
            st.info("No results available yet.")
        else:
            st.dataframe(results, use_container_width=True, hide_index=True)
