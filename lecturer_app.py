import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import os
import io
import bcrypt
import plotly.express as px

# ================= CONFIG =================
st.set_page_config(page_title="Civil-AI Pro", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .card { background-color: white; padding: 20px; border-radius: 10px; border-left: 5px solid #004b87; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stHeader { background-color: #004b87; color: white; padding: 10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ================= DB & SELF-REPAIR =================
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
            else: st.error("Access Denied.")
    st.stop()

# ================= LECTURER DASHBOARD =================
if st.session_state.role == "lecturer":
    tabs = st.tabs(["📊 Analytics", "📚 Library", "📁 Assignments", "📝 Submissions", "👥 Students", "⚙️ Setup"])

    # SETUP (MUST BE DONE FIRST)
    with tabs[5]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Add Semester")
            sn = st.text_input("Semester Name (e.g., I/I, III/II)")
            if st.button("Save Semester"):
                c.execute("INSERT INTO semesters (name) VALUES (?)", (sn,))
                conn.commit(); st.rerun()
        with c2:
            st.subheader("Add Subject")
            all_sems = pd.read_sql_query("SELECT * FROM semesters", conn)
            if not all_sems.empty:
                target_sem = st.selectbox("Select Semester", all_sems["name"], key="setup_s")
                sub_name = st.text_input("Subject Name")
                if st.button("Save Subject"):
                    sid = all_sems[all_sems["name"]==target_sem]["id"].values[0]
                    c.execute("INSERT INTO subjects (name, semester_id) VALUES (?,?)", (sub_name, int(sid)))
                    conn.commit(); st.success(f"Subject '{sub_name}' added to {target_sem}"); st.rerun()

    # ASSIGNMENTS (WITH SEMESTER NAME INCLUDED)
    with tabs[2]:
        st.subheader("Publish New Assignment")
        # Multi-Join Query to show Semester Name next to Subject Name
        sub_query = """
            SELECT subjects.id, subjects.name || ' (' || semesters.name || ')' as full_label 
            FROM subjects JOIN semesters ON subjects.semester_id = semesters.id
        """
        full_subs = pd.read_sql_query(sub_query, conn)
        
        if not full_subs.empty:
            a_label = st.selectbox("Select Subject & Semester", full_subs["full_label"])
            a_title = st.text_input("Assignment Title")
            a_due = st.date_input("Deadline", min_value=date.today())
            a_file = st.file_uploader("Upload Question (PDF)", type="pdf")
            
            if st.button("Publish Assignment"):
                selected_id = full_subs[full_subs["full_label"] == a_label]["id"].values[0]
                path = f"submission_files/Q_{a_file.name}" if a_file else ""
                if a_file:
                    with open(path, "wb") as f: f.write(a_file.getbuffer())
                
                c.execute("INSERT INTO assignments (title, subject_id, deadline, question_file) VALUES (?,?,?,?)", 
                          (a_title, int(selected_id), str(a_due), path))
                conn.commit(); st.success(f"✅ '{a_title}' is now visible to students in {a_label}!")
        else:
            st.warning("No subjects available. Go to Setup first.")

    # STUDENT MANAGEMENT (MANUAL ENTRY)
    with tabs[4]:
        st.subheader("Manual Student Enrollment")
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)
        if not sems.empty:
            m_user = st.text_input("Student Roll No.")
            m_pass = st.text_input("Assign Password", type="password")
            m_sem = st.selectbox("Assign to Semester", sems["name"], key="stud_sem")
            if st.button("Create Student Account"):
                sid = sems[sems["name"]==m_sem]["id"].values[0]
                c.execute("INSERT INTO users (username, password, role, semester_id) VALUES (?,?,?,?)", 
                          (m_user, hash_pw(m_pass), "student", int(sid)))
                conn.commit(); st.success(f"User {m_user} registered for {m_sem}")

# ================= STUDENT DASHBOARD =================
elif st.session_state.role == "student":
    # 1. Verification of the link
    curr_sid = st.session_state.semester_id
    st.title(f"Student Portal: {st.session_state.user}")
    
    if curr_sid is None:
        st.error("⚠️ Configuration Error: You have not been assigned to a semester. Contact your Lecturer.")
    else:
        st_tabs = st.tabs(["📚 Study Materials", "📝 My Assignments", "📊 Results"])

        with st_tabs[0]: # Linked Library
            mats = pd.read_sql_query("""
                SELECT sm.title, sm.file_path, s.name as subject 
                FROM study_materials sm 
                JOIN subjects s ON sm.subject_id = s.id 
                WHERE s.semester_id = ?
            """, conn, params=(int(curr_sid),))
            if not mats.empty:
                for _, m in mats.iterrows():
                    with st.container(border=True):
                        st.write(f"📖 **{m['title']}** ({m['subject']})")
                        if os.path.exists(m['file_path']):
                            with open(m['file_path'], "rb") as f:
                                st.download_button("Download Notes", f, file_name=f"{m['title']}.pdf", key=f"l_{m['title']}")
            else: st.info("No materials published for your semester yet.")

        with st_tabs[1]: # Linked Assignments (VIEW, DOWNLOAD, UPLOAD)
            # This query finds assignments where the subject belongs to the student's semester
            assigns = pd.read_sql_query("""
                SELECT a.id, a.title, a.deadline, a.question_file, s.name as subject 
                FROM assignments a 
                JOIN subjects s ON a.subject_id = s.id 
                WHERE s.semester_id = ?
            """, conn, params=(int(curr_sid),))
            
            if not assigns.empty:
                for _, a in assigns.iterrows():
                    with st.container(border=True):
                        st.subheader(f"📌 {a['title']}")
                        st.write(f"**Subject:** {a['subject']} | **Deadline:** {a['deadline']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if a['question_file'] and os.path.exists(a['question_file']):
                                with open(a['question_file'], "rb") as f:
                                    st.download_button("📄 Download Question", f, file_name=f"Q_{a['title']}.pdf", key=f"q_{a['id']}")
                        
                        with col2:
                            # Check if already submitted
                            check = pd.read_sql_query("SELECT id FROM submissions WHERE assignment_id=? AND user_id=?", 
                                                       conn, params=(int(a['id']), st.session_state.user_id))
                            if not check.empty:
                                st.success("✅ Submission Received")
                            else:
                                up = st.file_uploader("Upload Solution (PDF)", type="pdf", key=f"up_{a['id']}")
                                if st.button("Submit My Work", key=f"btn_{a['id']}"):
                                    if up:
                                        path = f"submission_files/{st.session_state.user}_{up.name}"
                                        with open(path, "wb") as f: f.write(up.getbuffer())
                                        c.execute("INSERT INTO submissions (assignment_id, user_id, submission_time, submission_file) VALUES (?,?,?,?)",
                                                  (int(a['id']), st.session_state.user_id, str(datetime.now()), path))
                                        conn.commit(); st.success("Submitted successfully!"); st.rerun()
            else:
                st.info("No active assignments found for your semester.")

# ================= SYSTEM =================
st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False})
    st.rerun()

if st.session_state.role == "lecturer":
    if st.sidebar.button("🧨 Hard Reset (Wipe All Data)"):
        c.execute("DROP TABLE IF EXISTS users"); c.execute("DROP TABLE IF EXISTS submissions")
        c.execute("DROP TABLE IF EXISTS assignments"); c.execute("DROP TABLE IF EXISTS study_materials")
        conn.commit(); st.rerun()
