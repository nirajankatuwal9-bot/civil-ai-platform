import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import os
import io
import bcrypt
import plotly.express as px
from pdf2image import convert_from_path
from google import genai

# ================= CONFIG =================
st.set_page_config(page_title="Civil-AI Professional", page_icon="🏗️", layout="wide")

# Professional CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .status-late { color: #d9534f; font-weight: bold; }
    .status-ontime { color: #5cb85c; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

GEMINI_MODEL = "gemini-3-flash-preview"
client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"))

# ================= DATABASE & DIRECTORIES =================
DB_PATH = "data/lecturer.db"
folders = ["data", "submission_files", "study_materials"]
for f in folders: os.makedirs(f, exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def build_db():
    c.execute("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, semester_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS semesters(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, semester_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, subject_id INTEGER, deadline TEXT, question_file TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER, user_id INTEGER, submission_time TEXT, submission_file TEXT, marks TEXT, ai_feedback TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS study_materials(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, subject_id INTEGER, file_path TEXT, upload_date TEXT)""")
    conn.commit()

build_db()

# ================= UTILITIES =================
def hash_pw(password): return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
def check_pw(password, hashed):
    try: return bcrypt.checkpw(password.encode(), hashed.encode())
    except: return False

def init_system():
    c.execute("SELECT COUNT(*) FROM users WHERE role='lecturer'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", hash_pw("admin123"), "lecturer"))
        c.execute("INSERT INTO semesters (name) VALUES (?)", ("I/I",))
        conn.commit()

init_system()

# ================= AUTHENTICATION =================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": None, "user": None, "user_id": None})

if not st.session_state.logged_in:
    st.title("🏗️ Civil Engineering AI Portal")
    with st.container(border=True):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            res = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(u,))
            if not res.empty and check_pw(p, res.iloc[0]["password"]):
                st.session_state.update({"logged_in": True, "role": res.iloc[0]["role"], "user": res.iloc[0]["username"], "user_id": res.iloc[0]["id"]})
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# ================= LECTURER DASHBOARD =================
if st.session_state.role == "lecturer":
    tabs = st.tabs(["📈 Analytics", "📁 Assignments", "📚 Study Materials", "📝 Submissions", "👥 Students", "⚙️ Setup"])

    # ⚙️ SETUP (Create Semesters & Subjects first!)
    with tabs[5]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Add Semester")
            sem_n = st.text_input("Semester (e.g. I/II)")
            if st.button("Save Semester"):
                try:
                    c.execute("INSERT INTO semesters (name) VALUES (?)", (sem_n,))
                    conn.commit(); st.success("Saved"); st.rerun()
                except: st.error("Duplicate")
        with col2:
            st.subheader("Add Subject")
            sems = pd.read_sql_query("SELECT * FROM semesters", conn)
            if not sems.empty:
                s_sem = st.selectbox("Assign to Semester", sems["name"])
                s_name = st.text_input("Subject Name")
                if st.button("Save Subject"):
                    sid = sems[sems["name"]==s_sem]["id"].values[0]
                    c.execute("INSERT INTO subjects (name, semester_id) VALUES (?,?)", (s_name, int(sid)))
                    conn.commit(); st.success("Saved"); st.rerun()

    # 📁 ASSIGNMENTS (Create & Upload Question)
    with tabs[1]:
        st.subheader("Create New Assignment")
        subs = pd.read_sql_query("SELECT * FROM subjects", conn)
        if not subs.empty:
            a_sub = st.selectbox("Subject", subs["name"], key="asub")
            a_title = st.text_input("Title")
            a_date = st.date_input("Deadline", min_value=date.today())
            a_file = st.file_uploader("Upload Question PDF (Optional)", type="pdf")
            if st.button("Publish Assignment"):
                asid = subs[subs["name"]==a_sub]["id"].values[0]
                f_path = f"submission_files/Q_{a_file.name}" if a_file else ""
                if a_file:
                    with open(f_path, "wb") as f: f.write(a_file.getbuffer())
                c.execute("INSERT INTO assignments (title, subject_id, deadline, question_file) VALUES (?,?,?,?)",
                          (a_title, int(asid), str(a_date), f_path))
                conn.commit(); st.success("Published Successfully!"); st.rerun()
        else: st.warning("Please setup subjects first.")

    # 📝 SUBMISSIONS (AI Grading & Submission Status)
    with tabs[3]:
        st.subheader("Student Submissions")
        query = """
            SELECT s.id, u.username as roll, a.title, a.deadline, s.submission_time, s.submission_file, s.marks 
            FROM submissions s JOIN users u ON s.user_id = u.id JOIN assignments a ON s.assignment_id = a.id
        """
        df_s = pd.read_sql_query(query, conn)
        if not df_s.empty:
            # Add Late/On-Time Logic
            df_s['Status'] = df_s.apply(lambda r: "Late" if r['submission_time'][:10] > r['deadline'] else "On-Time", axis=1)
            st.dataframe(df_s, use_container_width=True)
            
            # Export to CSV
            csv = df_s.to_csv(index=False).encode('utf-8')
            st.download_button("📊 Download Grades (CSV)", csv, "grade_report.csv", "text/csv")
        else: st.info("No submissions yet.")

    # 👥 STUDENTS (CSV Upload & Grouping)
    with tabs[4]:
        st.subheader("Bulk Student Enrollment")
        csv_f = st.file_uploader("Upload CSV (username, password, semester)", type="csv")
        if csv_f:
            df_u = pd.read_csv(csv_f)
            sem_map = pd.read_sql_query("SELECT id, name FROM semesters", conn)
            for _, r in df_u.iterrows():
                try:
                    sem_id = sem_map[sem_map["name"]==str(r['semester']).strip()]["id"].values[0]
                    c.execute("INSERT INTO users (username, password, role, semester_id) VALUES (?,?,?,?)",
                              (str(r['username']), hash_pw(str(r['password'])), "student", int(sem_id)))
                except: pass
            conn.commit(); st.success("Students enrolled and grouped by semester.")

# ================= STUDENT DASHBOARD =================
elif st.session_state.role == "student":
    st.title(f"Student Portal: {st.session_state.user}")
    tabs = st.tabs(["📚 Library", "📝 Submit Work", "📊 My Results"])
    
    # Library Section
    with tabs[0]:
        st.subheader("Study Materials")
        # Logic to fetch materials based on student's semester_id

    # Submission Section
    with tabs[1]:
        st.subheader("Pending Assignments")
        # Logic to filter assignments by student's semester and subject

# ================= SIDEBAR =================
if st.sidebar.button("Hard Reset (Clean Data)"):
    c.execute("DROP TABLE IF EXISTS submissions")
    c.execute("DROP TABLE IF EXISTS users")
    conn.commit(); st.rerun()
