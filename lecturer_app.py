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
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #f0f2f6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

GEMINI_MODEL = "gemini-3-flash-preview"
client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"))

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
    
    # Auto-repair: Ensure columns exist
    cols = [col[1] for col in c.execute("PRAGMA table_info(submissions)").fetchall()]
    if "ai_feedback" not in cols:
        c.execute("ALTER TABLE submissions ADD COLUMN ai_feedback TEXT")
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
                # CRITICAL FIX: Storing semester_id in session
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

    # ANALYTICS
    with tabs[0]:
        st.subheader("Performance Overview")
        df_an = pd.read_sql_query("SELECT s.marks, sub.name as subject FROM submissions s JOIN assignments a ON s.assignment_id = a.id JOIN subjects sub ON a.subject_id = sub.id", conn)
        if not df_an.empty:
            df_an["marks"] = pd.to_numeric(df_an["marks"], errors='coerce').fillna(0)
            st.plotly_chart(px.bar(df_an.groupby("subject")["marks"].mean().reset_index(), x="subject", y="marks", color="marks"), use_container_width=True)

    # LIBRARY (UPLOAD)
    with tabs[1]:
        st.subheader("Publish Study Material")
        subs = pd.read_sql_query("SELECT * FROM subjects", conn)
        if not subs.empty:
            m_title = st.text_input("Material Title")
            m_sub = st.selectbox("Subject", subs["name"], key="lib_sub")
            m_file = st.file_uploader("Upload PDF", type="pdf", key="lib_file")
            if st.button("Publish Material") and m_file:
                sid = subs[subs["name"]==m_sub]["id"].values[0]
                path = f"study_materials/{m_file.name}"
                with open(path, "wb") as f: f.write(m_file.getbuffer())
                c.execute("INSERT INTO study_materials (title, subject_id, file_path, upload_date) VALUES (?,?,?,?)", (m_title, int(sid), path, str(date.today())))
                conn.commit(); st.success("Published!")

    # ASSIGNMENTS (CREATE)
    with tabs[2]:
        st.subheader("Create New Assignment")
        if not subs.empty:
            a_title = st.text_input("Title")
            a_sub = st.selectbox("Subject", subs["name"], key="ass_sub")
            a_due = st.date_input("Deadline", min_value=date.today())
            a_file = st.file_uploader("Question PDF", type="pdf", key="ass_file")
            if st.button("Create Assignment"):
                sid = subs[subs["name"]==a_sub]["id"].values[0]
                path = f"submission_files/Q_{a_file.name}" if a_file else ""
                if a_file:
                    with open(path, "wb") as f: f.write(a_file.getbuffer())
                c.execute("INSERT INTO assignments (title, subject_id, deadline, question_file) VALUES (?,?,?,?)", (a_title, int(sid), str(a_due), path))
                conn.commit(); st.success("Created!")

    # SUBMISSIONS (REPORT)
    with tabs[3]:
        st.subheader("Submissions & Grading")
        df_s = pd.read_sql_query("SELECT s.id, u.username as roll, a.title, s.submission_time, s.submission_file, s.marks, s.ai_feedback FROM submissions s JOIN users u ON s.user_id = u.id JOIN assignments a ON s.assignment_id = a.id", conn)
        if not df_s.empty:
            for _, r in df_s.iterrows():
                with st.expander(f"📄 {r['roll']} - {r['title']}"):
                    st.write(f"Grade: {r['marks'] or 'Pending'} | Feedback: {r['ai_feedback'] or 'None'}")
                    if os.path.exists(str(r['submission_file'])):
                        with open(str(r['submission_file']), "rb") as f: st.download_button("View Work", f, file_name=f"{r['roll']}.pdf", key=f"v_{r['id']}")

    # STUDENTS (MANAGEMENT)
    with tabs[4]:
        st.subheader("Manage Students")
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.write("**Manual Entry**")
            m_user = st.text_input("Roll No")
            m_pass = st.text_input("Password", type="password")
            m_sem = st.selectbox("Assign Semester", sems["name"], key="m_sem")
            if st.button("Add Student"):
                try:
                    sid = sems[sems["name"]==m_sem]["id"].values[0]
                    c.execute("INSERT INTO users (username, password, role, semester_id) VALUES (?,?,?,?)", (m_user, hash_pw(m_pass), "student", int(sid)))
                    conn.commit(); st.success(f"Added {m_user}!")
                except: st.error("Duplicate Roll Number")
        with col_m2:
            st.write("**Bulk CSV Upload**")
            csv_f = st.file_uploader("Upload CSV", type="csv")
            if csv_f and st.button("Bulk Register"):
                df_u = pd.read_csv(csv_f)
                for _, r in df_u.iterrows():
                    try:
                        sid = sems[sems["name"]==str(r['semester']).strip()]["id"].values[0]
                        c.execute("INSERT INTO users (username, password, role, semester_id) VALUES (?,?,?,?)", (str(r['username']), hash_pw(str(r['password'])), "student", int(sid)))
                    except: pass
                conn.commit(); st.success("Bulk Upload Complete!")

    # SETUP
    with tabs[5]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Add Semester")
            sn = st.text_input("Semester Name")
            if st.button("Save Sem"):
                c.execute("INSERT INTO semesters (name) VALUES (?)", (sn,))
                conn.commit(); st.rerun()
        with col2:
            st.subheader("Add Subject")
            if not sems.empty:
                s_sem = st.selectbox("Target Semester", sems["name"], key="setup_sem")
                s_name = st.text_input("Subject Name")
                if st.button("Save Sub"):
                    sid = sems[sems["name"]==s_sem]["id"].values[0]
                    c.execute("INSERT INTO subjects (name, semester_id) VALUES (?,?)", (s_name, int(sid)))
                    conn.commit(); st.rerun()

# ================= STUDENT DASHBOARD =================
elif st.session_state.role == "student":
    # 1. FETCH CURRENT SEMESTER DATA
    curr_sid = st.session_state.semester_id
    st.title(f"Student Portal: {st.session_state.user}")
    
    if not curr_sid:
        st.warning("⚠️ Access Limited: You have not been assigned to a semester. Contact the lecturer.")
    else:
        st_tabs = st.tabs(["📚 Library", "📝 Submit Assignment", "📊 My Results"])

        with st_tabs[0]: # Linked Library
            mats = pd.read_sql_query("""
                SELECT sm.title, sm.file_path, s.name as subject FROM study_materials sm 
                JOIN subjects s ON sm.subject_id = s.id WHERE s.semester_id = ?
            """, conn, params=(int(curr_sid),))
            if not mats.empty:
                for _, m in mats.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3,1])
                        c1.write(f"📖 **{m['title']}**")
                        c1.caption(f"Subject: {m['subject']}")
                        if os.path.exists(m['file_path']):
                            with open(m['file_path'], "rb") as f:
                                c2.download_button("Download PDF", f, file_name=f"{m['title']}.pdf", key=f"l_{m['title']}")
            else: st.info("No library items found for your semester.")

        with st_tabs[1]: # Linked Assignments (DOWNLOAD & UPLOAD)
            assigns = pd.read_sql_query("""
                SELECT a.id, a.title, a.deadline, a.question_file, s.name as subject FROM assignments a 
                JOIN subjects s ON a.subject_id = s.id WHERE s.semester_id = ?
            """, conn, params=(int(curr_sid),))
            
            if not assigns.empty:
                for _, a in assigns.iterrows():
                    with st.container(border=True):
                        st.subheader(f"📌 {a['title']}")
                        st.write(f"**Subject:** {a['subject']} | **Due:** {a['deadline']}")
                        
                        col_q, col_u = st.columns(2)
                        with col_q:
                            if a['question_file'] and os.path.exists(a['question_file']):
                                with open(a['question_file'], "rb") as f:
                                    st.download_button("📄 Download Question PDF", f, file_name=f"Q_{a['title']}.pdf", key=f"q_{a['id']}")
                            else: st.info("No question file attached.")
                        
                        with col_u:
                            up = st.file_uploader("Upload Solution (PDF)", type="pdf", key=f"up_{a['id']}")
                            if st.button("Submit Work", key=f"btn_{a['id']}") and up:
                                path = f"submission_files/{st.session_state.user}_{up.name}"
                                with open(path, "wb") as f: f.write(up.getbuffer())
                                c.execute("INSERT INTO submissions (assignment_id, user_id, submission_time, submission_file) VALUES (?,?,?,?)", 
                                          (int(a['id']), st.session_state.user_id, str(datetime.now()), path))
                                conn.commit(); st.success("✅ Submitted Successfully!")
            else: st.info("No active assignments for your semester.")

        with st_tabs[2]: # Results
            res = pd.read_sql_query("""
                SELECT a.title, s.marks, s.ai_feedback FROM submissions s 
                JOIN assignments a ON s.assignment_id = a.id WHERE s.user_id = ?
            """, conn, params=(int(st.session_state.user_id),))
            if not res.empty: st.dataframe(res, use_container_width=True, hide_index=True)
            else: st.info("You haven't submitted anything yet.")

# ================= SIDEBAR =================
st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False})
    st.rerun()

if st.session_state.role == "lecturer":
    if st.sidebar.button("Hard Reset"):
        c.execute("DROP TABLE IF EXISTS users"); c.execute("DROP TABLE IF EXISTS submissions")
        conn.commit(); st.rerun()
