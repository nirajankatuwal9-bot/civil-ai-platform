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

# Professional UI Styling
st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { background-color: #ffffff; border-radius: 5px 5px 0 0; padding: 10px 20px; border: 1px solid #ddd; }
    .stTabs [aria-selected="true"] { background-color: #004b87 !important; color: white !important; }
    .card { background-color: white; padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; margin-bottom: 15px; }
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

# ================= AUTH UTILS =================
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

# ================= LOGIN SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": None, "user": None, "user_id": None})

if not st.session_state.logged_in:
    st.title("🏗️ Civil-AI Institutional Portal")
    with st.container(border=True):
        u = st.text_input("Username (Admin/Roll No)")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            res = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(u,))
            if not res.empty and check_pw(p, res.iloc[0]["password"]):
                st.session_state.update({"logged_in": True, "role": res.iloc[0]["role"], "user": res.iloc[0]["username"], "user_id": res.iloc[0]["id"]})
                st.rerun()
            else: st.error("Invalid Login Credentials")
    st.stop()

# ================= LECTURER DASHBOARD =================
if st.session_state.role == "lecturer":
    tabs = st.tabs(["📊 Analytics", "📚 Materials", "📁 Assignments", "📝 Submissions", "👥 Manage Students", "⚙️ Setup", "🔎 Plagiarism"])

    # 1. ANALYTICS
    with tabs[0]:
        st.subheader("Performance Insights")
        df_an = pd.read_sql_query("""
            SELECT s.marks, sub.name as subject FROM submissions s 
            JOIN assignments a ON s.assignment_id = a.id 
            JOIN subjects sub ON a.subject_id = sub.id""", conn)
        if not df_an.empty:
            df_an["marks"] = pd.to_numeric(df_an["marks"], errors='coerce').fillna(0)
            fig = px.bar(df_an.groupby("subject")["marks"].mean().reset_index(), 
                         x="subject", y="marks", color="marks", template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("No data available for analytics yet.")

    # 2. STUDY MATERIALS (NEWLY RE-ADDED)
    with tabs[1]:
        st.subheader("Upload Reference Materials")
        all_subs = pd.read_sql_query("SELECT * FROM subjects", conn)
        if not all_subs.empty:
            m_title = st.text_input("Title (e.g., Fluid Mechanics Notes)")
            m_sub_name = st.selectbox("Assign to Subject", all_subs["name"], key="m_sub")
            m_file = st.file_uploader("Upload PDF File", type="pdf", key="m_file")
            if st.button("Publish Material"):
                if m_title and m_file:
                    m_sid = all_subs[all_subs["name"] == m_sub_name]["id"].values[0]
                    m_path = f"study_materials/{m_file.name}"
                    with open(m_path, "wb") as f: f.write(m_file.getbuffer())
                    c.execute("INSERT INTO study_materials (title, subject_id, file_path, upload_date) VALUES (?,?,?,?)",
                              (m_title, int(m_sid), m_path, str(date.today())))
                    conn.commit()
                    st.success(f"✅ '{m_title}' published successfully!")
                else: st.error("Please provide a title and a file.")
        else: st.warning("Please create subjects in the 'Setup' tab first.")

    # 3. ASSIGNMENTS
    with tabs[2]:
        st.subheader("Create New Assignment")
        all_subs = pd.read_sql_query("SELECT * FROM subjects", conn)
        if not all_subs.empty:
            a_sub_name = st.selectbox("Subject", all_subs["name"], key="a_sub")
            a_title = st.text_input("Assignment Title")
            a_deadline = st.date_input("Submission Deadline", min_value=date.today())
            a_file = st.file_uploader("Question PDF", type="pdf", key="a_file")
            if st.button("Create Assignment"):
                if a_title:
                    a_sid = all_subs[all_subs["name"] == a_sub_name]["id"].values[0]
                    a_path = f"submission_files/Q_{a_file.name}" if a_file else ""
                    if a_file:
                        with open(a_path, "wb") as f: f.write(a_file.getbuffer())
                    c.execute("INSERT INTO assignments (title, subject_id, deadline, question_file) VALUES (?,?,?,?)",
                              (a_title, int(a_sid), str(a_deadline), a_path))
                    conn.commit()
                    st.success(f"✅ Assignment '{a_title}' saved successfully!")
                else: st.error("Please enter a title.")

    # 4. SUBMISSIONS
    with tabs[3]:
        st.subheader("Review Submissions")
        df_s = pd.read_sql_query("""
            SELECT s.id, u.username as roll, a.title, s.submission_time, s.submission_file, s.marks 
            FROM submissions s JOIN users u ON s.user_id = u.id JOIN assignments a ON s.assignment_id = a.id
        """, conn)
        if not df_s.empty:
            st.dataframe(df_s, use_container_width=True)
            # Add Grading logic here
        else: st.info("No submissions found.")

    # 5. MANAGE STUDENTS (MANUAL + CSV)
    with tabs[4]:
        st.subheader("Student Data Management")
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.write("**Manual Student Entry**")
            m_user = st.text_input("Roll Number")
            m_pass = st.text_input("Password", type="password", key="m_pass")
            m_sem = st.selectbox("Assign Semester", sems["name"], key="m_sem")
            if st.button("Add Student"):
                try:
                    sem_id = sems[sems["name"] == m_sem]["id"].values[0]
                    c.execute("INSERT INTO users (username, password, role, semester_id) VALUES (?,?,?,?)",
                              (m_user, hash_pw(m_pass), "student", int(sem_id)))
                    conn.commit(); st.success(f"Added {m_user}!")
                except: st.error("Username already exists.")

        with col_m2:
            st.write("**Bulk CSV Upload**")
            csv_f = st.file_uploader("Upload CSV", type="csv")
            if csv_f and st.button("Bulk Register"):
                df_u = pd.read_csv(csv_f)
                for _, r in df_u.iterrows():
                    try:
                        sid = sems[sems["name"]==str(r['semester']).strip()]["id"].values[0]
                        c.execute("INSERT INTO users (username, password, role, semester_id) VALUES (?,?,?,?)",
                                  (str(r['username']), hash_pw(str(r['password'])), "student", int(sid)))
                    except: pass
                conn.commit(); st.success("Bulk registration complete.")

    # 6. SETUP
    with tabs[5]:
        col_setup1, col_setup2 = st.columns(2)
        with col_setup1:
            st.subheader("Add Semester")
            s_name = st.text_input("Semester (e.g., I/I)")
            if st.button("Save Semester"):
                c.execute("INSERT INTO semesters (name) VALUES (?)", (s_name,))
                conn.commit(); st.success("Semester Created."); st.rerun()
        with col_setup2:
            st.subheader("Add Subject")
            sems_list = pd.read_sql_query("SELECT * FROM semesters", conn)
            if not sems_list.empty:
                target_sem = st.selectbox("Select Semester", sems_list["name"])
                sub_name = st.text_input("Subject Name")
                if st.button("Save Subject"):
                    t_id = sems_list[sems_list["name"] == target_sem]["id"].values[0]
                    c.execute("INSERT INTO subjects (name, semester_id) VALUES (?,?)", (sub_name, int(t_id)))
                    conn.commit(); st.success("Subject Created."); st.rerun()

# ================= STUDENT DASHBOARD =================
elif st.session_state.role == "student":
    tabs_stu = st.tabs(["📚 Library", "📝 My Assignments", "📊 Results"])
    
    with tabs_stu[0]:
        st.subheader("Study Materials")
        # Logic to display materials based on current student's semester_id

    with tabs_stu[1]:
        st.subheader("Active Submissions")
        # Logic to display pending assignments

# ================= LOGOUT & RESET =================
st.sidebar.divider()
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False})
    st.rerun()

if st.session_state.role == "lecturer":
    if st.sidebar.button("🧨 Hard Reset (Wipe All)"):
        c.execute("DROP TABLE IF EXISTS users")
        c.execute("DROP TABLE IF EXISTS submissions")
        c.execute("DROP TABLE IF EXISTS study_materials")
        conn.commit(); st.rerun()
