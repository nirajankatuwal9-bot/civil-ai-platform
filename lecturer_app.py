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
# ✅ ONE-TIME DATABASE RESET
if os.path.exists("data/lecturer.db"):
    os.remove("data/lecturer.db")
conn = sqlite3.connect("data/lecturer.db", check_same_thread=False)
c = conn.cursor()
# ✅ CLOUD SAFE MIGRATION FOR full_name COLUMN

columns = pd.read_sql_query("PRAGMA table_info(users);", conn)

if "full_name" not in columns["name"].values:
    c.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
    conn.commit()
# USERS TABLE
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
conn.commit()


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
INSERT OR IGNORE INTO users(full_name,username, password, role, semester_id) 
VALUES(?,?,?, ?, ?)
""", ("Admistrator", "admin", hash_password("admin123"), "lecturer",None))
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

    tabs = st.tabs([
    "Semesters",
    "Subjects",
    "Assignments",
    "Submissions & AI",
    "Analytics",
    "Manage Students"
])

    # SEMESTERS
    with tabs[0]:
        name = st.text_input("New Semester")
        if st.button("Add Semester"):

            if not name.strip():
                st.error("Semester name cannot be empty.")
            else:
                try:
                    c.execute("INSERT INTO semesters(name) Values(?)", (name.strip(),))
                    conn.commit()
                    st.success("✅ Semester Added")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("⚠️Semester already exists.")
                    
            

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

        st.subheader("create New Assignment")

        sems = pd.read_sql_query("SELECT * FROM semesters", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
            st.stop()

        sem_name = st.selectbox("Select Semester", sems["name"], key="assign_sem")
        sem_id = sems[sems["name"] == sem_name]["id"].values[0]

        subjects = pd.read_sql_query(
            "SELECT * FROM subjects WHERE semester_id=?",
            conn,
            params=(sem_id,)
        )

        if subjects.empty:
            st.warning("Please create a subject for this semester first.")
            st.stop()

        subject_options = {
            f"{row['name']} (ID:{row['id']})": row['id']
            for _, row in subjects.iterrows()
        }

        selected_subject = st.selectbox("Select Subject", list(subject_options.keys()))
        sub_id = subject_options[selected_subject]

        title = st.text_input("Assignment Title")
        deadline = st.date_input("Deadline")
        file = st.file_uploader("Upload Assignment PDF", type=["pdf"])

        if st.button("Create Assignment"):

            if not title.strip():
                st.error("Title cannot be empty.")
            else:
                file_path = ""

                if file:
                    file_path = f"assignment_files/{datetime.now().timestamp()}_{file.name}"
                    with open(file_path, "wb") as f:
                        f.write(file.getbuffer())

                try:
                    c.execute("""
                    INSERT INTO assignments(title,subject_id,deadline,question_file)
                    VALUES(?,?,?,?)
                    """, (title.strip(), sub_id, str(deadline), file_path))

                    conn.commit()
                    st.success("✅ Assignment Created Successfully!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()

        st.subheader("Existing Assignments")

        all_assignments = pd.read_sql_query("""
            SELECT id, title, deadline, subject_id
            FROM assignments
            ORDER BY id DESC
        """, conn)

        if all_assignments.empty:
            st.info("No assignments created yet.")
        else:
            st.dataframe(all_assignments, use_container_width=True)

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
        # ===================== MANAGE STUDENTS ====================
    # ==========================================================
    with tabs[5]:

        st.subheader("Add Student Manually")

        col1, col2 = st.columns(2)

        with col1:
            student_name = st.text_input("Full Name")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

        with col2:
            sems = pd.read_sql_query("SELECT * FROM semesters", conn)

            if sems.empty:
                st.warning("Please create semesters first.")
                st.stop()

            semester_name = st.selectbox("Assign Semester", sems["name"])
            semester_id = sems[sems["name"] == semester_name]["id"].values[0]

        if st.button("Create Student"):

            if not username or not password:
                st.error("Username and password required.")
            else:
                try:
                    c.execute("""
                    INSERT INTO users(full_name, username, password, role, semester_id)
                    VALUES(?,?,?,?,?)
                    """, (
                        student_name.strip(),
                        username.strip(),
                        hash_password(password.strip()),
                        "student",
                        int(semester_id)
                    ))
                    conn.commit()
                    st.success("✅ Student created successfully.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Username already exists.")

        st.divider()

        # ================= CSV UPLOAD =================
        st.subheader("Bulk Upload Students via CSV")

        st.info("CSV format: name,username,password,semester")

        csv_file = st.file_uploader("Upload CSV", type=["csv"])

        if csv_file:

            df_csv = pd.read_csv(csv_file)

            required_cols = {"name", "username", "password", "semester"}

            if not required_cols.issubset(df_csv.columns):
                st.error("CSV must contain columns: name, username, password, semester")
            else:
                if st.button("Upload Students"):

                    success_count = 0

                    for _, row in df_csv.iterrows():

                        sem_match = sems[sems["name"] == row["semester"]]

                        if sem_match.empty:
                            continue

                        sem_id = sem_match["id"].values[0]

                        try:
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(?,?,?,?,?)
                            """, (
                                row["name"],
                                row["username"],
                                hash_password(str(row["password"])),
                                "student",
                                sem_id
                            ))
                            success_count += 1

                        except:
                            continue

                    conn.commit()
                    st.success(f"✅ {success_count} students uploaded successfully.")

        st.divider()

        # ================= VIEW STUDENTS =================
        st.subheader("Student List")

        students = pd.read_sql_query("""
        SELECT users.id, users.full_name, users.username, semesters.name as semester
        FROM users
        JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student'
        ORDER BY semesters.name ASC, users.username ASC
        """, conn)

        if students.empty:
            st.info("No students added yet.")
        else:
            st.dataframe(
                students[["semester", "username", "full_name"]],
                use_container_width=True,
                hide_index=True
            )

        # ✅ DELETE SECTION (ONLY INDENT FIXED)
        if not students.empty:

            student_options = {
                f"{row['semester']} | {row['username']} | {row['full_name']}": row['id']
                for _, row in students.iterrows()
            }

            selected_student = st.selectbox(
                "Select Student to Delete",
                list(student_options.keys())
            )

            if st.button("Delete Selected Student"):

                student_id = student_options[selected_student]

                c.execute("DELETE FROM users WHERE id=?", (student_id,))
                conn.commit()

                st.success("✅ Student deleted successfully.")
                st.rerun()
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
