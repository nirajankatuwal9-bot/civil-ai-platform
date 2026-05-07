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

c.execute("""
INSERT OR IGNORE INTO users(username, password, role) 
VALUES(?, ?, ?)
""", ("admin", hash_password("admin123"), "lecturer"))
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
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)

        if not sems.empty:
            sem = st.selectbox("Semester", sems["name"])
            sem_id = sems[sems["name"] == sem]["id"].values[0]

            sub = st.text_input("Subject Name")
            if st.button("Add Subject"):
                c.execute("INSERT INTO subjects(name,semester_id) VALUES(?,?)",
                          (sub, sem_id))
                conn.commit()
                st.success("Added")

            st.dataframe(pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=?",
                conn,
                params=(sem_id,)
            ))

    # ASSIGNMENTS
    with tabs[2]:
        subjects = pd.read_sql_query("""
        SELECT subjects.id, subjects.name, semesters.name as semester
        FROM subjects
        JOIN semesters ON subjects.semester_id=semesters.id
        """, conn)

        if not subjects.empty:
            sub = st.selectbox(
                "Subject",
                subjects["semester"] + " - " + subjects["name"]
            )

            sub_id = subjects.iloc[
                (subjects["semester"] + " - " + subjects["name"] == sub).idxmax()
            ]["id"]

            title = st.text_input("Assignment Title")
            deadline = st.date_input("Deadline")
            file = st.file_uploader("Upload Question PDF", type=["pdf"])

            if st.button("Create Assignment"):
                path = ""
                if file:
                    path = f"assignment_files/{file.name}"
                    with open(path, "wb") as f:
                        f.write(file.getbuffer())

                c.execute("""
                INSERT INTO assignments(title,subject_id,deadline,question_file)
                VALUES(?,?,?,?)
                """, (title, sub_id, str(deadline), path))

                conn.commit()
                st.success("Assignment Created")

    # SUBMISSIONS & AI
    with tabs[3]:
        df = pd.read_sql_query("""
        SELECT submissions.id, users.username, assignments.title,
               submissions.submission_file, submissions.marks
        FROM submissions
        JOIN users ON submissions.student_id = users.id
        JOIN assignments ON submissions.assignment_id = assignments.id
        """, conn)

        st.dataframe(df)

        rubric = st.text_area("Rubric for AI grading")

        for _, row in df.iterrows():
            if row["submission_file"] and os.path.exists(row["submission_file"]):
                if st.button(f"AI Grade {row['username']}", key=row["id"]):
                    result = vision_grade(row["submission_file"], rubric)
                    st.write(result)
                    marks = extract_marks(result)
                    if marks:
                        c.execute("UPDATE submissions SET marks=? WHERE id=?",
                                  (marks, row["id"]))
                        conn.commit()

    # ANALYTICS
    with tabs[4]:
        df = pd.read_sql_query("""
        SELECT assignments.title, submissions.marks
        FROM submissions
        JOIN assignments ON submissions.assignment_id=assignments.id
        """, conn)

        if not df.empty:
            df["marks"] = pd.to_numeric(df["marks"], errors="coerce")
            st.bar_chart(df.groupby("title")["marks"].mean())

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs = st.tabs(["Assignments", "My Results"])

    with tabs[0]:

        student = pd.read_sql_query(
            "SELECT semester_id FROM users WHERE id=?",
            conn,
            params=(st.session_state.user_id,)
        )

        if student.empty or student.iloc[0]["semester_id"] is None:
            st.warning("You are not assigned to a semester.")
            st.stop()

        sem_id = student.iloc[0]["semester_id"]

        assignments = pd.read_sql_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id=subjects.id
        WHERE subjects.semester_id=?
        """, conn, params=(sem_id,))

        for _, row in assignments.iterrows():
            with st.expander(row["title"]):

                if row["question_file"] and os.path.exists(row["question_file"]):
                    with open(row["question_file"], "rb") as f:
                        st.download_button(
                            "Download Assignment",
                            f,
                            file_name=os.path.basename(row["question_file"])
                        )

                uploaded = st.file_uploader("Upload Your PDF", type=["pdf"], key=row["id"])

                if st.button("Submit", key=f"submit{row['id']}"):
                    if uploaded:
                        path = f"submission_files/{st.session_state.username}_{uploaded.name}"
                        with open(path, "wb") as f:
                            f.write(uploaded.getbuffer())

                        c.execute("""
                        INSERT INTO submissions(assignment_id,student_id,
                        submission_time,submission_file,marks)
                        VALUES(?,?,?,?,?)
                        """, (row["id"], st.session_state.user_id,
                              str(datetime.now()), path, ""))

                        conn.commit()
                        st.success("Submitted")

    with tabs[1]:
        results = pd.read_sql_query("""
        SELECT assignments.title, submissions.marks
        FROM submissions
        JOIN assignments ON submissions.assignment_id=assignments.id
        WHERE submissions.student_id=?
        """, conn, params=(st.session_state.user_id,))

        st.dataframe(results)
