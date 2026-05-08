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
                    c.execute("INSERT INTO semesters(name) VALUES(?)", (name.strip(),))
                    conn.commit()
                    st.success("✅ Semester Added")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("⚠️ Semester already exists.")

        st.dataframe(
            pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn),
            use_container_width=True,
            hide_index=True
        )
        st.divider()
        st.subheader("Delete Semester")

        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn) 
        if not sems.empty:
            semester_options={
                f"{row['name']} (ID:{row['id']})": row['id']
                for _, row in sems.iterrows()
            }

            selected_sem = st.selectbox(
                "select Semester to Delete",
                list(semester_options.keys()),
                key="delete_semester"
            )
            if st.button("Delete Selected Semester"):

                sem_id = semester_options[selected_sem]
                subject_ids=pd.read_sql_query(
                    "SELECT id FROM subjects WHERE semester_id=?",
                    conn,
                    params=(int(sem_id),)
                )
                for _, row in subject_ids.iterrows():
                    c.execute("DELETE FROM assignments WHERE subject_id=?", (row["id"],)) 
                c.execute("DELETE FROM subjects WHERE semester_id=?", (sem_id,))
                c.execute("UPDATE users SET semester_id=NULL WHERE semester_id=?", (sem_id,))
                c.execute("DELETE FROM semesters WHERE id=?", (sem_id,))

                conn.commit()
                st.success("✅ Semester deleted successfully.")
                st.rerun()
    # SUBJECTS
    with tabs[1]:
        
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            sem = st.selectbox("Semester", sems["name"], key="subject_semester")
            sem_id = int(sems[sems["name"] == sem]["id"].values[0])

            st.write("DEBUG selected semester id:", sem_id)
            
            sub = st.text_input("Subject Name", key="subject_name")
            
            if st.button("Add Subject"):
                if not sub.strip():
                    st.error("Subject name cannot be empty.")
                else:
                    try:
                        c.execute(
                            "INSERT INTO subjects(name,semester_id) VALUES(?,?)",
                            (sub.strip(), int(sem_id))
                        )
                        conn.commit()
                        st.success("Added")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding subject: {e}")
            st.divider()
            st.subheader("Subjects for Selected Semester")
            subjects_for_sem = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=?",
                conn,
                params=(int(sem_id),)
            )
                
            st.dataframe(
                pd.read_sql_query(
                    "SELECT * FROM subjects WHERE semester_id=?",
                    conn,
                    params=(sem_id,)
                ),
                use_container_width=True,
                hide_index=True
            )
            st.divider()
            st.subheader("All Subjects Debug")
            all_subjects_debug = pd.read_sql_query("SELECT * FROM subjects", conn)
            st.dataframe(all_subjects_debug, use_container_width=True, hide_index=True)
    # ASSIGNMENTS
    with tabs[2]:
# sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        st.subheader("create New Assignment")

        sems = pd.read_sql_query("SELECT * FROM semesters ORDER by name ASC", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            sem_name = st.selectbox("Select Semester", sems["name"], key="assign_sem")
            sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])

            subjects = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=?",
                conn,
                params= (sem_id,)
            )
            #TEMPORARY================
            st.write("DEBUG sem_id:", sem_id)
            st.write("DEBUG subjects returned:", subjects)
            st.write("DEBUG all subjects:", pd.read_sql_query("SELECT * FROM subjects", conn))

            if subjects.empty:
                st.warning("Please create a subject for this semester first.")
            else:
                subject_options = {
                    f"{row['name']} (ID:{row['id']})": row['id']
                    for _, row in subjects.iterrows()
                }

                selected_subject = st.selectbox("Select Subject", list(subject_options.keys()))
                sub_id = int(subject_options[selected_subject])

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
                            """, (title.strip(), int(sub_id), str(deadline), file_path))

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
            st.dataframe(all_assignments, use_container_width=True, hide_index=True)

    # SUBMISSIONS & AI
    with tabs[3]:

        st.subheader("📊 Student Submissions & AI Grading")

        #filter by semester
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if not sems.empty:
            selected_sem = st.selectbox("Filter by Semester", ["All"] + sems["name"].tolist(), key="filter_sem")

            if selected_sem == "All":
                 df = pd.read_sql_query("""
                 SELECT
                     submissions.id,
                     users.username,
                     users.full_name,
                     semesters.name as semester,
                     subjects.name as subject,
                     assignments.title as assignment,
                     submissions.submission_time,
                     submissions.submission_file,
                     submissions.marks,
                     submissions.ai_summary,
                FROM submissions
                JOIN users ON submissions.student_id = users.id 
                JOIN assignments ON submissions.assignment_id = assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN subjects ON assignments.subject_id = subjects.id
                ORDER BY submissions.submission_time DESC
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = pd.read_sql_query("""
                SELECT
                    submissions.id, 
                    users.username,
                    users.full_name,
                    semesters.name as semester,
                    subjects.name as subject,
                    assignments.title as assignment,
                    submissions.submission_time,
                    submissions.submission_file,
                    submissions.marks,
                    submissions.ai_summary
                FROM submissions
                JOIN users ON submissions.student_id = users.id
                JOIN assignments ON submissions.assignment_id = assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                WHERE semesters.id = ?
                ORDER BY submissions.submission_time DESC
                """, conn, params=(sem_id,))
        if df.empty:
            st.info("📭 No submissions yet.")
        else:
            # Display summary
            st.dataframe(
            df[["semester", "subject", "assignment", "username", "full_name", "submission_time", "marks"]],
            use_container_width=True,
            hide_index=True
            )
            st.divider()
            st.subheader("🤖 AI Grading Tool")

            rubric = st.text_area("Enter Model Answer / Rubric for AI Grading (applies to all below)",height=150)
            for _, row in df.iterrows():
                with st.expander(f"👤 {row['username']} - {row['assignment']} ({row['subject']})"):
                    col1,col2 = st.columns([2,1])

                    with col1:
                        st.write(f"**Student:** {row['full_name']} ({row['username']})")
                        st.write(f"**Semester:** {row['semester']}")
                        st.write(f"**Subject:** {row['subject']}")
                        st.write(f"**Assignment:** {row['assignment']}")
                        st.write(f"**Submitted:** {row['submission_time']}")

                        if row['marks'] and str(row['marks']).strip():
                            st.metric("Current Marks", f"{row['marks']}/10")
                        else:
                            st.info("Not graded yet")

                    with col2:
                        if row["submission_file"] and os.path.exists(row["submission_file"]):
                            with open(row["submission_file"], "rb") as f:
                                st.download_button(
                                    "📥 Download Submission", 
                                    f,
                                    file_name=os.path.basename(row["submissions_file"]),
                                    key=f"dl_{row['id']}"
                                )
                    st.divider()

                    #AI Grading 
                    if row["submission_file"] and os.path.exists(row["submission_file"]):
                        col_a, col_b = st.columns(2)
                            
                        with col_a:
                           if st.button (f"🤖 AI Grade", key=f"grade_{row['id']}"):
                                if not rubric.strip():
                                    st.warning("⚠️ Please enter a rubric/model answer first")
                                else:
                                    with st.spinner("AI is grading..."):
                                        try:
                                            result = vision_grade(row["submission_file"],rubric)
                                            st.write("***AI Response:***")
                                            st.write(result)

                                            marks = extract_marks(result)
                                            if marks is not None:
                                                c.execute(
                                                    "UPDATE submissions SET marks=?, ai_summary=? WHERE id=?",
                                                    (marks,result,row["id"])
                                                )
                                                conn.commit()
                                                st.success(f"✅ Updated marks: {marks}/10")
                                                st.rerun()
                                            else:
                                                st.warning("⚠️ Could not extract marks from AI response")
                                        except Exception as e:
                                            st.error(f"Error during AI grading: {e}")
                        with col_b:
                            # Manual grade override
                            manual_marks = st.number_input(
                                 "Or enter marks manually",
                                min_value=0,
                                max_value=10,
                                value=int(row['marks']) if row['marks'] and str(row['marks']).strip() else 0,
                                key=f"manual_{row['id']}"
                           )
                           if st.button("💾 Save Manual Marks", key=f"save_{row['id']}"):
                               c.execute(
                                    "UPDATE submissions SET marks=? WHERE id=?",
                                    (manual_marks, row["id"])
                               )
                               conn.commit()
                               st.success(f"✅ Marks updated to {manual_marks}/10")
                               st.rerun()
                
                # Show previous AI summary if exists
                if row['ai_summary'] and str(row['ai_summary']).strip():
                    with st.expander("📝 Previous AI Feedback"):
                        st.write(row['ai_summary'])
                               
                                            

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
        else:
            st.info("No graded submissions yet.")

    # MANAGE STUDENTS
    with tabs[5]:

        st.subheader("Add Student Manually")

        col1, col2 = st.columns(2)

        with col1:
            student_name = st.text_input("Full Name", key="student_name")
            username = st.text_input("Username", key="student_username")
            password = st.text_input("Password", type="password", key="student_password")

        with col2:
            sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

            if sems.empty:
                st.warning("Please create semesters first.")
            else:
                semester_name = st.selectbox("Assign Semester", sems["name"], key="student_semester")
                semester_id = int(sems[sems["name"] == semester_name]["id"].values[0])  # ← Convert to int

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
                                int(semester_id)  # ← Ensure it's int
                            ))
                            conn.commit()
                            st.success(f"✅ Student '{username}' created and assigned to '{semester_name}'")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already exists.")
                        except Exception as e:
                            st.error(f"Error creating student: {e}")

    st.divider()

    st.subheader("Bulk Upload Students via CSV")
    st.info("CSV format: name,username,password,semester")

    csv_file = st.file_uploader("Upload CSV", type=["csv"], key="student_csv")

    if csv_file:
        df_csv = pd.read_csv(csv_file)
        required_cols = {"name", "username", "password", "semester"}

        if not required_cols.issubset(df_csv.columns):
            st.error("CSV must contain columns: name, username, password, semester")
        else:
            if st.button("Upload Students"):
                sems = pd.read_sql_query("SELECT * FROM semesters", conn)
                success_count = 0
                error_count = 0

                for _, row in df_csv.iterrows():
                    sem_match = sems[sems["name"] == row["semester"]]

                    if sem_match.empty:
                        error_count += 1
                        continue

                    sem_id = int(sem_match["id"].values[0])  # ← Convert to int

                    try:
                        c.execute("""
                        INSERT INTO users(full_name, username, password, role, semester_id)
                        VALUES(?,?,?,?,?)
                        """, (
                            row["name"],
                            row["username"],
                            hash_password(str(row["password"])),
                            "student",
                            int(sem_id)  # ← Ensure int
                        ))
                        success_count += 1
                    except:
                        error_count += 1
                        continue

                conn.commit()
                st.success(f"✅ {success_count} students uploaded successfully. {error_count} failed.")
                st.rerun()

    st.divider()

    st.subheader("Student List")

    students = pd.read_sql_query("""
    SELECT users.id, users.full_name, users.username, users.semester_id, semesters.name as semester
    FROM users
    LEFT JOIN semesters ON users.semester_id = semesters.id
    WHERE users.role='student'
    ORDER BY semesters.name ASC, users.username ASC
    """, conn)

    if students.empty:
        st.info("No students added yet.")
    else:
        # Show debug info
        st.dataframe(
            students[["semester", "username", "full_name", "semester_id"]],
            use_container_width=True,
            hide_index=True
        )

        student_options = {
            f"{row['semester']} | {row['username']} | {row['full_name']}": row['id']
            for _, row in students.iterrows()
        }

        selected_student = st.selectbox(
            "Select Student to Delete",
            list(student_options.keys()),
            key="delete_student_select"
        )

        if st.button("Delete Selected Student"):
            student_id = student_options[selected_student]
            c.execute("DELETE FROM submissions WHERE student_id=?", (student_id,))  # ← Delete submissions first
            c.execute("DELETE FROM users WHERE id=?", (student_id,))
            conn.commit()
            st.success("✅ Student deleted successfully.")
            st.rerun()

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs = st.tabs(["Assignments", "My Results"])

    # ================= ASSIGNMENTS =================
    with tabs[0]:

        # Get student's semester
        student_info = pd.read_sql_query(
            "SELECT semester_id FROM users WHERE id=?",
            conn,
            params=(int(st.session_state.user_id),)
        )

        if student_info.empty:
            st.error("Student record not found.")
            st.stop()

        sem_id = student_info.iloc[0]["semester_id"]

        #Debug- REmove after fixing 
        st.write(f"DEBUG: Your user_id = {st.session_state.user_id}")
        st.write(f"DEBUG: Your semester_id = {sem_id} (type: {type(sem_id)})")

        if sem_id is None or pd.isna(sem_id):
            st.warning("You are not assigned to a semester.Please Contact your Lecturer")
            st.stop()

        sem_id = int(sem_id)

        # Get semester name
        semester_info = pd.read_sql_query(
            "SELECT name FROM semesters WHERE id=?",
            conn,
            params=(sem_id,)
        )
        if not semester_info.empty:
            st.info(f"📚 You are enrolled in: **{semester_info.iloc[0]['name']}**")
            
            
        # Get assignments for student's semester
        assignments = pd.read_sql_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=?
        ORDER BY assignments.deadline ASC
        """, conn, params=(int(sem_id),))

        #Debug - remove after fixing
        st.write(f"DEBUG: Found {len(assignments)} assignments for semester {sem_id}")

        if assignments.empty:
            st.info(" 📭 No assignments available for your semester.")
        else:
            for _, row in assignments.iterrows():

                with st.expander((f"📝 {row['subject']} - {row['title']} (Due: {row['deadline']})"):

                    # ✅ DOWNLOAD ASSIGNMENT FILE
                    if row["question_file"] and os.path.exists(row["question_file"]):
                        with open(row["question_file"], "rb") as f:
                            st.download_button(
                                "📥 Download Assignment",
                                f,
                                file_name=os.path.basename(row["question_file"]),
                                key=f"download_{row['id']}"
                            )
                    else:
                        st.info("No assignment file attached by lecturer.")

                    st.divider()

                    # ✅ CHECK IF ALREADY SUBMITTED
                    existing_submission = pd.read_sql_query("""
                    SELECT * FROM submissions
                    WHERE assignment_id=? AND student_id=?
                    """, conn, params=(int(row["id"], st.session_state.user_id)))

                    if not existing_submission.empty:
                        st.success("✅ You have already submitted this assignment.")

                        submission_time = existing_submission.iloc[0]["submission_time"]
                        st.write(f"**Submitted on:** {submission_time}")

                        # Show marks if graded
                        marks = existing_submission.iloc[0]["marks"]
                        if marks:
                            st.metric(" 🎯 Marks Awarded", f"{marks}/10)
                        else:
                            st.info("⏳ Not graded yet")

                        # Allow download of submitted file
                        submitted_file = existing_submission.iloc[0]["submission_file"]
                        if submitted_file and os.path.exists(submitted_file):
                            with open(submitted_file, "rb") as f:
                                st.download_button(
                                    "Download My Submission",
                                    f,
                                    file_name=os.path.basename(submitted_file),
                                    key=f"download_submission_{row['id']}"
                                )

                    else:
                        # ✅ UPLOAD NEW SUBMISSION
                        uploaded = st.file_uploader(
                            "📤 Upload Your PDF",
                            type=["pdf"],
                            key=f"upload_{row['id']}"
                        )

                        if st.button("Submit Assignment", key=f"submit_{row['id']}"):

                            if not uploaded:
                                st.warning(" ⚠️ Please upload a PDF file before submitting.")
                            else:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                file_path = f"submission_files/{st.session_state.username}_{row['id']}_{timestamp}"

                                with open(file_path, "wb") as f:
                                    f.write(uploaded.getbuffer())

                                c.execute("""
                                INSERT INTO submissions(
                                    assignment_id,
                                    student_id,
                                    submission_time,
                                    submission_file,
                                    marks
                                    ai_summary
                                )
                                VALUES(?,?,?,?,?,?)
                                """, (
                                    int(row["id"]),
                                    int(st.session_state.user_id),
                                    str(datetime.now()),
                                    file_path,
                                    "",
                                    ""
                                ))

                                conn.commit()
                                st.success("✅ Assignment submitted successfully.")
                                st.rerun()

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
