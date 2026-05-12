import streamlit as st
import pandas as pd
import psycopg2
import subprocess
from datetime import datetime
import os
import re
from urllib.parse import urlparse
from pdf2image import convert_from_path
import io
import base64
import bcrypt
from PIL import Image
import google.generativeai as genai
import fitz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ================= CONFIG =================

st.set_page_config(
    page_title="The N-streamlines",
    page_icon="🌊",
    layout="wide"
)

# ================= FOLDERS =================

os.makedirs("data", exist_ok=True)
os.makedirs("assignment_files", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)
os.makedirs("study_materials", exist_ok=True)

# ================= DATABASE CONNECTION =================

try:
    DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL"))

    if not DATABASE_URL:
        st.error("🚨 DATABASE_URL not found!")
        st.stop()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    c = conn.cursor()

    # Parse Neon connection for backup system
    parsed = urlparse(DATABASE_URL)
    DB_USER = parsed.username
    DB_PASS = parsed.password
    DB_HOST = parsed.hostname
    DB_PORT = parsed.port
    DB_NAME = parsed.path[1:]

except Exception as e:
    st.error(f"🚨 Database Connection Failed: {e}")
    st.stop()

# ================= SAFE DATABASE FUNCTIONS =================

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

# ================= TABLE CREATION =================

try:
    success, error = db_execute("""
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
    if not success:
        st.error(f"Users table error: {error}")
except Exception as e:
    st.error(f"Users table creation failed: {e}")

db_execute("""
CREATE TABLE IF NOT EXISTS semesters(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
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

# ================= PASSWORD HELPERS =================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, hashed):
    try:
        return bcrypt.checkpw(p.encode(), hashed.encode())
    except:
        return False

# ================= DEFAULT ADMIN =================

admin_exists = db_query(
    "SELECT * FROM users WHERE username=%s",
    params=("admin",)
)

if admin_exists.empty:
    success, erro = db_execute("""
        INSERT INTO users(full_name, username, password, role, semester_id)
        VALUES(%s,%s,%s,%s,%s)
    """, (
        "Administrator",
        "admin",
        hash_password("admin123"),
        "lecturer",
        None
    ))
    if not success:
        st.error(f"Failed to create admin user: {erro}")

# ================= SESSION =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.username = None

# ================= LOGIN =================

if not st.session_state.logged_in:

    st.markdown("## 🌊 THE N-STREAMLINES")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Enter the Flow"):
        res = db_query(
            "SELECT * FROM users WHERE username=%s",
            params=(user,)
        )

        if not res.empty:
            stored_password = res.iloc[0]["password"]

            if check_password(pw, stored_password):
                st.session_state.logged_in = True
                st.session_state.user_id = int(res.iloc[0]["id"])
                st.session_state.role = res.iloc[0]["role"]
                st.session_state.username = res.iloc[0]["username"]
                st.session_state.semester_id = res.iloc[0]["semester_id"]
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")
        else:
            st.error("User not found")

    st.stop()

# ================= SYSTEM & SIDEBAR =================

require_login()

with st.sidebar:
    st.write(f"👤 **{st.session_state.username}** ({str(st.session_state.role).capitalize()})")
    st.divider()
    
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    if st.session_state.role == "lecturer":
        with st.expander("⚙️ Danger Zone"):
            if st.button("🧨 Wipe Database", use_container_width=True):
                tables = ["users", "submissions", "assignments", "subjects", "semesters", "study_materials", "announcements"]
                for t in tables: 
                    db_execute(f"DROP TABLE IF EXISTS {t} CASCADE")
                st.rerun()

    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    st.markdown("""
        <div style='text-align: center; padding: 15px; background-color: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; border-top: 4px solid #004b87;'>
            <h4 style='color: #004b87; margin-bottom: 5px;'>🌊 The N-Streamlines</h4>
            <p style='font-size: 0.85em; color: #555;'>Advanced Hydro-Informatics & Learning Management</p>
            <p style='font-size: 0.8em;'><strong>Er. Nirajan Katuwal</strong></p>
        </div>
    """, unsafe_allow_html=True)

role = st.session_state.role

# ================= ANNOUNCEMENTS =================

def create_announcement(title, message, semester_id, priority, user_id):
    try:
        success, erro = db_execute("""
            INSERT INTO announcements(title, message, semester_id, created_by, created_at, priority)
            VALUES(%s,%s,%s,%s,%s,%s)
        """, (
            title.strip(),
            message.strip(),
            int(semester_id) if semester_id else None,
            int(user_id),
            str(datetime.now()),
            priority
        ))
        return success, "Announcement created successfully" if success else erro
    except Exception as e:
        return False, str(e)


def get_announcements_for_semester(semester_id=None):
    if semester_id:
        return db_query("""
            SELECT announcements.*, users.full_name as author, semesters.name as semester
            FROM announcements
            LEFT JOIN users ON announcements.created_by = users.id
            LEFT JOIN semesters ON announcements.semester_id = semesters.id
            WHERE announcements.semester_id=%s OR announcements.semester_id IS NULL
            ORDER BY announcements.created_at DESC
        """, params=(int(semester_id),))
    else:
        return db_query("""
            SELECT announcements.*, users.full_name as author, semesters.name as semester
            FROM announcements
            LEFT JOIN users ON announcements.created_by = users.id
            LEFT JOIN semesters ON announcements.semester_id = semesters.id
            ORDER BY announcements.created_at DESC
        """)

# ================= EMAIL SYSTEM =================

def send_email_notification(target_semester_id, subject, message_body):
    if target_semester_id:
        df = db_query(
            "SELECT email FROM users WHERE role='student' AND semester_id=%s AND email IS NOT NULL AND email <> ''",
            params=(int(target_semester_id),)
        )
    else:
        df = db_query(
            "SELECT email FROM users WHERE role='student' AND email IS NOT NULL AND email <> ''"
        )

    emails = df['email'].tolist()
    if not emails:
        return False, "No valid student emails found."

    SENDER_EMAIL = st.secrets["EMAIL_USER"]
    APP_PASSWORD = st.secrets["EMAIL_PASSWORD"]

    try:
        msg = MIMEMultipart()
        msg['From'] = f"The N-Streamlines <{SENDER_EMAIL}>"
        msg['Subject'] = subject
        msg.attach(MIMEText(message_body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, emails, msg.as_string())
        server.quit()

        return True, f"Emailed {len(emails)} students."
    except Exception as e:
        return False, str(e)

# ================= BACKUP SYSTEM =================

def create_database_backup():
    try:
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"lecturer_backup_{timestamp}.sql"
        backup_path = os.path.join(backup_dir, backup_filename)

        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASS

        result = subprocess.run(
            ["pg_dump", "-U", DB_USER, "-h", DB_HOST, "-p", str(DB_PORT), "-d", DB_NAME, "-f", backup_path],
            env=env, capture_output=True, text=True
        )

        if result.returncode != 0:
            return False, result.stderr

        return True, f"Backup created: {backup_filename}"
    except Exception as e:
        return False, str(e)

def get_backup_list():
    backup_dir = "data/backups"
    backups = []
    if not os.path.exists(backup_dir):
        return backups

    for filename in os.listdir(backup_dir):
        if filename.endswith(".sql"):
            file_path = os.path.join(backup_dir, filename)
            backups.append({
                "filename": filename,
                "path": file_path,
                "size_kb": round(os.path.getsize(file_path)/1024,2),
                "date": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
            })

    backups.sort(key=lambda x: x["date"], reverse=True)
    return backups

# ================= SEARCH FUNCTIONS =================

def search_students(query, semester_id=None):
    query = query.strip().lower()
    if not query:
        return pd.DataFrame()

    if semester_id:
        return db_query("""
            SELECT users.id, users.full_name, users.username, semesters.name as semester
            FROM users
            LEFT JOIN semesters ON users.semester_id = semesters.id
            WHERE users.role='student'
            AND users.semester_id=%s
            AND (LOWER(users.full_name) LIKE %s OR LOWER(users.username) LIKE %s)
            ORDER BY users.full_name ASC
        """, params=(semester_id, f"%{query}%", f"%{query}%"))
    else:
        return db_query("""
            SELECT users.id, users.full_name, users.username, semesters.name as semester
            FROM users
            LEFT JOIN semesters ON users.semester_id = semesters.id
            WHERE users.role='student'
            AND (LOWER(users.full_name) LIKE %s OR LOWER(users.username) LIKE %s)
            ORDER BY users.full_name ASC
        """, params=(f"%{query}%", f"%{query}%"))

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs = st.tabs(["Assignments", "Study Materials", "My Results"])

    # ================= ASSIGNMENTS =================
    with tabs[0]:

        st.title("📝 My Assignments")

        # Get student's semester
        student_info = db_query(
            "SELECT semester_id FROM users WHERE id=%s",
            params=(int(st.session_state.user_id),)
        )

        if student_info.empty:
            st.error("Student record not found.")
            st.stop()

        sem_id_raw = student_info.iloc[0]["semester_id"]

        if sem_id_raw is None:
            st.warning("You are not assigned to a semester. Please contact your Lecturer.")
            st.stop()

        sem_id = int(sem_id_raw)

        # Load announcements
        announcements = get_announcements_for_semester(sem_id)

        if not announcements.empty:
            st.subheader("📢 Announcements")
            for _, ann in announcements.iterrows():
                if ann['priority'] == 'Urgent':
                    color = '#ff4444'
                    icon = '🚨'
                elif ann['priority'] == 'Important':
                    color = '#ff9800'
                    icon = '⚠️'
                else:
                    color = '#4CAF50'
                    icon = '📢'

                st.markdown(f"""
                <div style='background-color: {color}22; padding: 15px; border-radius: 8px; 
                            border-left: 5px solid {color}; margin-bottom: 10px;'>
                    <h4 style='margin:0; color: white;'>{icon} {ann['title']}</h4>
                    <p style='color: white; margin: 10px 0;'>{ann['message']}</p>
                    <small style='color: #f0f0f0;'>Posted by {ann['author']} on {ann['created_at'][:16]}</small>
                </div>
                """, unsafe_allow_html=True)

            st.divider()

        # Semester name
        semester_info = db_query(
            "SELECT name FROM semesters WHERE id=%s",
            params=(sem_id,)
        )

        if not semester_info.empty:
            st.info(f"📚 Semester: **{semester_info.iloc[0]['name']}**")

        # ================= DEADLINE REMINDERS =================
        st.subheader("⏰ Deadline Reminders")

        all_assignments = db_query("""
            SELECT assignments.id, assignments.title, assignments.deadline,
                   subjects.name as subject
            FROM assignments
            JOIN subjects ON assignments.subject_id = subjects.id
            WHERE subjects.semester_id=%s
            ORDER BY assignments.deadline ASC
        """, params=(sem_id,))

        if not all_assignments.empty:

            overdue, due_today, due_soon, completed = [], [], [], []

            for _, assignment in all_assignments.iterrows():

                submission = db_query("""
                    SELECT id FROM submissions
                    WHERE assignment_id=%s AND student_id=%s
                """, params=(assignment['id'], st.session_state.user_id))

                days, status, _ = get_deadline_status(assignment['deadline'])

                if not submission.empty:
                    completed.append(assignment)
                elif status == "Overdue":
                    overdue.append(assignment)
                elif status == "Due Today":
                    due_today.append(assignment)
                elif status == "Due Soon":
                    due_soon.append(assignment)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🔴 Overdue", len(overdue))
            col2.metric("🟠 Due Today", len(due_today))
            col3.metric("🟡 Due Soon", len(due_soon))
            col4.metric("✅ Completed", len(completed))

            st.divider()

        # ================= ASSIGNMENT LIST =================
        st.subheader("📋 All Assignments")

        assignments = db_query("""
            SELECT assignments.*, subjects.name as subject
            FROM assignments
            JOIN subjects ON assignments.subject_id = subjects.id
            WHERE subjects.semester_id=%s
            ORDER BY assignments.deadline ASC
        """, params=(sem_id,))

        if assignments.empty:
            st.info("No assignments available.")
        else:
            for _, row in assignments.iterrows():

                existing_submission = db_query("""
                    SELECT * FROM submissions
                    WHERE assignment_id=%s AND student_id=%s
                """, params=(row["id"], st.session_state.user_id))

                deadline_display = format_deadline_display(row['deadline'])

                expander_title = f"{row['subject']} - {row['title']} | {deadline_display}"
                if not existing_submission.empty:
                    expander_title = "✅ " + expander_title

                with st.expander(expander_title):

                    # Download question file
                    if row["question_file"] and os.path.exists(row["question_file"]):
                        with open(row["question_file"], "rb") as f:
                            st.download_button(
                                "📥 Download Assignment Question",
                                f,
                                file_name=os.path.basename(row["question_file"])
                            )

                    st.divider()

                    # Check deadline
                    try:
                        deadline_date = datetime.strptime(row['deadline'], '%Y-%m-%d').date()
                        is_late = datetime.now().date() > deadline_date
                    except:
                        is_late = False

                    if not existing_submission.empty:
                        st.success("✅ Already Submitted")

                        marks = existing_submission.iloc[0]["marks"]
                        if marks:
                            st.metric("🎯 Marks", f"{marks}/10")
                        else:
                            st.info("Not graded yet")

                    elif is_late:
                        st.error("🔒 Deadline Locked")

                    else:
                        uploaded = st.file_uploader(
                            "Upload Your Answer PDF",
                            type=["pdf"],
                            key=f"upload_{row['id']}"
                        )

                        if st.button("Submit Assignment", key=f"submit_{row['id']}"):
                            if not uploaded:
                                st.warning("Upload PDF first.")
                            else:
                                file_path = f"submission_files/{st.session_state.username}_{row['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

                                with open(file_path, "wb") as f:
                                    f.write(uploaded.getbuffer())

                                c.execute("""
                                    INSERT INTO submissions(
                                        assignment_id,
                                        student_id,
                                        submission_time,
                                        submission_file,
                                        marks,
                                        ai_summary
                                    )
                                    VALUES(%s,%s,%s,%s,%s,%s)
                                """, (
                                    row["id"],
                                    st.session_state.user_id,
                                    str(datetime.now()),
                                    file_path,
                                    "",
                                    ""
                                ))

                                conn.commit()
                                st.success("✅ Submitted successfully!")
                                st.rerun()

    # ================= STUDY MATERIALS =================
    with tabs[1]:

        st.title("📚 Study Materials")

        materials = db_query("""
            SELECT study_materials.title,
                   subjects.name as subject,
                   study_materials.file_path,
                   study_materials.upload_date,
                   study_materials.description
            FROM study_materials
            JOIN subjects ON study_materials.subject_id = subjects.id
            WHERE study_materials.semester_id=%s
            ORDER BY subjects.name ASC
        """, params=(sem_id,))

        if materials.empty:
            st.info("No materials available.")
        else:
            for _, material in materials.iterrows():
                with st.expander(f"{material['subject']} - {material['title']}"):
                    st.write(f"Uploaded: {material['upload_date']}")
                    if material['description']:
                        st.info(material['description'])

                    if material['file_path'] and os.path.exists(material['file_path']):
                        with open(material['file_path'], "rb") as f:
                            st.download_button(
                                "Download",
                                f,
                                file_name=os.path.basename(material['file_path'])
                            )

    # ================= RESULTS =================
    with tabs[2]:

        st.subheader("📝 My Academic Performance Record")

        results_df = db_query("""
            SELECT subjects.name as Subject,
                   assignments.title as Assignment,
                   assignments.deadline as Deadline,
                   submissions.marks as Marks,
                   submissions.submission_time as Submitted_On
            FROM assignments
            JOIN subjects ON assignments.subject_id = subjects.id
            LEFT JOIN submissions
                ON assignments.id = submissions.assignment_id
                AND submissions.student_id=%s
            WHERE subjects.semester_id=%s
            ORDER BY assignments.deadline DESC
        """, params=(st.session_state.user_id, sem_id))

        if results_df.empty:
            st.info("No assignments yet.")
        else:
            display_data = []
            today = datetime.now().date()

            for _, row in results_df.iterrows():
                deadline_date = datetime.strptime(row['Deadline'], '%Y-%m-%d').date()
                marks = row['Marks']

                if row['Submitted_On'] and marks:
                    status = f"✅ Graded ({marks}/10)"
                elif today > deadline_date:
                    status = "❌ MISSED (Negligence)"
                else:
                    status = "📖 Open for Submission"

                display_data.append({
                    "Subject": row['Subject'],
                    "Assignment": row['Assignment'],
                    "Deadline": row['Deadline'],
                    "Status": status
                })

            st.dataframe(pd.DataFrame(display_data), use_container_width=True)
