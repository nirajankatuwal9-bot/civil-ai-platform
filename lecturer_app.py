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
from PIL import Image
import google.generativeai as genai
import fitz

# ================= CONFIG =================

st.set_page_config(
    page_title="The N-streamlines",
    page_icon="🌊",
    layout="wide"
)

# ================= GLOBAL FOOTER =================

st.markdown("""
    <style>
    footer {visibility: hidden;}
    .nira-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #ffffff;
        border-top: 1px solid #e1e4e8;
        color: #555;
        text-align: center;
        padding: 12px 0;
        font-size: 0.85em;
        z-index: 999;
    }
    .block-container {
        padding-bottom: 70px !important; 
    }
    </style>
    <div class="nira-footer">
        <strong>🌊 The N-Streamlines</strong> | Advanced Hydro-Informatics Platform | © 2026 Developed by Er. Nirajan Katuwal
    </div>
""", unsafe_allow_html=True)

# ================= FOLDERS =================

os.makedirs("data", exist_ok=True)
os.makedirs("assignment_files", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)
os.makedirs("study_materials", exist_ok=True)

# ================= DATABASE =================

DB_PATH = "data/lecturer.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

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

c.execute("""
CREATE TABLE IF NOT EXISTS semesters(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS subjects(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    semester_id INTEGER
)
""")

# ADDED RUBRIC COLUMN
c.execute("""
CREATE TABLE IF NOT EXISTS assignments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    subject_id INTEGER,
    deadline TEXT,
    question_file TEXT,
    rubric TEXT
)
""")

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

c.execute("""
CREATE TABLE IF NOT EXISTS study_materials(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    subject_id INTEGER,
    semester_id INTEGER,
    file_path TEXT,
    description TEXT,
    upload_date TEXT,
    uploaded_by INTEGER
)
""")

conn.commit()

# ================= HELPERS =================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, hashed):
    try:
        return bcrypt.checkpw(p.encode(), hashed.encode())
    except:
        return False

# ================= AI FUNCTIONS (UPGRADED) =================

def vision_grade(pdf_path, rubric):
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        images = convert_from_path(pdf_path)
        model = genai.GenerativeModel('gemini-3-flash-preview')

        prompt = f"""
You are a strict Civil Engineering Professor. Grade this student's handwritten work based ONLY on the provided model answer.

### ASSIGNMENT RUBRIC / MODEL ANSWER:
{rubric}

### RESPONSE FORMAT (STRICT):
FINAL_MARKS: X/10
SCORECARD:
- Concepts: X/4
- Math: X/4
- Units: X/2

DETECTED_EQUATIONS:
[List extracted LaTeX equations here]

FEEDBACK:
- [Point 1]
- [Point 2]
Now grade the images below:"""

        content_parts = [prompt]
        for img in images[:5]:
            content_parts.append(img)
            
        response = model.generate_content(content_parts)
        return response.text if hasattr(response, 'text') else "Error"
    except Exception as e:
        return f"Error: {e}"

def extract_marks(text):
    if not text: return None
    m = re.search(r"FINAL_MARKS:\s*(\d+)/10", str(text), re.IGNORECASE)
    return int(m.group(1)) if m else None

def apply_watermark(file_path, watermark_text="🌊 The N-Streamlines | Er. Nirajan Katuwal"):
    try:
        doc = fitz.open(file_path)
        for page in doc:
            page.insert_text((30, page.rect.height - 30), watermark_text, fontsize=12, color=(0.6, 0.6, 0.6), fill_opacity=0.5, overlay=True)
        temp_path = file_path + "_wm.pdf"
        doc.save(temp_path)
        doc.close()
        os.replace(temp_path, file_path)
    except: pass

def get_deadline_status(deadline_str):
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        today = datetime.now()
        days = (deadline - today).days
        if days < 0: return days, "Overdue", "🔴"
        elif days == 0: return days, "Due Today", "🟠"
        else: return days, "Upcoming", "🔵"
    except: return None, "Unknown", "⚪"

def format_deadline_display(deadline_str):
    days, status, color = get_deadline_status(deadline_str)
    return f"{color} {deadline_str} ({status})"

# ================= LOGIN =================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🌊 THE N-STREAMLINES")
    with st.container(border=True):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        if st.button("Enter the Flow"):
            res = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(user,))
            if not res.empty and check_password(pw, res.iloc[0]["password"]):
                st.session_state.logged_in = True
                st.session_state.user_id = res.iloc[0]["id"]
                st.session_state.role = res.iloc[0]["role"]
                st.session_state.username = res.iloc[0]["username"]
                st.session_state.semester_id = res.iloc[0]["semester_id"]
                st.rerun()
            else: st.error("Invalid credentials")
    st.stop()

# ================= LECTURER PORTAL =================

if st.session_state.role == "lecturer":
    tabs = st.tabs(["Dashboard", "Semesters", "Subjects", "Assignments", "Submissions & AI", "Analytics", "Manage Students", "Study Materials", "Student Profiles"])
    
    with tabs[0]:
        st.title("📊 Dashboard")
        df_dash = pd.read_sql_query("SELECT assignments.id, assignments.title, assignments.deadline, subjects.name as subject FROM assignments JOIN subjects ON assignments.subject_id = subjects.id", conn)
        if not df_dash.empty:
            for _, row in df_dash.iterrows():
                st.write(f"📌 {row['subject']} - {row['title']} | {format_deadline_display(row['deadline'])}")

    with tabs[1]:
        name_s = st.text_input("New Semester")
        if st.button("Add Semester") and name_s.strip():
            c.execute("INSERT INTO semesters(name) VALUES(?)", (name_s.strip(),)); conn.commit(); st.rerun()
        st.dataframe(pd.read_sql_query("SELECT * FROM semesters", conn), use_container_width=True, hide_index=True)

    with tabs[2]:
        st.title("📚 Subject Management")
        sems = pd.read_sql_query("SELECT * FROM semesters", conn)
        if not sems.empty:
            s_name = st.selectbox("Select Semester", sems["name"])
            sid = int(sems[sems["name"] == s_name]["id"].values[0])
            sub_in = st.text_input("Subject Name")
            if st.button("Add Subject") and sub_in.strip():
                c.execute("INSERT INTO subjects(name, semester_id) VALUES(?,?)", (sub_in.strip(), sid)); conn.commit(); st.rerun()

    with tabs[3]:
        st.title("📝 Assignment Management")
        st.subheader("➕ Create New Assignment")
        sems_a = pd.read_sql_query("SELECT * FROM semesters", conn)
        if not sems_a.empty:
            sn = st.selectbox("Semester", sems_a["name"], key="as_sem")
            sid_a = int(sems_a[sems_a["name"] == sn]["id"].values[0])
            subs = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=?", conn, params=(sid_a,))
            if not subs.empty:
                sub_sel = st.selectbox("Subject", subs["name"])
                sub_id = int(subs[subs["name"] == sub_sel]["id"].values[0])
                title = st.text_input("Title")
                deadline = st.date_input("Deadline")
                rubric_text = st.text_area("🎯 Marking Rubric / Model Answer")
                file = st.file_uploader("Upload Question PDF", type=["pdf"])
                if st.button("Create Assignment"):
                    fp = ""
                    if file:
                        fp = f"assignment_files/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
                        with open(fp, "wb") as f: f.write(file.getbuffer())
                    c.execute("INSERT INTO assignments(title, subject_id, deadline, question_file, rubric) VALUES(?,?,?,?,?)", (title, sub_id, str(deadline), fp, rubric_text))
                    conn.commit(); st.success("Created"); st.rerun()

    with tabs[4]:
        st.subheader("Student Submissions & AI Grading")
        df_sub = pd.read_sql_query("""SELECT submissions.*, users.full_name, assignments.title, assignments.rubric FROM submissions 
                                   JOIN users ON submissions.student_id = users.id 
                                   JOIN assignments ON submissions.assignment_id = assignments.id""", conn)
        if not df_sub.empty:
            for _, row in df_sub.iterrows():
                with st.expander(f"{row['full_name']} - {row['title']}"):
                    if st.button("AI Grade", key=f"ai_{row['id']}"):
                        res = vision_grade(row['submission_file'], row['rubric'])
                        st.write(res)
                        marks = extract_marks(res)
                        if marks is not None:
                            c.execute("UPDATE submissions SET marks=?, ai_summary=? WHERE id=?", (marks, res, row['id'])); conn.commit(); st.rerun()

    with tabs[6]:
        st.subheader("Manage Students")
        sn = st.text_input("Full Name")
        un = st.text_input("Username")
        ps = st.text_input("Password", type="password")
        sems_st = pd.read_sql_query("SELECT * FROM semesters", conn)
        if not sems_st.empty:
            sem_st = st.selectbox("Semester", sems_st["name"])
            sid_st = int(sems_st[sems_st["name"] == sem_st]["id"].values[0])
            if st.button("Create Student"):
                c.execute("INSERT INTO users(full_name, username, password, role, semester_id) VALUES(?,?,?,?,?)", (sn, un, hash_password(ps), "student", sid_st))
                conn.commit(); st.success("Created"); st.rerun()

    with tabs[8]: # STUDENT PROFILES (RESTORED)
        st.title("👤 Student Profiles")
        st_list = pd.read_sql_query("SELECT id, full_name, username FROM users WHERE role='student'", conn)
        if not st_list.empty:
            sel_st = st.selectbox("Select Student", st_list['full_name'])
            st_id = int(st_list[st_list['full_name'] == sel_st]['id'].values[0])
            st_subs = pd.read_sql_query("SELECT assignments.title, submissions.marks, submissions.submission_time FROM submissions JOIN assignments ON submissions.assignment_id = assignments.id WHERE student_id=?", conn, params=(st_id,))
            st.dataframe(st_subs, use_container_width=True, hide_index=True)

# ================= STUDENT PORTAL =================

elif role == "student":
    tabs_st = st.tabs(["Assignments", "Study Materials", "My Results"])
    
    with tabs_st[0]:
        st.title("📝 My Assignments")
        sid_s = st.session_state.semester_id
        as_s = pd.read_sql_query("SELECT assignments.*, subjects.name as subject FROM assignments JOIN subjects ON assignments.subject_id = subjects.id WHERE subjects.semester_id=?", conn, params=(sid_s,))
        if not as_s.empty:
            for _, row in as_s.iterrows():
                with st.expander(f"{row['subject']} - {row['title']} | {format_deadline_display(row['deadline'])}"):
                    up = st.file_uploader("Submit PDF", type=["pdf"], key=f"up_{row['id']}")
                    if st.button("Submit", key=f"btn_{row['id']}"):
                        if up:
                            fp = f"submission_files/{st.session_state.username}_{row['id']}.pdf"
                            with open(fp, "wb") as f: f.write(up.getbuffer())
                            c.execute("INSERT INTO submissions(assignment_id, student_id, submission_time, submission_file) VALUES(?,?,?,?)", (row['id'], st.session_state.user_id, str(datetime.now()), fp))
                            conn.commit(); st.success("Submitted"); st.rerun()
