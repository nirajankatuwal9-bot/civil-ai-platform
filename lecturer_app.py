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
POPPLER_PATH = r"C:\Program Files\poppler\Library\bin"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ================= FOLDERS =================

os.makedirs("data", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)

DB_PATH = "data/lecturer.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# ================= DATABASE TABLES =================

# ================= DATABASE TABLES =================

# USERS
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
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
    deadline TEXT
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

# QUIZZES (EXAMS)
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

# QUIZ ATTEMPTS
c.execute("""
CREATE TABLE IF NOT EXISTS quiz_attempts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    quiz_id INTEGER,
    score REAL,
    attempt_time TEXT
)
""")

conn.commit()
# ================= PASSWORD SECURITY =================

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

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
        images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        prompt = f"""
You are a strict Civil Engineering lecturer.

MODEL ANSWER:
{rubric}

Return EXACTLY:
FINAL_MARKS: X/10
FEEDBACK:
- bullet points
"""

        content = [{"type":"text","text":prompt}]

        for img in images[:5]:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            content.append({
                "type":"image",
                "source":{"mime_type":"image/png","data":img_b64}
            })

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[{"role":"user","parts":content}]
        )

        return response.text

    except Exception as e:
        return f"Error: {e}"

def extract_marks(text):
    match = re.search(r"FINAL_MARKS:\s*(\d+)/(\d+)", text)
    return int(match.group(1)) if match else None

def generate_summary(pdf_path):
    try:
        images = convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        prompt = "Summarize this engineering solution in 8 technical sentences."
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text
    except:
        return None

# ================= LECTURER =================

if role == "lecturer":

    tabs = st.tabs([
        "📅 Semesters",
        "📚 Subjects",
        "📁 Assignments",
        "📝 Submissions & AI",
        "🧪 MCQ Exams",
        "🔎 Plagiarism",
        "📊 Analytics"
    ])

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
        sems = pd.read_sql_query("SELECT * FROM semesters",conn)
        if not sems.empty:
            sem_name = st.selectbox("Semester",sems["name"],key="sub_sem")
            sem_id = sems[sems["name"]==sem_name]["id"].values[0]

            subj = st.text_input("New Subject",key="new_subj")
            if st.button("Add Subject"):
                c.execute("INSERT INTO subjects(name,semester_id) VALUES(?,?)",(subj,sem_id))
                conn.commit()
                st.success("Added ✅")

            st.dataframe(pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=?",conn,(sem_id,)
            ))

    # ASSIGNMENTS
    with tabs[2]:
        subjects = pd.read_sql_query("SELECT * FROM subjects",conn)
        if not subjects.empty:
            sub = st.selectbox("Subject",subjects["name"],key="assign_sub")
            sub_id = subjects[subjects["name"]==sub]["id"].values[0]

            title = st.text_input("Assignment Title",key="assign_title")
            deadline = st.date_input("Deadline",key="assign_deadline")

            if st.button("Create Assignment"):
                c.execute("INSERT INTO assignments(title,subject_id,deadline) VALUES(?,?,?)",
                          (title,sub_id,str(deadline)))
                conn.commit()
                st.success("Created ✅")

            st.dataframe(pd.read_sql_query("""
            SELECT assignments.title,subjects.name
            FROM assignments
            JOIN subjects ON assignments.subject_id=subjects.id
            """,conn))

    # SUBMISSIONS & AI
    with tabs[3]:
        df = pd.read_sql_query("""
        SELECT submissions.*,assignments.title
        FROM submissions
        JOIN assignments ON submissions.assignment_id=assignments.id
        """,conn)

        st.dataframe(df)

        rubric = st.text_area("Rubric")

        for _,row in df.iterrows():
            if row["submission_file"] and os.path.exists(row["submission_file"]):
                if st.button(f"AI Grade {row['student_name']}",key=f"grade_{row['id']}"):
                    result = vision_grade(row["submission_file"],rubric)
                    st.text_area("Result",result)
                    marks = extract_marks(result)
                    if marks:
                        c.execute("UPDATE submissions SET marks=? WHERE id=?",
                                  (marks,row["id"]))
                        conn.commit()
                        st.success(f"Marks Updated: {marks}")

    # MCQ EXAMS
    with tabs[4]:
        subjects = pd.read_sql_query("SELECT * FROM subjects",conn)
        if not subjects.empty:
            sub = st.selectbox("Subject",subjects["name"],key="quiz_sub")
            sub_id = subjects[subjects["name"]==sub]["id"].values[0]

            quiz_title = st.text_input("Quiz Title",key="quiz_title")
            total = st.number_input("Total Marks",1,100,20)
            max_attempts = st.number_input("Max Attempts",1,5,1)

            if st.button("Create Quiz"):
                c.execute("INSERT INTO quizzes(title,subject_id,total_marks,max_attempts) VALUES(?,?,?,?)",
                          (quiz_title,sub_id,total,max_attempts))
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

# ================= STUDENT =================

elif role == "student":

    tabs = st.tabs(["📝 Submit Assignment","🧪 Take Exam","📊 My Results"])

    # SUBMIT
    with tabs[0]:
        sems=pd.read_sql_query("SELECT * FROM semesters",conn)
        if not sems.empty:
            sem=st.selectbox("Semester",sems["name"])
            sem_id=sems[sems["name"]==sem]["id"].values[0]

            subjects=pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=?",conn,(sem_id,))
            if not subjects.empty:
                sub=st.selectbox("Subject",subjects["name"])
                sub_id=subjects[subjects["name"]==sub]["id"].values[0]

                assigns=pd.read_sql_query("SELECT * FROM assignments WHERE subject_id=?",conn,(sub_id,))
                if not assigns.empty:
                    sel=st.selectbox("Assignment",assigns["title"])
                    pdf=st.file_uploader("Upload PDF",type=["pdf"])
                    if st.button("Submit"):
                        if pdf:
                            path=f"submission_files/{st.session_state.user}_{pdf.name}"
                            with open(path,"wb") as f:
                                f.write(pdf.getbuffer())
                            aid=assigns[assigns["title"]==sel]["id"].values[0]
                            c.execute("INSERT INTO submissions(assignment_id,student_name,submission_time,submission_file,marks) VALUES(?,?,?,?,?)",
                                      (aid,st.session_state.user,str(datetime.now()),path,""))
                            conn.commit()
                            st.success("Submitted ✅")

    # EXAM
    # EXAM
with tabs[1]:

    quizzes = pd.read_sql_query("SELECT * FROM quizzes", conn)

    if not quizzes.empty:

        sel = st.selectbox("Select Quiz", quizzes["title"], key="student_quiz")
        quiz = quizzes[quizzes["title"] == sel].iloc[0]

        # ✅ Attempt Limit Check
        prev = pd.read_sql_query(
            "SELECT * FROM quiz_attempts WHERE user_id=? AND quiz_id=?",
            conn, (st.session_state.user_id, quiz["id"])
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
                conn, (quiz["id"],)
            )

            score = 0
            answers = {}

            for _, row in questions.iterrows():
                options = ["A", "B", "C", "D"]
                random.shuffle(options)

                ans = st.radio(row["question"], options, key=row["id"])
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
                    quiz["id"],
                    round(final, 2),
                    str(datetime.now())
                ))

                conn.commit()

                st.success(f"✅ Final Marks: {round(final,2)}")

                # ✅ Reset Timer
                st.session_state.exam_start_time = None

                st.stop()

    # RESULTS
    with tabs[2]:
        results=pd.read_sql_query("""
        SELECT quizzes.title,quiz_attempts.score
        FROM quiz_attempts
        JOIN quizzes ON quiz_attempts.quiz_id=quizzes.id
        WHERE quiz_attempts.user_id=?
        """,conn,params=(st.session_state.user_id,))
        st.dataframe(results)
