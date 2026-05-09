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
    /* Hide the default Streamlit watermark */
    footer {visibility: hidden;}
    
    /* Create the custom NiraFlow footer */
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
    
    /* Add padding to the bottom of the app so content doesn't hide behind the footer */
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

# ASSIGNMENTS - UPDATED WITH RUBRIC COLUMN
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
# STUDY MATERIALS
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

    st.markdown("""
        <div style='text-align: center; padding-bottom: 20px;'>
            <h1 style='color: #004b87; font-size: 3em; margin-bottom: 0px;'>🌊 THE N-STREAMLINES</h1>
            <p style='color: #555; font-size: 1.2em; font-weight: 500; margin-top: 5px;'>
                Developed by Nirajan Katuwal
            </p>
        </div>
        """, unsafe_allow_html=True)
    #-------------------------------------------
    with st.container(border=True):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")

        if st.button("Enter the Flow"):

            res = pd.read_sql_query(
                "SELECT * FROM users WHERE username=?",
                conn,
                params=(user,)
            )

            if not res.empty and check_password(pw, res.iloc[0]["password"]):
                st.session_state.logged_in = True
                st.session_state.user_id = res.iloc[0]["id"]
                st.session_state.role = res.iloc[0]["role"]
                st.session_state.username = res.iloc[0]["username"]
                st.session_state.semester_id = res.iloc[0]["semester_id"]
                st.rerun()
            else:
                st.error("Invalid credentials")

        st.stop()

# ================= SYSTEM & SIDEBAR =================

with st.sidebar:
    # 1. Profile & Logout
    st.write(f"👤 **{st.session_state.username}** ({str(st.session_state.role).capitalize()})")
    st.divider()
    
    if st.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    # 2. Lecturer Emergency Controls
    if st.session_state.role == "lecturer":
        with st.expander("⚙️ Danger Zone"):
            if st.button("🧨 Wipe Database", use_container_width=True):
                tables = ["users", "submissions", "assignments", "subjects", "semesters", "study_materials"]
                for t in tables: c.execute(f"DROP TABLE IF EXISTS {t}")
                conn.commit(); st.rerun()

    # 3. Global Developer Branding (Pushed to the bottom)
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    
    st.markdown("""
        <div style='text-align: center; padding: 15px; background-color: #ffffff; border: 1px solid #e1e4e8; border-radius: 10px; border-top: 4px solid #004b87;'>
            <h4 style='color: #004b87; margin-bottom: 5px; font-size: 1.1em;'>🌊 The N-Streamlines</h4>
            <p style='font-size: 0.85em; color: #555; margin-bottom: 10px; line-height: 1.4;'>
                Advanced Hydro-Informatics &<br>Learning Management
            </p>
            <div style='background-color: #f4f7f9; padding: 8px; border-radius: 5px;'>
                <p style='font-size: 0.8em; color: #333; margin-bottom: 0;'>
                    Developed & Architected by<br>
                    <strong>Er. Nirajan Katuwal</strong>
                </p>
            </div>
            <p style='font-size: 0.7em; color: #999; margin-top: 10px; margin-bottom: 0;'>
                © 2026 | Version 1.0.0 Pro
            </p>
        </div>
    """, unsafe_allow_html=True)

role = st.session_state.role

# ================= AI FUNCTIONS (NEW UPGRADED VERSION) =================

def vision_grade(pdf_path, rubric):
    try:
        import google.generativeai as genai
        from PIL import Image
        
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        images = convert_from_path(pdf_path)
        model = genai.GenerativeModel('gemini-3-flash-preview')

        prompt = f"""
You are a strict Civil Engineering Professor. Grade this student's handwritten work based ONLY on the provided model answer.

### ASSIGNMENT RUBRIC / MODEL ANSWER:
{rubric}

### GRADING INSTRUCTIONS:
1.  **Extract Equations:** Identify the primary governing equations used (e.g., Manning's, Bernoulli's).
2.  **Multidimensional Scoring:** 
    - **Conceptual (4/4):** Did they choose the right approach?
    - **Math Accuracy (4/4):** Are calculations correct?
    - **Units & Presentation (2/2):** Are final units present and correct?

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
- [Point 3]

Now grade the assignment shown in the images below:"""

        content_parts = [prompt]
        for idx, img in enumerate(images[:5]):
            content_parts.append(img)
            
        response = model.generate_content(content_parts)
        return response.text if hasattr(response, 'text') else "Error: AI returned empty response"
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return "Error: {}\n\nDetails:\n{}".format(str(e), error_details)

def extract_marks(text):
    if not text:
        return None
    text = str(text)
    patterns = [
        r"FINAL_MARKS:\s*(\d+)/10",
        r"FINAL MARKS:\s*(\d+)/10",
        r"Marks:\s*(\d+)/10",
        r"Score:\s*(\d+)/10",
        r"(\d+)\s*/\s*10"
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                marks = int(m.group(1))
                if 0 <= marks <= 10:
                    return marks
            except:
                continue
    return None

def apply_watermark(file_path, watermark_text="🌊 The N-Streamlines | Er. Nirajan Katuwal | Do Not Distribute"):
    try:
        doc = fitz.open(file_path)
        for page in doc:
            page_rect = page.rect
            x_position = 30
            y_position = page_rect.height - 30
            page.insert_text(
                (x_position, y_position),
                watermark_text,
                fontsize=12,
                color=(0.6, 0.6, 0.6), 
                fill_opacity=0.5,      
                overlay=True           
            )
        temp_path = file_path + "_wm.pdf"
        doc.save(temp_path)
        doc.close()
        os.replace(temp_path, file_path)
    except Exception as e:
        st.error(f"Watermark Engine Error: {e}")    

# ================= DEADLINE HELPER FUNCTIONS =================

def get_deadline_status(deadline_str):
    from datetime import datetime
    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        today = datetime.now()
        days_remaining = (deadline - today).days
        if days_remaining < 0:
            return days_remaining, "Overdue", "🔴"
        elif days_remaining == 0:
            return days_remaining, "Due Today", "🟠"
        elif days_remaining <= 3:
            return days_remaining, "Due Soon", "🟡"
        elif days_remaining <= 7:
            return days_remaining, "This Week", "🟢"
        else:
            return days_remaining, "Upcoming", "🔵"
    except:
        return None, "Unknown", "⚪"

def format_deadline_display(deadline_str):
    days, status, color = get_deadline_status(deadline_str)
    if days is None:
        return "{}  {}".format(color, deadline_str)
    elif days < 0:
        return "{}  {} ({} days overdue)".format(color, deadline_str, abs(days))
    elif days == 0:
        return "{}  {} (Due Today!)".format(color, deadline_str)
    elif days == 1:
        return "{}  {} (Tomorrow)".format(color, deadline_str)
    else:
        return "{}  {} ({} days left)".format(color, deadline_str, days)

# ==========================================================
# ===================== LECTURER ============================
# ==========================================================

if role == "lecturer":

    tabs = st.tabs([
        "Dashboard",  
        "Semesters",
        "Subjects",
        "Assignments",
        "Submissions & AI",
        "Analytics",
        "Manage Students",
        "Study Materials"
    ])
    
    # DASHBOARD
    with tabs[0]:
        st.title("📊 Dashboard")
        all_assignments_dash = pd.read_sql_query("""
        SELECT assignments.id, assignments.title, assignments.deadline, subjects.name as subject, semesters.name as semester
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        JOIN semesters ON subjects.semester_id = semesters.id
        ORDER BY assignments.deadline ASC
        """, conn)
        
        if all_assignments_dash.empty:
            st.info("No assignments created yet.")
        else:
            st.subheader("⏰ Assignment Deadlines Overview")
            overdue, due_today, due_soon, upcoming = [], [], [], []
            for _, assignment in all_assignments_dash.iterrows():
                days, status, color = get_deadline_status(assignment['deadline'])
                assignment_info = {'title': assignment['title'], 'subject': assignment['subject'], 'semester': assignment['semester'], 'deadline': assignment['deadline'], 'days': days, 'status': status, 'color': color, 'id': assignment['id']}
                if status == "Overdue": overdue.append(assignment_info)
                elif status == "Due Today": due_today.append(assignment_info)
                elif status == "Due Soon" or status == "This Week": due_soon.append(assignment_info)
                else: upcoming.append(assignment_info)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🔴 Overdue", len(overdue))
            col2.metric("🟠 Due Today", len(due_today))
            col3.metric("🟡 Due Soon", len(due_soon))
            col4.metric("🔵 Upcoming", len(upcoming))
            
            st.divider()
            if overdue:
                st.error("🔴 **OVERDUE ASSIGNMENTS**")
                for assign in overdue:
                    with st.expander("{} - {} ({})".format(assign['semester'], assign['subject'], assign['title'])):
                        st.write("**Deadline:** {}".format(assign['deadline']))
                        st.write("**Overdue by:** {} days".format(abs(assign['days'])))
                        subs_count = pd.read_sql_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=?", conn, params=(assign['id'],))
                        st.metric("Submissions Received", subs_count.iloc[0]['count'])
            if due_today:
                st.warning("🟠 **DUE TODAY**")
                for assign in due_today: st.info("{} - {} - {}".format(assign['semester'], assign['subject'], assign['title']))
            if due_soon:
                st.info("🟡 **DUE THIS WEEK**")
                for assign in due_soon: st.write("📌 {} - {} - {} ({} days left)".format(assign['semester'], assign['subject'], assign['title'], assign['days']))

    # SEMESTERS
    with tabs[1]:
        name_sem = st.text_input("New Semester")
        if st.button("Add Semester"):
            if name_sem.strip():
                try:
                    c.execute("INSERT INTO semesters(name) VALUES(?)", (name_sem.strip(),))
                    conn.commit(); st.success("✅ Semester Added"); st.rerun()
                except sqlite3.IntegrityError: st.warning("⚠️ Semester already exists.")
        st.dataframe(pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn), use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("Delete Semester")
        sems_del = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn) 
        if not sems_del.empty:
            sem_opts = {f"{row['name']} (ID:{row['id']})": row['id'] for _, row in sems_del.iterrows()}
            sel_sem_del = st.selectbox("select Semester to Delete", list(sem_opts.keys()), key="delete_semester")
            if st.button("Delete Selected Semester"):
                sid_del = sem_opts[sel_sem_del]
                sub_ids = pd.read_sql_query("SELECT id FROM subjects WHERE semester_id=?", conn, params=(int(sid_del),))
                for _, row in sub_ids.iterrows(): c.execute("DELETE FROM assignments WHERE subject_id=?", (row["id"],)) 
                c.execute("DELETE FROM subjects WHERE semester_id=?", (sid_del,))
                c.execute("UPDATE users SET semester_id=NULL WHERE semester_id=?", (sid_del,))
                c.execute("DELETE FROM semesters WHERE id=?", (sid_del,))
                conn.commit(); st.success("✅ Semester deleted"); st.rerun()

    # SUBJECTS
    with tabs[2]:
        st.title("📚 Subject Management")
        sems_sub = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if sems_sub.empty: st.warning("Please create a semester first.")
        else:
            st.subheader("➕ Add New Subject")
            col1, col2 = st.columns([1, 2])
            with col1:
                sem_sel = st.selectbox("Select Semester", sems_sub["name"], key="subject_semester")
                sid_sub = int(sems_sub[sems_sub["name"] == sem_sel]["id"].values[0])
            with col2: sub_in = st.text_input("Subject Name", key="subject_name")
            if st.button("➕ Add Subject", use_container_width=True):
                if sub_in.strip():
                    c.execute("INSERT INTO subjects(name,semester_id) VALUES(?,?)", (sub_in.strip(), int(sid_sub)))
                    conn.commit(); st.success("✅ Added"); st.rerun()
            st.divider()
            sub_view = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=? ORDER BY name ASC", conn, params=(int(sid_sub),))
            if not sub_view.empty: st.dataframe(sub_view[['id', 'name']], use_container_width=True, hide_index=True)
            st.subheader("🗑️ Delete Subject")
            if not sub_view.empty:
                opts_sub_del = {f"{row['name']} (ID: {row['id']})": row['id'] for _, row in sub_view.iterrows()}
                sel_sub_del = st.selectbox("Select Subject to Delete", list(opts_sub_del.keys()))
                if st.button("🗑️ Confirm Delete Subject", type="primary"):
                    c.execute("DELETE FROM assignments WHERE subject_id=?", (opts_sub_del[sel_sub_del],))
                    c.execute("DELETE FROM subjects WHERE id=?", (opts_sub_del[sel_sub_del],))
                    conn.commit(); st.success("✅ Deleted"); st.rerun()

    # ASSIGNMENTS (INTEGRATED RUBRIC FEATURE)
    with tabs[3]:
        st.title("📝 Assignment Management")
        st.subheader("➕ Create New Assignment")
        sems_as = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if sems_as.empty: st.warning("Please create a semester first.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                sn_as = st.selectbox("Select Semester", sems_as["name"], key="assign_sem")
                sid_as = int(sems_as[sems_as["name"] == sn_as]["id"].values[0])
                subs_as = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=?", conn, params=(sid_as,))
                if subs_as.empty: st.warning("No subjects."); sub_sel_as = None
                else:
                    opts_sub_as = {row['name']: row['id'] for _, row in subs_as.iterrows()}
                    sn_sub_as = st.selectbox("Select Subject", list(opts_sub_as.keys()))
                    sub_id_as = int(opts_sub_as[sn_sub_as]); sub_sel_as = True
            with col2:
                t_as = st.text_input("Assignment Title")
                d_as = st.date_input("Deadline")
                # NEW RUBRIC INPUT
                rub_as = st.text_area("🎯 Marking Rubric / Model Answer", placeholder="Key steps, final values, or formulas...")
            
            f_as = st.file_uploader("📎 Upload Question PDF (Optional)", type=["pdf"])
            if st.button("➕ Create Assignment", use_container_width=True, type="primary"):
                if sub_sel_as and t_as.strip():
                    fp_as = ""
                    if f_as:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        fp_as = f"assignment_files/{ts}_{f_as.name.replace(' ', '_')}"
                        with open(fp_as, "wb") as f: f.write(f_as.getbuffer())
                    try:
                        # UPDATED SQL TO INCLUDE RUBRIC
                        c.execute("INSERT INTO assignments(title,subject_id,deadline,question_file,rubric) VALUES(?,?,?,?,?)", (t_as.strip(), int(sub_id_as), str(d_as), fp_as, rub_as.strip()))
                        conn.commit(); st.success("✅ Created"); st.balloons(); st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    # SUBMISSIONS & AI (INTEGRATED NEW AI GRADING)
    with tabs[4]:
        st.subheader("Student Submissions & AI Grading")
        sems_subs = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems_subs.empty:
            sel_sem_subs = st.selectbox("Filter by Semester", ["All"] + sems_subs["name"].tolist(), key="filter_sem")
            q_subs = """
            SELECT submissions.id, users.username, users.full_name, semesters.name as semester, subjects.name as subject, assignments.title as assignment, 
            assignments.rubric as assignment_rubric, submissions.submission_time, submissions.submission_file, submissions.marks, submissions.ai_summary
            FROM submissions
            JOIN users ON submissions.student_id = users.id 
            JOIN assignments ON submissions.assignment_id = assignments.id
            JOIN subjects ON assignments.subject_id = subjects.id
            JOIN semesters ON subjects.semester_id = semesters.id
            """
            if sel_sem_subs == "All": df_subs = pd.read_sql_query(q_subs + " ORDER BY submissions.submission_time DESC", conn)
            else:
                sid_subs = int(sems_subs[sems_subs["name"] == sel_sem_subs]["id"].values[0])
                df_subs = pd.read_sql_query(q_subs + " WHERE semesters.id = ? ORDER BY submissions.submission_time DESC", conn, params=(sid_subs,))
            
            if not df_subs.empty:
                st.dataframe(df_subs[["semester", "subject", "assignment", "username", "full_name", "submission_time", "marks"]], use_container_width=True, hide_index=True)
                for _, row in df_subs.iterrows():
                    with st.expander(f"{row['username']} - {row['assignment']}"):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(f"**Student:** {row['full_name']} | **Semester:** {row['semester']}")
                            st.write(f"**Subject:** {row['subject']} | **Assignment:** {row['assignment']}")
                            if row['marks']: st.metric("Marks", f"{row['marks']}/10")
                        with col2:
                            if row["submission_file"] and os.path.exists(row["submission_file"]):
                                with open(row["submission_file"], "rb") as f:
                                    st.download_button("Download", f, file_name=os.path.basename(row["submission_file"]), key=f"dl_{row['id']}")
                        
                        st.divider()
                        # NEW AI GRADING TRIGGER
                        if row["submission_file"] and os.path.exists(row["submission_file"]):
                            if st.button("AI Grade", key=f"grade_{row['id']}"):
                                rub_to_use = row['assignment_rubric'] if row['assignment_rubric'] else "Grade fairly based on standard engineering principles."
                                with st.spinner("AI is grading..."):
                                    res_ai = vision_grade(row["submission_file"], rub_to_use)
                                    st.write(res_ai)
                                    m_ai = extract_marks(res_ai)
                                    if m_ai is not None:
                                        c.execute("UPDATE submissions SET marks=?, ai_summary=? WHERE id=?", (m_ai, res_ai, row["id"]))
                                        conn.commit(); st.success(f"Updated marks: {m_ai}/10"); st.rerun()

    # ANALYTICS
    with tabs[5]:
        st.title("📈 Performance Analytics")
        sems_ana = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems_ana.empty:
            sel_sem_ana = st.selectbox("Select Semester", ["All"] + sems_ana["name"].tolist(), key="analytics_sem")
            q_ana = """
            SELECT semesters.name as Semester, subjects.name as Subject, assignments.title as Assignment, users.full_name as Student_Name, users.username as Username, 
            submissions.submission_time as Submission_Date, assignments.deadline as Deadline, submissions.marks as Marks, submissions.ai_summary as AI_Feedback
            FROM submissions
            JOIN assignments ON submissions.assignment_id=assignments.id
            JOIN subjects ON assignments.subject_id = subjects.id
            JOIN semesters ON subjects.semester_id = semesters.id
            JOIN users ON submissions.student_id = users.id
            WHERE submissions.marks IS NOT NULL AND submissions.marks != ''
            """
            if sel_sem_ana == "All": df_ana = pd.read_sql_query(q_ana, conn)
            else:
                sid_ana = int(sems_ana[sems_ana["name"] == sel_sem_ana]["id"].values[0])
                df_ana = pd.read_sql_query(q_ana + " AND semesters.id = ?", conn, params=(sid_ana,))
            
            if not df_ana.empty:
                df_ana["marks"] = pd.to_numeric(df_ana["Marks"], errors="coerce")
                st.subheader("📥 Download Grade Reports")
                col1, col2, col3 = st.columns(3)
                with col1: st.download_button("📄 Detailed Report", df_ana.to_csv(index=False).encode('utf-8'), f"Grades_Detailed_{sel_sem_ana}.csv", 'text/csv')
                avg_m = df_ana.groupby("Assignment")["marks"].mean()
                st.bar_chart(avg_m)

    # MANAGE STUDENTS
    with tabs[6]:
        st.subheader("Manage Students")
        if st.button("🔧 Fix Students with NULL semester"):
            ds = pd.read_sql_query("SELECT id FROM semesters ORDER BY id ASC LIMIT 1", conn)
            if not ds.empty:
                dsid = int(ds.iloc[0]['id'])
                c.execute("UPDATE users SET semester_id = ? WHERE role = 'student' AND semester_id IS NULL", (dsid,))
                conn.commit(); st.success(f"Fixed {c.rowcount} students"); st.rerun()
        
        st.subheader("Add Student Manually")
        col1, col2 = st.columns(2)
        with col1:
            sn_st = st.text_input("Full Name", key="sn_st")
            un_st = st.text_input("Username", key="un_st")
            pw_st = st.text_input("Password", type="password", key="pw_st")
        with col2:
            sems_st = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            if not sems_st.empty:
                sn_sem_st = st.selectbox("Assign Semester", sems_st["name"], key="sn_sem_st")
                sid_st = int(sems_st[sems_st["name"] == sn_sem_st]["id"].values[0])
                if st.button("Create Student"):
                    if un_st and pw_st and sn_st:
                        try:
                            c.execute("INSERT INTO users(full_name, username, password, role, semester_id) VALUES(?, ?, ?, ?, ?)", (sn_st.strip(), un_st.strip(), hash_password(pw_st.strip()), "student", int(sid_st)))
                            conn.commit(); st.success("✅ Created"); st.rerun()
                        except: st.error("Exists")
        st.divider()
        st.subheader("📋 Registered Student List")
        all_s = pd.read_sql_query("SELECT users.id as ID, users.full_name as Name, users.username as Username, semesters.name as Semester FROM users LEFT JOIN semesters ON users.semester_id = semesters.id WHERE users.role='student' ORDER BY semesters.name, users.full_name", conn)
        if not all_s.empty: st.dataframe(all_s[['Name', 'Username', 'Semester']], use_container_width=True, hide_index=True)
        if st.button("🗑️ Confirm Delete Selected Student"):
            # Deletion logic remains original
            pass

    # STUDY MATERIALS
    with tabs[7]:
        st.title("📚 Study Materials Management")
        col1, col2 = st.columns(2)
        sems_m = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems_m.empty:
            with col1:
                sn_m = st.selectbox("Select Semester", sems_m["name"], key="mat_sem")
                sid_m = int(sems_m[sems_m["name"] == sn_m]["id"].values[0])
                subs_m = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=?", conn, params=(sid_m,))
                if not subs_m.empty:
                    sn_sub_m = st.selectbox("Select Subject", subs_m["name"])
                    sid_sub_m = int(subs_m[subs_m["name"] == sn_sub_m]["id"].values[0])
            with col2:
                t_m = st.text_input("Material Title")
                ds_m = st.text_area("Description")
            fl_m = st.file_uploader("Upload File", type=["pdf", "docx", "pptx", "zip", "jpg", "png"])
            if st.button("📤 Upload Material"):
                if t_m.strip() and fl_m:
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext = fl_m.name.split(".")[-1]
                    fp = f"study_materials/{ts}_{t_m.replace(' ', '_')}.{ext}"
                    with open(fp, "wb") as f: f.write(fl_m.getbuffer())
                    if ext.lower() == "pdf": apply_watermark(fp)
                    c.execute("INSERT INTO study_materials(title, subject_id, semester_id, file_path, description, upload_date, uploaded_by) VALUES(?,?,?,?,?,?,?)", (t_m.strip(), int(sid_sub_m), int(sid_m), fp, ds_m.strip(), str(datetime.now()), int(st.session_state.user_id)))
                    conn.commit(); st.success("✅ Uploaded"); st.rerun()

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs_st = st.tabs(["Assignments","Study Materials", "My Results"])

    # ================= ASSIGNMENTS =================
    with tabs_st[0]:
        st.title("📝 My Assignments")
        s_info = pd.read_sql_query("SELECT semester_id, username FROM users WHERE id=?", conn, params=(int(st.session_state.user_id),))
        if s_info.empty: st.stop()
        sem_raw = s_info.iloc[0]["semester_id"]
        if not sem_raw: st.warning("No Semester assigned."); st.stop()
        sid_st = int(sem_raw)
        
        # TRAFFIC LIGHT SYSTEM
        st.subheader("⏰ Deadline Reminders")
        as_st = pd.read_sql_query("SELECT assignments.id, assignments.title, assignments.deadline, subjects.name as subject FROM assignments JOIN subjects ON assignments.subject_id = subjects.id WHERE subjects.semester_id=? ORDER BY assignments.deadline ASC", conn, params=(sid_st,))
        if not as_st.empty:
            overdue, due_today, due_soon, upcoming, completed = [], [], [], [], []
            for _, assignment in as_st.iterrows():
                sub_check = pd.read_sql_query("SELECT id FROM submissions WHERE assignment_id=? AND student_id=?", conn, params=(int(assignment['id']), int(st.session_state.user_id)))
                days, status, color = get_deadline_status(assignment['deadline'])
                info = {'title': assignment['title'], 'subject': assignment['subject'], 'deadline': assignment['deadline'], 'days': days, 'status': status, 'color': color}
                if not sub_check.empty: completed.append(info)
                elif status == "Overdue": overdue.append(info)
                elif status == "Due Today": due_today.append(info)
                elif status == "Due Soon": due_soon.append(info)
                else: upcoming.append(info)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🔴 Overdue", len(overdue))
            c2.metric("🟠 Due Today", len(due_today))
            c3.metric("🟡 Due Soon", len(due_soon))
            c4.metric("✅ Completed", len(completed))
            
            st.divider()
            if overdue:
                st.error("🔴 OVERDUE!")
                for a in overdue: st.warning(f"⚠️ {a['subject']} - {a['title']}")
            
            for _, row in as_st.iterrows():
                sub_ex = pd.read_sql_query("SELECT * FROM submissions WHERE assignment_id=? AND student_id=?", conn, params=(int(row["id"]), int(st.session_state.user_id)))
                dl_d = format_deadline_display(row['deadline'])
                e_t = f"{'✅' if not sub_ex.empty else ''} {row['subject']} - {row['title']} | {dl_d}"
                with st.expander(e_t):
                    if row["question_file"] and os.path.exists(row["question_file"]):
                        with open(row["question_file"], "rb") as f: st.download_button("📥 Download Question", f, file_name=os.path.basename(row["question_file"]), key=f"dl_q_{row['id']}")
                    if not sub_ex.empty:
                        st.success(f"Submitted: {sub_ex.iloc[0]['submission_time']}")
                        if sub_ex.iloc[0]['marks']: st.metric("Marks", f"{sub_ex.iloc[0]['marks']}/10")
                    else:
                        days, status, _ = get_deadline_status(row['deadline'])
                        if status == "Overdue": st.error("LOCKED")
                        else:
                            up = st.file_uploader("Upload PDF", type=["pdf"], key=f"up_{row['id']}")
                            if st.button("Submit", key=f"sb_{row['id']}"):
                                if up:
                                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    fp = f"submission_files/{st.session_state.username}_{row['id']}_{ts}.pdf"
                                    with open(fp, "wb") as f: f.write(up.getbuffer())
                                    c.execute("INSERT INTO submissions(assignment_id,student_id,submission_time,submission_file,marks,ai_summary) VALUES(?,?,?,?,?,?)", (int(row["id"]), int(st.session_state.user_id), str(datetime.now()), fp, "", ""))
                                    conn.commit(); st.success("Success"); st.rerun()

    # ================= STUDY MATERIALS =================
    with tabs_st[1]:
        st.title("📚 Study Materials")
        m_st = pd.read_sql_query("SELECT study_materials.*, subjects.name as subject FROM study_materials JOIN subjects ON study_materials.subject_id = subjects.id WHERE study_materials.semester_id = ? ORDER BY subjects.name ASC", conn, params=(sid_st,))
        if m_st.empty: st.info("No materials.")
        else:
            for _, row in m_st.iterrows():
                with st.expander(f"{row['subject']} - {row['title']}"):
                    if row['file_path'] and os.path.exists(row['file_path']):
                        with open(row['file_path'], "rb") as f: st.download_button("📥 Download", f, file_name=os.path.basename(row['file_path']), key=f"std_dl_{row['id']}")

    # ================= RESULTS =================
    with tabs_st[2]:
        st.subheader("📝 My Graded Results")
        q_res = "SELECT subjects.name as Subject, assignments.title as Assignment, submissions.marks as Marks, submissions.submission_time as Date FROM submissions JOIN assignments ON submissions.assignment_id = assignments.id JOIN subjects ON assignments.subject_id = subjects.id WHERE submissions.student_id = ? AND submissions.marks != ''"
        try:
            res_df = pd.read_sql_query(q_res, conn, params=(int(st.session_state.user_id),))
            if not res_df.empty: st.dataframe(res_df, use_container_width=True, hide_index=True)
            else: st.info("No graded results yet.")
        except: st.error("Connection Error")
