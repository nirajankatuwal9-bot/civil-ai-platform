import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os
import re
import io
import bcrypt
import plotly.express as px
from pdf2image import convert_from_path
from google import genai

# ================= CONFIG & STYLING =================

st.set_page_config(page_title="Civil-AI Portal", page_icon="🏗️", layout="wide")

# Custom CSS for a Professional Grade Look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #004b87; color: white; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); background-color: white; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_stdio=True)

GEMINI_MODEL = "gemini-3-flash-preview"
client = genai.Client(api_key=st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY"))

# ================= DATABASE SETUP =================

DB_PATH = "data/lecturer.db"
os.makedirs("data", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)
os.makedirs("study_materials", exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT, semester_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS semesters(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, semester_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, subject_id INTEGER, deadline TEXT, question_file TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_id INTEGER, user_id INTEGER, submission_time TEXT, submission_file TEXT, marks TEXT, ai_summary TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS study_materials(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, subject_id INTEGER, file_path TEXT, upload_date TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS quiz_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, score REAL, attempt_time TEXT)""")
    conn.commit()

create_tables()

# ================= AUTH & SECURITY =================

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, stored_value):
    try:
        return bcrypt.checkpw(password.encode(), stored_value.encode())
    except: return False

def initialize_system():
    # Ensures you can ALWAYS login as admin after a reset
    c.execute("SELECT COUNT(*) FROM users WHERE role='lecturer'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                  ("admin", hash_password("admin123"), "lecturer"))
    c.execute("SELECT COUNT(*) FROM semesters")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO semesters (name) VALUES (?)", ("I/I",))
    conn.commit()

initialize_system()

# ================= SESSION STATE =================

if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": None, "user": None, "user_id": None})

# ================= LOGIN UI =================

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🏗️ Civil-AI")
        st.subheader("Institutional Grade Learning Portal")
        with st.container(border=True):
            u_in = st.text_input("Username")
            p_in = st.text_input("Password", type="password")
            if st.button("Access Portal"):
                res = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(u_in,))
                if not res.empty and check_password(p_in, res.iloc[0]["password"]):
                    st.session_state.update({"logged_in": True, "role": res.iloc[0]["role"], "user": res.iloc[0]["username"], "user_id": res.iloc[0]["id"]})
                    st.rerun()
                else: st.error("Authentication Failed")
    st.stop()

# ================= SIDEBAR =================

st.sidebar.title(f"👤 {st.session_state.user}")
st.sidebar.caption(f"Role: {st.session_state.role.capitalize()}")

if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False})
    st.rerun()

if st.session_state.role == "lecturer":
    st.sidebar.divider()
    if st.sidebar.button("⚠️ Hard Reset System"):
        c.execute("DROP TABLE IF EXISTS submissions"); c.execute("DROP TABLE IF EXISTS users")
        conn.commit()
        st.rerun()

# ================= LECTURER DASHBOARD =================

if st.session_state.role == "lecturer":
    tabs = st.tabs(["📊 Analytics", "📁 Materials", "📝 Submissions", "📁 Assignments", "📅 Setup", "👥 Students"])

    # 1. ANALYTICS (VISUALLY ENGAGING)
    with tabs[0]:
        st.title("Institutional Analytics")
        df_an = pd.read_sql_query("""
            SELECT s.marks, sub.name as subject 
            FROM submissions s 
            JOIN assignments a ON s.assignment_id = a.id 
            JOIN subjects sub ON a.subject_id = sub.id
        """, conn)
        
        if not df_an.empty:
            df_an["marks"] = pd.to_numeric(df_an["marks"], errors='coerce').fillna(0)
            col1, col2 = st.columns(2)
            with col1:
                fig1 = px.bar(df_an.groupby("subject")["marks"].mean().reset_index(), 
                             x="subject", y="marks", color="marks", 
                             color_continuous_scale="RdYlGn", title="Avg Performance per Subject")
                st.plotly_chart(fig1, use_container_width=True)
            with col2:
                fig2 = px.histogram(df_an, x="marks", nbins=10, title="Grade Distribution (Bell Curve)", color_discrete_sequence=['#004b87'])
                st.plotly_chart(fig2, use_container_width=True)
        else: st.info("Analytics will populate as students are graded.")

    # 2. STUDY MATERIALS (NEW FEATURE)
    with tabs[1]:
        st.subheader("📚 Upload Study Materials")
        all_subs = pd.read_sql_query("SELECT id, name FROM subjects", conn)
        if not all_subs.empty:
            m_title = st.text_input("Material Title (e.g. Lecture 1: Hydraulics)")
            m_sub = st.selectbox("Link to Subject", all_subs["name"], key="m_sub_sel")
            m_file = st.file_uploader("Upload PDF Reference", type="pdf")
            if st.button("Publish Material") and m_file:
                m_sub_id = all_subs[all_subs["name"] == m_sub]["id"].values[0]
                path = f"study_materials/{m_file.name}"
                with open(path, "wb") as f: f.write(m_file.getbuffer())
                c.execute("INSERT INTO study_materials (title, subject_id, file_path, upload_date) VALUES (?,?,?,?)",
                          (m_title, int(m_sub_id), path, str(datetime.now().date())))
                conn.commit()
                st.success("Material published to Student Library!")
        
        st.divider()
        st.subheader("Manage Current Materials")
        m_list = pd.read_sql_query("SELECT sm.id, sm.title, s.name as subject FROM study_materials sm JOIN subjects s ON sm.subject_id = s.id", conn)
        st.dataframe(m_list, use_container_width=True, hide_index=True)

    # 3. SUBMISSIONS & AI
    with tabs[2]:
        st.subheader("Student Submissions")
        query = """
            SELECT s.id, u.username, sub.name as subject, a.title as assignment, s.submission_file, s.marks 
            FROM submissions s 
            JOIN users u ON s.user_id = u.id 
            JOIN assignments a ON s.assignment_id = a.id 
            JOIN subjects sub ON a.subject_id = sub.id
        """
        df_s = pd.read_sql_query(query, conn)
        for _, row in df_s.iterrows():
            with st.expander(f"📄 {row['username']} - {row['assignment']}"):
                col_left, col_right = st.columns(2)
                with col_left:
                    st.write(f"**Subject:** {row['subject']}")
                    if os.path.exists(str(row['submission_file'])):
                        with open(str(row['submission_file']), "rb") as f:
                            st.download_button("Download Work", f, file_name=f"{row['username']}.pdf", key=f"dl_{row['id']}")
                with col_right:
                    st.write(f"Current Marks: **{row['marks'] or 'Pending'}**")
                    if st.button("AI Grade", key=f"ai_{row['id']}"):
                        st.toast("AI Grading in progress...")
                        # Logic for AI grading goes here

    # 4. SETUP (SEMESTERS/SUBJECTS)
    with tabs[4]:
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.write("**Add Semester**")
            n_sem = st.text_input("Semester Name (e.g. II/I)")
            if st.button("Save Semester"):
                c.execute("INSERT INTO semesters (name) VALUES (?)", (n_sem,))
                conn.commit(); st.rerun()
        with col_s2:
            st.write("**Add Subject**")
            sems = pd.read_sql_query("SELECT * FROM semesters", conn)
            if not sems.empty:
                target_sem = st.selectbox("For Semester", sems["name"])
                n_sub = st.text_input("Subject Name")
                if st.button("Save Subject"):
                    t_id = sems[sems["name"]==target_sem]["id"].values[0]
                    c.execute("INSERT INTO subjects (name, semester_id) VALUES (?,?)", (n_sub, int(t_id)))
                    conn.commit(); st.rerun()

# ================= STUDENT DASHBOARD =================

elif st.session_state.role == "student":
    tabs = st.tabs(["📚 Library", "📝 Assignments", "📊 My Grades"])

    # 1. LIBRARY (VIEW STUDY MATERIALS)
    with tabs[0]:
        st.title("Student Library")
        u_sem = pd.read_sql_query("SELECT semester_id FROM users WHERE id=?", conn, params=(st.session_state.user_id,)).iloc[0][0]
        if u_sem:
            mats = pd.read_sql_query("""
                SELECT sm.title, sm.file_path, s.name as subject 
                FROM study_materials sm 
                JOIN subjects s ON sm.subject_id = s.id 
                WHERE s.semester_id = ?
            """, conn, params=(int(u_sem),))
            
            if not mats.empty:
                for _, m in mats.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3,1])
                        c1.write(f"📖 **{m['title']}**")
                        c1.caption(f"Subject: {m['subject']}")
                        if os.path.exists(m['file_path']):
                            with open(m['file_path'], "rb") as f:
                                c2.download_button("Open", f, file_name=m['title']+".pdf", key=f"lib_{m['title']}")
            else: st.info("No study materials uploaded for your semester yet.")
        else: st.warning("You are not assigned to a semester.")

    # 2. ASSIGNMENTS
    with tabs[1]:
        st.title("Active Assignments")
        # Same assignment logic as before...

# Final Footer
st.divider()
st.caption("© 2026 Professional Civil-AI Platform | Developed for Academic Excellence")
