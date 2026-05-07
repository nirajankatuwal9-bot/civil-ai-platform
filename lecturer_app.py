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
st.set_page_config(page_title="Civil-AI Pro", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .card { background-color: white; padding: 20px; border-radius: 10px; border-left: 5px solid #004b87; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

GEMINI_MODEL = "gemini-3-flash-preview"
client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"))

# ================= DB & FOLDERS =================
DB_PATH = "data/lecturer.db"
for folder in ["data", "submission_files", "study_materials"]:
    os.makedirs(folder, exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def build_db():
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, semester_id INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS semesters(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
    c.execute("CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, semester_id INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, subject_id INTEGER, deadline TEXT, question_file TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER, user_id INTEGER, submission_time TEXT, submission_file TEXT, marks TEXT, ai_feedback TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS study_materials(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, subject_id INTEGER, file_path TEXT, upload_date TEXT)")
    conn.commit()

build_db()

# ================= UTILS =================
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

# ================= LOGIN =================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": None, "user": None, "user_id": None, "semester_id": None})

if not st.session_state.logged_in:
    st.title("🏗️ Civil-AI Institutional Portal")
    with st.container(border=True):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            res = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(u,))
            if not res.empty and check_pw(p, res.iloc[0]["password"]):
                st.session_state.update({
                    "logged_in": True, "role": res.iloc[0]["role"], 
                    "user": res.iloc[0]["username"], "user_id": res.iloc[0]["id"],
                    "semester_id": res.iloc[0]["semester_id"]
                })
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# ================= LECTURER =================
if st.session_state.role == "lecturer":
    tabs = st.tabs(["📊 Analytics", "📚 Materials", "📁 Assignments", "📝 Submissions", "👥 Students", "⚙️ Setup"])

    with tabs[3]: # Submissions View
        st.subheader("Student Submissions")
        # Fixed Query: Ensure columns match DB
        df_s = pd.read_sql_query("""
            SELECT s.id, u.username as roll, a.title, s.submission_time, s.submission_file, s.marks, s.ai_feedback 
            FROM submissions s 
            JOIN users u ON s.user_id = u.id 
            JOIN assignments a ON s.assignment_id = a.id
        """, conn)
        
        if not df_s.empty:
            for _, row in df_s.iterrows():
                with st.expander(f"📄 {row['roll']} - {row['title']}"):
                    st.write(f"**Grade:** {row['marks'] or 'Pending'}")
                    st.write(f"**Feedback:** {row['ai_feedback'] or 'No feedback yet'}")
                    if os.path.exists(str(row['submission_file'])):
                        with open(str(row['submission_file']), "rb") as f:
                            st.download_button("Download Work", f, file_name=f"{row['roll']}.pdf", key=f"dl_{row['id']}")
        else: st.info("No submissions found.")

    with tabs[5]: # Setup
        col1, col2 = st.columns(2)
        with col1:
            st.write("### Add Semester")
            sn = st.text_input("Semester Name")
            if st.button("Add Sem"):
                c.execute("INSERT INTO semesters (name) VALUES (?)", (sn,))
                conn.commit(); st.rerun()
        with col2:
            st.write("### Add Subject")
            sems = pd.read_sql_query("SELECT * FROM semesters", conn)
            if not sems.empty:
                s_sem = st.selectbox("Assign to Semester", sems["name"])
                s_name = st.text_input("Subject Name")
                if st.button("Add Sub"):
                    sid = sems[sems["name"]==s_sem]["id"].values[0]
                    c.execute("INSERT INTO subjects (name, semester_id) VALUES (?,?)", (s_name, int(sid)))
                    conn.commit(); st.rerun()

# ================= STUDENT =================
elif st.session_state.role == "student":
    curr_sid = st.session_state.semester_id
    st.title(f"Student Portal: {st.session_state.user}")
    
    if not curr_sid:
        st.warning("⚠️ You are not assigned to a semester. Please contact the lecturer.")
    else:
        st_tabs = st.tabs(["📚 Library", "📝 My Assignments", "📊 Results"])

        with st_tabs[0]: # Library
            mats = pd.read_sql_query("""
                SELECT sm.title, sm.file_path, s.name as subject FROM study_materials sm 
                JOIN subjects s ON sm.subject_id = s.id WHERE s.semester_id = ?
            """, conn, params=(int(curr_sid),))
            if not mats.empty:
                for _, m in mats.iterrows():
                    with st.container(border=True):
                        st.write(f"📖 **{m['title']}** ({m['subject']})")
                        if os.path.exists(m['file_path']):
                            with open(m['file_path'], "rb") as f:
                                st.download_button("Download Material", f, file_name=f"{m['title']}.pdf", key=f"l_{m['title']}")
            else: st.info("No library items found for your semester.")

        with st_tabs[1]: # Active Assignments
            assigns = pd.read_sql_query("""
                SELECT a.id, a.title, a.deadline, a.question_file, s.name as subject FROM assignments a 
                JOIN subjects s ON a.subject_id = s.id WHERE s.semester_id = ?
            """, conn, params=(int(curr_sid),))
            
            if not assigns.empty:
                for _, a in assigns.iterrows():
                    with st.container(border=True):
                        st.subheader(f"📌 {a['title']}")
                        st.write(f"**Subject:** {a['subject']} | **Due:** {a['deadline']}")
                        
                        # Download Question
                        if a['question_file'] and os.path.exists(a['question_file']):
                            with open(a['question_file'], "rb") as f:
                                st.download_button("Download Question PDF", f, file_name=f"Q_{a['title']}.pdf", key=f"q_{a['id']}")
                        
                        # Upload Area
                        up = st.file_uploader("Upload Your Solution (PDF)", type="pdf", key=f"up_{a['id']}")
                        if st.button("Submit Assignment", key=f"btn_{a['id']}"):
                            if up:
                                path = f"submission_files/{st.session_state.user}_{up.name}"
                                with open(path, "wb") as f: f.write(up.getbuffer())
                                c.execute("INSERT INTO submissions (assignment_id, user_id, submission_time, submission_file) VALUES (?,?,?,?)",
                                          (int(a['id']), st.session_state.user_id, str(datetime.now()), path))
                                conn.commit(); st.success("✅ Submitted successfully!")
                            else: st.error("Please upload a file first.")
            else: st.info("No active assignments for your semester.")

# ================= SIDEBAR =================
st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False})
    st.rerun()

if st.session_state.role == "lecturer":
    if st.sidebar.button("Hard Reset"):
        c.execute("DROP TABLE IF EXISTS users")
        c.execute("DROP TABLE IF EXISTS submissions")
        c.execute("DROP TABLE IF EXISTS assignments")
        c.execute("DROP TABLE IF EXISTS study_materials")
        conn.commit(); st.rerun()
