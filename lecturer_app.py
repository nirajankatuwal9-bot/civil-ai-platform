import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import os
import re
import bcrypt
import time
import io

# ==========================================================
# ================== PAGE CONFIG ===========================
# ==========================================================

st.set_page_config(
    page_title="The N-Streamlines",
    page_icon="🌊",
    layout="wide"
)

# ==========================================================
# ================== DATABASE CONNECTION ===================
# ==========================================================

try:
    DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL"))

    if not DATABASE_URL:
        st.error("🚨 DATABASE_URL not found in Streamlit Secrets!")
        st.stop()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False

except Exception as e:
    st.error(f"🚨 Database Connection Failed: {e}")
    st.stop()

# ==========================================================
# ================== DATABASE HELPERS ======================
# ==========================================================

def db_query(query, params=None):
    try:
        if params:
            return pd.read_sql_query(query, conn, params=params)
        else:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Database Query Error: {e}")
        return pd.DataFrame()

def db_execute(query, params=None):
    try:
        with conn.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)

# ==========================================================
# ================== CREATE TABLES =========================
# ==========================================================

db_execute("""
CREATE TABLE IF NOT EXISTS semesters(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    full_name TEXT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT,
    semester_id INTEGER,
    email TEXT
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS subjects(
    id SERIAL PRIMARY KEY,
    name TEXT,
    semester_id INTEGER
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS assignments(
    id SERIAL PRIMARY KEY,
    title TEXT,
    subject_id INTEGER,
    deadline TEXT,
    question_file TEXT,
    rubric TEXT
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS submissions(
    id SERIAL PRIMARY KEY,
    assignment_id INTEGER,
    student_id INTEGER,
    submission_time TEXT,
    submission_file TEXT,
    marks TEXT,
    ai_summary TEXT
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS announcements(
    id SERIAL PRIMARY KEY,
    title TEXT,
    message TEXT,
    semester_id INTEGER,
    created_by INTEGER,
    created_at TEXT,
    priority TEXT
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS study_materials(
    id SERIAL PRIMARY KEY,
    title TEXT,
    subject_id INTEGER,
    semester_id INTEGER,
    file_path TEXT,
    description TEXT,
    upload_date TEXT,
    uploaded_by INTEGER
)
""")

# ==========================================================
# ================== PASSWORD HELPERS ======================
# ==========================================================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, hashed):
    try:
        return bcrypt.checkpw(p.encode(), hashed.encode())
    except:
        return False

# ==========================================================
# ================== DEFAULT ADMIN =========================
# ==========================================================

admin_check = db_query(
    "SELECT * FROM users WHERE username=%s",
    params=("admin",)
)

if admin_check.empty:
    db_execute("""
        INSERT INTO users(full_name, username, password, role)
        VALUES(%s,%s,%s,%s)
    """, (
        "Administrator",
        "admin",
        hash_password("admin123"),
        "lecturer"
    ))

# ==========================================================
# ================== SESSION CONTROL =======================
# ==========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.username = None

SESSION_TIMEOUT = 1800

def check_session_timeout():
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()
        return True

    if time.time() - st.session_state.last_activity > SESSION_TIMEOUT:
        return False

    st.session_state.last_activity = time.time()
    return True

def require_login():
    if not st.session_state.get("logged_in"):
        st.error("🔒 Please login")
        st.stop()

    if not check_session_timeout():
        st.warning("⏰ Session expired")
        st.session_state.clear()
        st.stop()

# ==========================================================
# ================== LOGIN SYSTEM ==========================
# ==========================================================

if not st.session_state.logged_in:

    st.title("🌊 THE N-STREAMLINES")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        user_data = db_query(
            "SELECT * FROM users WHERE username=%s",
            params=(username,)
        )

        if not user_data.empty:
            stored_pw = user_data.iloc[0]["password"]

            if check_password(password, stored_pw):
                st.session_state.logged_in = True
                st.session_state.user_id = int(user_data.iloc[0]["id"])
                st.session_state.role = user_data.iloc[0]["role"]
                st.session_state.username = user_data.iloc[0]["username"]
                st.session_state.semester_id = user_data.iloc[0]["semester_id"]
                st.session_state.last_activity = time.time()
                st.success("✅ Login Successful")
                st.rerun()
            else:
                st.error("Invalid credentials")
        else:
            st.error("User not found")

    st.stop()

# ==========================================================
# ================== BACKUP SYSTEM (OPTION 1) ==============
# ==========================================================

def create_database_backup():

    backup_dir = "data/backups"
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.sql"
    path = os.path.join(backup_dir, filename)

    try:
        with open(path, "w", encoding="utf-8") as f:
            tables = ["users", "semesters", "subjects", "assignments",
                      "submissions", "announcements", "study_materials"]

            for table in tables:
                df = db_query(f"SELECT * FROM {table}")
                if not df.empty:
                    f.write(f"-- Data for table {table}\n")
                    for _, row in df.iterrows():
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            else:
                                escaped = str(val).replace("'", "''")
                                values.append(f"'{escaped}'")
                        insert = f"INSERT INTO {table} VALUES ({', '.join(values)});\n"
                        f.write(insert)
                    f.write("\n")

        return True, f"Backup created: {filename}"

    except Exception as e:
        return False, str(e)
# ==========================================================
# ================== SIDEBAR ===============================
# ==========================================================

with st.sidebar:
    st.write(f"👤 {st.session_state.username}")
    st.write(f"Role: {st.session_state.role}")

    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()

    st.divider()

    if st.button("📦 Create Backup"):
        success, msg = create_database_backup()
        if success:
            st.success(msg)
        else:
            st.error(msg)

# ==========================================================
# ================== LECTURER PANEL ========================
# ==========================================================

if st.session_state.role == "lecturer":

    tabs = st.tabs([
        "Dashboard",
        "Semesters",
        "Subjects",
        "Assignments",
        "Submissions",
        "Students"
    ])

    # ================= DASHBOARD =================
    with tabs[0]:

        st.title("📊 Dashboard")

        semester_count = db_query("SELECT COUNT(*) as count FROM semesters").iloc[0]["count"]
        student_count = db_query("SELECT COUNT(*) as count FROM users WHERE role='student'").iloc[0]["count"]
        assignment_count = db_query("SELECT COUNT(*) as count FROM assignments").iloc[0]["count"]
        submission_count = db_query("SELECT COUNT(*) as count FROM submissions").iloc[0]["count"]

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Semesters", semester_count)
        col2.metric("Students", student_count)
        col3.metric("Assignments", assignment_count)
        col4.metric("Submissions", submission_count)

    # ================= SEMESTERS =================
    with tabs[1]:

        st.title("🎓 Semester Management")

        new_sem = st.text_input("New Semester Name")

        if st.button("Add Semester"):
            if new_sem.strip():
                success, err = db_execute(
                    "INSERT INTO semesters(name) VALUES(%s)",
                    params=(new_sem.strip(),)
                )
                if success:
                    st.success("Semester added")
                    st.rerun()
                else:
                    st.error(err)

        st.divider()

        semesters = db_query("SELECT * FROM semesters ORDER BY name")

        if not semesters.empty:
            st.dataframe(semesters, use_container_width=True)

    # ================= SUBJECTS =================
    with tabs[2]:

        st.title("📚 Subject Management")

        sems = db_query("SELECT * FROM semesters ORDER BY name")

        if sems.empty:
            st.warning("Create semester first")
        else:
            sem_name = st.selectbox("Select Semester", sems["name"])
            sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])

            subject_name = st.text_input("New Subject")

            if st.button("Add Subject"):
                success, err = db_execute(
                    "INSERT INTO subjects(name, semester_id) VALUES(%s,%s)",
                    params=(subject_name.strip(), sem_id)
                )
                if success:
                    st.success("Subject added")
                    st.rerun()
                else:
                    st.error(err)

            st.divider()

            subjects = db_query(
                "SELECT * FROM subjects WHERE semester_id=%s",
                params=(sem_id,)
            )

            if not subjects.empty:
                st.dataframe(subjects, use_container_width=True)

    # ================= ASSIGNMENTS =================
    with tabs[3]:

        st.title("📝 Assignment Management")

        sems = db_query("SELECT * FROM semesters ORDER BY name")

        if sems.empty:
            st.warning("Create semester first")
        else:
            sem_name = st.selectbox("Semester", sems["name"])
            sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])

            subjects = db_query(
                "SELECT * FROM subjects WHERE semester_id=%s",
                params=(sem_id,)
            )

            if subjects.empty:
                st.warning("Create subject first")
            else:
                subject_name = st.selectbox("Subject", subjects["name"])
                subject_id = int(subjects[subjects["name"] == subject_name]["id"].values[0])

                title = st.text_input("Assignment Title")
                deadline = st.date_input("Deadline")
                rubric = st.text_area("Rubric / Model Answer")

                if st.button("Create Assignment"):
                    success, err = db_execute("""
                        INSERT INTO assignments(title, subject_id, deadline, rubric)
                        VALUES(%s,%s,%s,%s)
                    """, params=(title.strip(), subject_id, str(deadline), rubric.strip()))

                    if success:
                        st.success("Assignment created")
                        st.rerun()
                    else:
                        st.error(err)

            st.divider()

            assignments = db_query("""
                SELECT assignments.id, assignments.title, assignments.deadline,
                       subjects.name as subject
                FROM assignments
                JOIN subjects ON assignments.subject_id = subjects.id
                ORDER BY assignments.deadline DESC
            """)

            if not assignments.empty:
                st.dataframe(assignments, use_container_width=True)

    # ================= SUBMISSIONS =================
    with tabs[4]:

        st.title("📤 Submissions")

        submissions = db_query("""
            SELECT users.username,
                   assignments.title,
                   submissions.marks,
                   submissions.submission_time
            FROM submissions
            JOIN users ON submissions.student_id = users.id
            JOIN assignments ON submissions.assignment_id = assignments.id
            ORDER BY submissions.submission_time DESC
        """)

        if submissions.empty:
            st.info("No submissions yet")
        else:
            st.dataframe(submissions, use_container_width=True)

    # ================= STUDENTS =================
    with tabs[5]:

        st.title("👥 Student Management")

        sems = db_query("SELECT * FROM semesters ORDER BY name")

        if sems.empty:
            st.warning("Create semester first")
        else:
            sem_name = st.selectbox("Assign Semester", sems["name"])
            sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])

            full_name = st.text_input("Full Name")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Create Student"):
                success, err = db_execute("""
                    INSERT INTO users(full_name, username, password, role, semester_id)
                    VALUES(%s,%s,%s,%s,%s)
                """, params=(
                    full_name.strip(),
                    username.strip(),
                    hash_password(password.strip()),
                    "student",
                    sem_id
                ))

                if success:
                    st.success("Student created")
                    st.rerun()
                else:
                    st.error(err)

        st.divider()

        students = db_query("""
            SELECT users.id, users.full_name, users.username,
                   semesters.name as semester
            FROM users
            LEFT JOIN semesters ON users.semester_id = semesters.id
            WHERE users.role='student'
            ORDER BY users.full_name
        """)

        if not students.empty:
            st.dataframe(students, use_container_width=True)
# ==========================================================
# ================== STUDENT PANEL =========================
# ==========================================================

elif st.session_state.role == "student":

    tabs = st.tabs(["My Assignments", "Study Materials", "My Results"])

    # ================= MY ASSIGNMENTS =================
    with tabs[0]:

        st.title("📝 My Assignments")

        # Get student semester
        student_info = db_query(
            "SELECT semester_id FROM users WHERE id=%s",
            params=(int(st.session_state.user_id),)
        )

        if student_info.empty or student_info.iloc[0]["semester_id"] is None:
            st.warning("You are not assigned to a semester.")
            st.stop()

        sem_id = int(student_info.iloc[0]["semester_id"])

        assignments = db_query("""
            SELECT assignments.*, subjects.name as subject
            FROM assignments
            JOIN subjects ON assignments.subject_id = subjects.id
            WHERE subjects.semester_id=%s
            ORDER BY assignments.deadline ASC
        """, params=(sem_id,))

        if assignments.empty:
            st.info("No assignments yet.")
        else:
            for _, row in assignments.iterrows():

                submission = db_query("""
                    SELECT * FROM submissions
                    WHERE assignment_id=%s AND student_id=%s
                """, params=(int(row["id"]), int(st.session_state.user_id)))

                deadline = datetime.strptime(str(row["deadline"]), "%Y-%m-%d").date()
                today = datetime.now().date()
                is_late = today > deadline

                title = f"{row['subject']} - {row['title']} (Due: {row['deadline']})"

                with st.expander(title):

                    # Already submitted
                    if not submission.empty:

                        st.success("✅ Submitted")

                        sub_time = submission.iloc[0]["submission_time"]
                        st.write(f"Submitted on: {sub_time}")

                        marks = submission.iloc[0]["marks"]
                        if marks and str(marks).strip():
                            st.metric("Marks", f"{marks}/10")
                        else:
                            st.info("Not graded yet")

                    # Deadline passed
                    elif is_late:
                        st.error("🔒 Deadline passed. Submission locked.")

                    # Submission open
                    else:
                        uploaded = st.file_uploader(
                            "Upload PDF",
                            type=["pdf"],
                            key=f"upload_{row['id']}"
                        )

                        if st.button("Submit", key=f"submit_{row['id']}"):

                            if not uploaded:
                                st.warning("Upload a PDF first.")
                            else:
                                os.makedirs("submission_files", exist_ok=True)

                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                file_path = f"submission_files/{st.session_state.username}_{row['id']}_{timestamp}.pdf"

                                with open(file_path, "wb") as f:
                                    f.write(uploaded.getbuffer())

                                success, err = db_execute("""
                                    INSERT INTO submissions(
                                        assignment_id,
                                        student_id,
                                        submission_time,
                                        submission_file,
                                        marks,
                                        ai_summary
                                    )
                                    VALUES(%s,%s,%s,%s,%s,%s)
                                """, params=(
                                    int(row["id"]),
                                    int(st.session_state.user_id),
                                    str(datetime.now()),
                                    file_path,
                                    "",
                                    ""
                                ))

                                if success:
                                    st.success("✅ Submitted successfully")
                                    st.balloons()
                                    st.rerun()
                                else:
                                    st.error(err)

    # ================= STUDY MATERIALS =================
    with tabs[1]:

        st.title("📚 Study Materials")

        student_info = db_query(
            "SELECT semester_id FROM users WHERE id=%s",
            params=(int(st.session_state.user_id),)
        )

        if student_info.empty or student_info.iloc[0]["semester_id"] is None:
            st.warning("No semester assigned.")
            st.stop()

        sem_id = int(student_info.iloc[0]["semester_id"])

        materials = db_query("""
            SELECT study_materials.title,
                   study_materials.file_path,
                   study_materials.upload_date,
                   subjects.name as subject
            FROM study_materials
            JOIN subjects ON study_materials.subject_id = subjects.id
            WHERE study_materials.semester_id=%s
            ORDER BY subjects.name, study_materials.upload_date DESC
        """, params=(sem_id,))

        if materials.empty:
            st.info("No study materials yet.")
        else:
            for _, row in materials.iterrows():

                with st.expander(f"{row['subject']} - {row['title']}"):

                    st.write(f"Uploaded: {row['upload_date']}")

                    if row["file_path"] and os.path.exists(row["file_path"]):
                        with open(row["file_path"], "rb") as f:
                            st.download_button(
                                "Download",
                                f,
                                file_name=os.path.basename(row["file_path"])
                            )
                    else:
                        st.error("File not found")

    # ================= MY RESULTS =================
    with tabs[2]:

        st.title("📊 My Results")

        student_info = db_query(
            "SELECT semester_id FROM users WHERE id=%s",
            params=(int(st.session_state.user_id),)
        )

        if student_info.empty or student_info.iloc[0]["semester_id"] is None:
            st.warning("No semester assigned.")
            st.stop()

        sem_id = int(student_info.iloc[0]["semester_id"])

        results = db_query("""
            SELECT subjects.name as subject,
                   assignments.title,
                   assignments.deadline,
                   submissions.marks
            FROM assignments
            JOIN subjects ON assignments.subject_id = subjects.id
            LEFT JOIN submissions
                ON assignments.id = submissions.assignment_id
                AND submissions.student_id=%s
            WHERE subjects.semester_id=%s
            ORDER BY assignments.deadline DESC
        """, params=(int(st.session_state.user_id), sem_id))

        if results.empty:
            st.info("No assignments yet.")
        else:

            display = []

            today = datetime.now().date()

            for _, row in results.iterrows():

                deadline = datetime.strptime(str(row["deadline"]), "%Y-%m-%d").date()
                marks = row["marks"]

                if marks and str(marks).strip():
                    status = f"✅ Graded ({marks}/10)"
                elif today > deadline:
                    status = "❌ Missed (0/10)"
                else:
                    status = "📖 Open"

                display.append({
                    "Subject": row["subject"],
                    "Assignment": row["title"],
                    "Deadline": row["deadline"],
                    "Status": status
                })

            st.dataframe(pd.DataFrame(display), use_container_width=True)
