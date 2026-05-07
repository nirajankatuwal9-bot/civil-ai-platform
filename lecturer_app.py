import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import re
from difflib import SequenceMatcher
from google import genai
from pdf2image import convert_from_path
import random
import io
import base64
import bcrypt

# ================= CONFIG =================

st.set_page_config(
    page_title="Civil Engineering AI Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

GEMINI_MODEL = "gemini-3-flash-preview"
#POPPLER_PATH = r"C:\Program Files\poppler\Library\bin"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ================= FOLDERS =================

os.makedirs("data", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)

DB_PATH = "data/lecturer.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()
# ✅ Cached loader functions (for performance)


def load_semesters():
    return pd.read_sql_query("SELECT * FROM semesters", conn)


def load_subjects():
    return pd.read_sql_query("SELECT * FROM subjects", conn)


def load_assignments():
    return pd.read_sql_query("SELECT * FROM assignments", conn)

def load_subjects_by_semester(semester_id):
    return pd.read_sql_query(
        "SELECT * FROM subjects WHERE semester_id=?", 
        conn, 
        params=(semester_id,)
    )

# ================= DATABASE TABLES =================

# ================= DATABASE TABLES =================

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
    student_name TEXT,
    submission_time TEXT,
    submission_file TEXT,
    marks TEXT,
    ai_summary TEXT
)
""")

# QUIZZES (EXAMS) - FIXED: This is the table for the quiz details
c.execute("""
CREATE TABLE IF NOT EXISTS quizzes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    subject_id INTEGER,
    total_marks INTEGER,
    max_attempts INTEGER,
    duration_minutes INTEGER
)
""")

# MCQ QUESTIONS
c.execute("""
CREATE TABLE IF NOT EXISTS mcq_questions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER,
    question TEXT,
    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,
    correct_answer TEXT
)
""")

# QUIZ ATTEMPTS - Keep only this one copy for student scores
c.execute("""
CREATE TABLE IF NOT EXISTS quiz_attempts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    quiz_id INTEGER,
    score REAL,
    attempt_time TEXT
)
""")
# ✅ ✅ ✅ ADD PERFORMANCE INDEXES HERE ✅ ✅ ✅
c.execute("CREATE INDEX IF NOT EXISTS idx_sub_assignment ON submissions(assignment_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_sub_student ON submissions(student_name)")
c.execute("CREATE INDEX IF NOT EXISTS idx_quiz_user ON quiz_attempts(user_id)")
c.execute("CREATE INDEX IF NOT EXISTS idx_assign_subject ON assignments(subject_id)")
conn.commit()
# ================= PASSWORD SECURITY =================

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, stored_value):
    try:
        # If+-*+- it's already a bcrypt hash
        if stored_value.startswith("$2b$"):
            return bcrypt.checkpw(password.encode(), stored_value.encode())
        else:
            # Old plain text password (legacy)
            return password == stored_value
    except:
        return False
 # ================= AUTO-CREATE DEFAULT USERS =================
# Check if the users table is empty
c.execute("SELECT COUNT(*) FROM users")
if c.fetchone()[0] == 0:
    # Create default Admin/Lecturer
    c.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ("admin", hash_password("admin123"), "lecturer")
    )
    # Create default Student
    c.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        ("student", hash_password("student123"), "student")
    )
    conn.commit()
# ==============================================================

# ================= HEADER =================

# ================= HEADER =================

col1, col2 = st.columns([1,4])

with col1:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=200)

with col2:
    st.markdown("""
    # Civil Engineering AI Platform  
    ### Himalaya College of Engineering
    """)

st.divider()

# --- TEMPORARY DEV TOOL: Delete this after you fix the database! ---
if st.sidebar.button("⚠️ Hard Reset Database"):
    if os.path.exists("data/lecturer.db"):
        os.remove("data/lecturer.db")
        st.sidebar.success("Database deleted! Refresh the page now.")
    else:
        st.sidebar.info("Database doesn't exist yet.")
# -------------------------------------------------------------------

# ================= SESSION =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user = None
    st.session_state.user_id = None

# ================= LOGIN =================

if not st.session_state.logged_in:

    st.subheader("Login")

    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Login"):

        user = pd.read_sql_query(
            "SELECT * FROM users WHERE username=?",
            conn,
            params=(username,)
        )

        if not user.empty:
            stored_hash = user.iloc[0]["password"]

            if check_password(password, stored_hash):
                st.session_state.logged_in = True
                st.session_state.role = user.iloc[0]["role"]
                st.session_state.user = user.iloc[0]["username"]
                st.session_state.user_id = user.iloc[0]["id"]
                st.rerun()
            else:
                st.error("Invalid credentials")
        else:
            st.error("Invalid credentials")

    st.stop()
# ================= LOGOUT =================

st.sidebar.write(f"👤 {st.session_state.user} ({st.session_state.role})")

if st.sidebar.button("Logout"):
    # ✅ Reset exam timer safely
    st.session_state.exam_start_time = None
    
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user = None
    st.session_state.user_id = None
    
    st.rerun()

role = st.session_state.role

# ================= AI FUNCTIONS =================

def vision_grade(pdf_path, rubric):
    try:
        # ✅ FIX: Removed poppler_path so it uses the system installation
        images = convert_from_path(pdf_path)
        
        prompt = f"""
        You are a strict Civil Engineering lecturer.

        MODEL ANSWER/RUBRIC:
        {rubric}

        Return EXACTLY in this format:
        FINAL_MARKS: X/10
        FEEDBACK:
        - bullet points
        """

        # Prepare the parts for the new Google GenAI SDK
        content_parts = [prompt]

        # Convert images to the format Gemini expects
        for img in images[:5]: # Limit to first 5 pages for speed
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            # The new SDK often prefers bytes directly or a specific Part object
            content_parts.append(img) 

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=content_parts
        )

        return response.text

    except Exception as e:
        return f"Error: {e}"

# ✅ HERE IS THE MISSING FUNCTION THAT FIXES THE NAME ERROR
def extract_marks(text):
    match = re.search(r"FINAL_MARKS:\s*(\d+)/(\d+)", text)
    return int(match.group(1)) if match else None

def generate_summary(pdf_path):
    try:
        # ✅ FIX: Removed poppler_path
        images = convert_from_path(pdf_path)
        
        # ✅ FIX: You must pass the images to Gemini, otherwise it can't see the PDF!
        prompt = "Summarize this engineering solution in 8 technical sentences based on the provided images."
        
        content_parts = [prompt] + images[:3] # Sending first 3 pages for a summary
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=content_parts
        )
        return response.text
    except Exception as e:
        return f"Summary Error: {e}"

# ================= LECTURER =================

if role == "lecturer":

    tabs = st.tabs([
        "📅 Semesters",
        "📚 Subjects",
        "📁 Assignments",
        "📝 Submissions & AI",
        "🧪 MCQ Exams",
        "🔎 Plagiarism",
        "📊 Analytics",
        "👥 Manage Students"
    ])

    with tabs[0]:
        ...

    # SEMESTERS
    with tabs[0]:
        sem = st.text_input("New Semester", key="new_sem")
        if st.button("Add Semester"):
            try:
                c.execute("INSERT INTO semesters(name) VALUES(?)",(sem,))
                conn.commit()
                st.success("Added ✅")
            except:
                st.error("Exists")
        st.dataframe(pd.read_sql_query("SELECT * FROM semesters",conn))

    # SUBJECTS
    with tabs[1]:
        sems = load_semesters()
        # SUBJECTS
    with tabs[1]:
        sems = load_semesters()
        if not sems.empty:
            sem_name = st.selectbox("Semester",sems["name"],key="sub_sem")
            sem_id = sems[sems["name"]==sem_name]["id"].values[0]

            subj = st.text_input("New Subject",key="new_subj")
            if st.button("Add Subject"):
                c.execute("INSERT INTO subjects(name,semester_id) VALUES(?,?)",(subj,sem_id))
                conn.commit()
                st.success("Added ✅")
                st.rerun() # ✅ This forces the screen to instantly show the new subject!

            subjects = load_subjects_by_semester(sem_id)
            st.dataframe(subjects)
            st.divider()
        st.subheader("⚠️ Danger Zone: Delete Subject")
        
        all_subjects = pd.read_sql_query("SELECT id, name FROM subjects", conn)
        if not all_subjects.empty:
            subject_to_delete = st.selectbox("Select Subject", all_subjects["name"], key="del_sub")
            if st.button("🗑️ Delete Subject", type="primary"):
                # Find the ID
                sub_id = all_subjects[all_subjects["name"] == subject_to_delete]["id"].values[0]
                
                # Delete it
                c.execute("DELETE FROM subjects WHERE id=?", (int(sub_id),))
                # Also delete assignments tied to it to prevent broken links
                c.execute("DELETE FROM assignments WHERE subject_id=?", (int(sub_id),))
                
                conn.commit()
                st.success(f"'{subject_to_delete}' deleted successfully!")
                st.rerun()
            

    # ASSIGNMENTS
    with tabs[2]:
        subjects = pd.read_sql_query("SELECT * FROM subjects",conn)
        if not subjects.empty:
            sub = st.selectbox("Subject",subjects["name"],key="assign_sub")
            sub_id = subjects[subjects["name"]==sub]["id"].values[0]

            title = st.text_input("Assignment Title",key="assign_title")
            deadline = st.date_input("Deadline",key="assign_deadline")
            
            # ✅ Added File Uploader for Lecturer
            assign_pdf = st.file_uploader("Upload Question/Reference PDF (Optional)", type=["pdf"], key="lecturer_pdf")

            if st.button("Create Assignment"):
                file_path = ""
                
                # If the lecturer uploads a file, save it
                if assign_pdf:
                    file_path = f"submission_files/assignment_{assign_pdf.name}"
                    with open(file_path, "wb") as f:
                        f.write(assign_pdf.getbuffer())

                # Insert into database with the file_path
                c.execute("INSERT INTO assignments(title,subject_id,deadline,question_file) VALUES(?,?,?,?)",
                          (title,sub_id,str(deadline), file_path))
                conn.commit()
                st.success("Created Assignment Successfully ✅")

            st.dataframe(pd.read_sql_query("""
            SELECT assignments.title,subjects.name
            FROM assignments
            JOIN subjects ON assignments.subject_id=subjects.id
            """,conn))
            st.divider()
        st.subheader("⚠️ Danger Zone: Delete Assignment")
        
        all_assigns = pd.read_sql_query("SELECT id, title FROM assignments", conn)
        if not all_assigns.empty:
            assign_to_delete = st.selectbox("Select Assignment", all_assigns["title"], key="del_ass")
            if st.button("🗑️ Delete Assignment", type="primary"):
                ass_id = all_assigns[all_assigns["title"] == assign_to_delete]["id"].values[0]
                
                c.execute("DELETE FROM assignments WHERE id=?", (int(ass_id),))
                # Also remove student submissions for this assignment
                c.execute("DELETE FROM submissions WHERE assignment_id=?", (int(ass_id),))
                
                conn.commit()
                st.success(f"'{assign_to_delete}' deleted successfully!")
                st.rerun()

    # SUBMISSIONS & AI
    with tabs[3]:

    # ✅ Load assignments first
      assignments = pd.read_sql_query(
        "SELECT id, title FROM assignments",
        conn
    )

    if assignments.empty:
        st.info("No assignments available.")
    else:

        selected_assignment = st.selectbox(
            "Select Assignment",
            assignments["title"],
            key="sub_ai_assignment"
        )

        selected_id = assignments[
            assignments["title"] == selected_assignment
        ]["id"].values[0]

        # ✅ Load only submissions for selected assignment
        df = pd.read_sql_query("""
        SELECT id, student_name, submission_time, marks, submission_file
        FROM submissions
        WHERE assignment_id=?
        """, conn, params=(selected_id,))

        st.dataframe(df, use_container_width=True)

        st.divider()

        rubric = st.text_area("Rubric for AI Grading", key="ai_rubric")

        # ✅ AI Grading Loop INSIDE tab
        for _, row in df.iterrows():

            if row["submission_file"] and os.path.exists(row["submission_file"]):

                if st.button(
                    f"AI Grade {row['student_name']}",
                    key=f"grade_{row['id']}"
                ):

                    if row["marks"]:
                        st.info(f"{row['student_name']} already graded ✅")
                    else:
                        result = vision_grade(row["submission_file"], rubric)

                        st.text_area(
                            f"AI Result - {row['student_name']}",
                            result,
                            key=f"result_{row['id']}"
                        )

                        marks = extract_marks(result)

                        if marks:
                            c.execute("""
                            UPDATE submissions
                            SET marks=?
                            WHERE id=?
                            """, (marks, row["id"]))

                            conn.commit()

                            st.success(
                                f"{row['student_name']} → Marks Updated: {marks}"
                            )

    # MCQ EXAMS
    with tabs[4]:
        subjects = pd.read_sql_query("SELECT * FROM subjects",conn)
        if not subjects.empty:
            sub = st.selectbox("Subject",subjects["name"],key="quiz_sub")
            sub_id = subjects[subjects["name"]==sub]["id"].values[0]

            quiz_title = st.text_input("Quiz Title",key="quiz_title")
            total = st.number_input("Total Marks",1,100,20)
            max_attempts = st.number_input("Max Attempts",1,5,1)
            duration_minutes = st.number_input("Duration (Minutes)", 1, 180, 30) # Added this line

            if st.button("Create Quiz"):
                # Updated the SQL query to include duration_minutes
                c.execute("INSERT INTO quizzes(title,subject_id,total_marks,max_attempts,duration_minutes) VALUES(?,?,?,?,?)",
                          (quiz_title,sub_id,total,max_attempts,duration_minutes))
                conn.commit()
                st.success("Created ✅")

    # PLAGIARISM
    with tabs[5]:
        df = pd.read_sql_query("SELECT * FROM submissions",conn)
        if st.button("Generate Summaries"):
            for _,row in df.iterrows():
                if row["submission_file"]:
                    summary = generate_summary(row["submission_file"])
                    if summary:
                        c.execute("UPDATE submissions SET ai_summary=? WHERE id=?",
                                  (summary,row["id"]))
            conn.commit()
            st.success("Summaries Generated ✅")

        results=[]
        for i in range(len(df)):
            for j in range(i+1,len(df)):
                s1=str(df.iloc[i]["ai_summary"])
                s2=str(df.iloc[j]["ai_summary"])
                if s1 and s2:
                    score=SequenceMatcher(None,s1,s2).ratio()
                    results.append({
                        "Student1":df.iloc[i]["student_name"],
                        "Student2":df.iloc[j]["student_name"],
                        "Similarity %":round(score*100,2)
                    })
        if results:
            st.dataframe(pd.DataFrame(results))

    # ANALYTICS
    with tabs[6]:
        df = pd.read_sql_query("""
        SELECT submissions.*,assignments.title
        FROM submissions
        JOIN assignments ON submissions.assignment_id=assignments.id
        """,conn)
        if not df.empty:
            df["marks_num"]=pd.to_numeric(df["marks"],errors="coerce")
            st.bar_chart(df.groupby("title")["marks_num"].mean())
    # MANAGE STUDENTS
  # MANAGE STUDENTS
    with tabs[7]:
        st.subheader("Manage Student Roster")
        
        # Load semesters for the dropdown & matching
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)
        
        if not sems.empty:
            tab_single, tab_bulk = st.tabs(["👤 Add Single Student", "📁 Bulk CSV Upload"])
            
            # --- SINGLE UPLOAD ---
            with tab_single:
                col1, col2, col3 = st.columns(3)
                with col1:
                    new_student_user = st.text_input("Username (Roll No.)", key="new_stu_user")
                with col2:
                    new_student_pass = st.text_input("Password", type="password", key="new_stu_pass")
                with col3:
                    # This will show I/I, I/II, etc.
                    selected_sem = st.selectbox("Assign to Semester", sems["name"], key="new_stu_sem")

                if st.button("Create Student Account"):
                    if new_student_user and new_student_pass:
                        try:
                            sem_id = sems[sems["name"] == selected_sem]["id"].values[0]
                            hashed_pw = hash_password(new_student_pass)
                            
                            c.execute("INSERT INTO users(username, password, role, semester_id) VALUES(?, ?, ?, ?)",
                                      (new_student_user, hashed_pw, "student", int(sem_id)))
                            conn.commit()
                            st.success(f"Student '{new_student_user}' added to {selected_sem}! ✅")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already exists.")
                    else:
                        st.warning("Please fill in all fields.")

            # --- BULK CSV UPLOAD ---
            with tab_bulk:
                st.info("💡 **Tip:** Use your exact Semester names (e.g., `I/I`, `I/II`) in your CSV file.")
                csv_file = st.file_uploader("Upload Student CSV", type=["csv"], key="bulk_csv")
                
                if csv_file and st.button("Process CSV Upload"):
                    try:
                        df_upload = pd.read_csv(csv_file)
                        required_cols = ["username", "password", "semester"]
                        
                        if not all(col in df_upload.columns for col in required_cols):
                            st.error(f"❌ CSV must have: {', '.join(required_cols)}")
                        else:
                            success_count = 0
                            error_list = []
                            
                            for _, row in df_upload.iterrows():
                                user = str(row["username"]).strip()
                                pwd = str(row["password"]).strip()
                                sem_name = str(row["semester"]).strip() # Matches "I/I"
                                
                                matching_sem = sems[sems["name"] == sem_name]
                                if matching_sem.empty:
                                    error_list.append(f"Skipped {user}: Semester '{sem_name}' not found.")
                                    continue
                                
                                sem_id = matching_sem["id"].values[0]
                                try:
                                    c.execute("INSERT INTO users(username, password, role, semester_id) VALUES(?, ?, ?, ?)",
                                              (user, hash_password(pwd), "student", int(sem_id)))
                                    success_count += 1
                                except:
                                    error_list.append(f"Skipped {user}: Duplicate Roll Number.")
                                    
                            conn.commit()
                            if success_count > 0: st.success(f"Added {success_count} students! ✅")
                            if error_list: st.warning("\n".join(error_list))
                    except Exception as e:
                        st.error(f"Error: {e}")

        else:
            st.warning("⚠️ Please create Semesters (like I/I, I/II) first.")

        st.divider()
        st.subheader("⚠️ Danger Zone: Remove Student")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Create a dropdown of all current students
            all_students = pd.read_sql_query("SELECT username FROM users WHERE role='student'", conn)
            if not all_students.empty:
                student_to_delete = st.selectbox("Select Student to Remove", all_students["username"])
        
        with col2:
            st.write("") # Spacing
            st.write("") # Spacing
            if 'student_to_delete' in locals() and st.button("🗑️ Delete Student", type="primary"):
                try:
                    c.execute("DELETE FROM users WHERE username=?", (student_to_delete,))
                    conn.commit()
                    st.success(f"{student_to_delete} has been removed from the system.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        # --- VIEW STUDENTS (SORTED) ---
        st.subheader("Master Student Roster")
        if not sems.empty:
            students_df = pd.read_sql_query("""
                SELECT semesters.name AS Semester, users.username AS 'Roll Number'
                FROM users 
                JOIN semesters ON users.semester_id = semesters.id
                WHERE users.role = 'student'
                ORDER BY semesters.name ASC, users.username ASC
            """, conn)
            
            if not students_df.empty:
                st.dataframe(students_df, use_container_width=True, hide_index=True)

        
# ================= STUDENT =================
elif role == "student":

    tabs = st.tabs(["📝 Submit Assignment","🧪 Take Exam","📊 My Results"])

    # SUBMIT
    with tabs[0]:
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)
        if not sems.empty:
            sem = st.selectbox("Semester", sems["name"])
            sem_id = sems[sems["name"] == sem]["id"].values[0]

            subjects = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=?", conn, params=(int(sem_id),))
            if not subjects.empty:
                sub = st.selectbox("Subject", subjects["name"])
                sub_id = subjects[subjects["name"] == sub]["id"].values[0]

                assigns = pd.read_sql_query("SELECT * FROM assignments WHERE subject_id=?", conn, params=(int(sub_id),))
                
                if not assigns.empty:
                    st.subheader(f"📚 Pending Assignments for {sub}")
                    
                    # ✅ THIS IS THE NEW ASSIGNMENT CARD LAYOUT
                    for _, row in assigns.iterrows():
                        with st.expander(f"📌 {row['title']} (Due: {row['due_date']})"):
                            st.markdown("**Instructions:**")
                            st.write(row['description'])
                            st.divider()
                            
                            pdf = st.file_uploader(f"Upload PDF for {row['title']}", type=["pdf"], key=f"up_{row['id']}")
                            
                            if st.button("Submit", key=f"btn_{row['id']}"):
                                if pdf:
                                    # Ensure the folder exists so it doesn't crash
                                    if not os.path.exists("submission_files"):
                                        os.makedirs("submission_files")
                                        
                                    path = f"submission_files/{st.session_state.user}_{pdf.name}"
                                    with open(path, "wb") as f:
                                        f.write(pdf.getbuffer())
                                        
                                    c.execute("""
                                    INSERT INTO submissions(assignment_id, student_name, submission_time, submission_file, marks) 
                                    VALUES(?,?,?,?,?)
                                    """, (int(row['id']), st.session_state.user, str(datetime.now()), path, ""))
                                    conn.commit()
                                    st.success(f"Submitted '{row['title']}' Successfully! ✅")
                                else:
                                    st.warning("Please upload a PDF first.")
                else:
                    st.info(f"No assignments posted yet for {sub}.")
            else:
                st.info("No subjects found for this semester.")
        else:
            st.info("No semesters available.")

    # EXAM
    with tabs[1]:
        quizzes = pd.read_sql_query("SELECT * FROM quizzes", conn)

        if not quizzes.empty:
            sel = st.selectbox("Select Quiz", quizzes["title"], key="student_quiz")
            quiz = quizzes[quizzes["title"] == sel].iloc[0]

            # ✅ Attempt Limit Check
            prev = pd.read_sql_query(
                "SELECT * FROM quiz_attempts WHERE user_id=? AND quiz_id=?",
                conn, (st.session_state.user_id, int(quiz["id"]))
            )

            if len(prev) >= quiz["max_attempts"]:
                st.error("⛔ Attempt limit reached.")
            else:
                # ✅ TIMER START
                if "exam_start_time" not in st.session_state or st.session_state.exam_start_time is None:
                    st.session_state.exam_start_time = datetime.now()

                duration_seconds = quiz["duration_minutes"] * 60
                elapsed = (datetime.now() - st.session_state.exam_start_time).seconds
                remaining = duration_seconds - elapsed

                if remaining <= 0:
                    st.error("⏰ Time is up! Auto-submitting...")
                    remaining = 0

                minutes = remaining // 60
                seconds = remaining % 60

                st.warning(f"⏳ Time Remaining: {minutes:02d}:{seconds:02d}")

                # ✅ Load Questions
                questions = pd.read_sql_query(
                    "SELECT * FROM mcq_questions WHERE quiz_id=?",
                    conn, (int(quiz["id"]),)
                )

                score = 0
                answers = {}

                for _, row in questions.iterrows():
                    options = ["A", "B", "C", "D"]
                    # If you want to shuffle options, you need to tie them to actual answer text,
                    # but keeping standard A, B, C, D is safest for basic MCQs.
                    ans = st.radio(row["question"], options, key=f"q_{row['id']}")
                    answers[row["id"]] = ans

                # ✅ Submit OR Auto Submit
                if st.button("Submit Exam") or remaining <= 0:

                    for _, row in questions.iterrows():
                        if answers.get(row["id"]) == row["correct_answer"]:
                            score += 1

                    final = (score / len(questions)) * quiz["total_marks"]

                    c.execute("""
                    INSERT INTO quiz_attempts(user_id, quiz_id, score, attempt_time)
                    VALUES (?, ?, ?, ?)
                    """, (
                        st.session_state.user_id,
                        int(quiz["id"]),
                        round(final, 2),
                        str(datetime.now())
                    ))

                    conn.commit()

                    st.success(f"✅ Final Marks: {round(final,2)}")

                    # ✅ Reset Timer
                    st.session_state.exam_start_time = None
                    st.stop()
        else:
            st.info("No exams available right now.")

    # RESULTS
    with tabs[2]:
        results = pd.read_sql_query("""
        SELECT quizzes.title, quiz_attempts.score
        FROM quiz_attempts
        JOIN quizzes ON quiz_attempts.quiz_id = quizzes.id
        WHERE quiz_attempts.user_id = ?
        """, conn, params=(st.session_state.user_id,))
        
        if not results.empty:
            st.dataframe(results, use_container_width=True, hide_index=True)
        else:
            st.info("You haven't taken any exams yet.")
