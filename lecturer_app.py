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
                tables = ["users", "submissions", "assignments", "subjects", "semesters"]
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

# ================= AI FUNCTIONS =================

def vision_grade(pdf_path, rubric):
    try:
        import google.generativeai as genai
        from PIL import Image
        
        #CONFIGURE WITH api KEY
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        #CONVERT pdf TO IMAGES
        images = convert_from_path(pdf_path)

        #Use Gemini Flash Model
        model=genai.GenerativeModel('gemini-3-flash-preview')

        #prepare the text prompt
        prompt = """
You are a strict civil engineering professor.

MODEL ANSWER/Rubric:
{}

#please grade the submitted assignment shown in the images.

Grade the assignment and Return your response in EXACTLY this format:
FINAL_MARKS: X/10
FEEDBACK:
- Point 1
- Point 2
- Point #
Now grade the assignment shown the images below:""".format(rubric)

        #Prepare content-text first, then PIL images directly
        content_parts = [prompt]

        #ADD images (limit to first 5 pages to avoid token limits)
        for idx,img in enumerate(images[:5]):
            content_parts.append(img)
        #Generate Response
        response = model.generate_content(content_parts)
        if response and hasattr(response, 'text'):
            return response.text
        else:
            return "Error: AI returned empty response"
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return "Error: {}\n\nDetails:\n{}".format(str(e), error_details)

def extract_marks(text):
    """
    Extract marks from AI response text.
    Returns aninteger between 1-10, or None if not found.
    """
    if not text:
        return None
    #convert to string in case it's not
    text = str(text)
    
    #Try multiple patterns to extract marks 
    patterns = [
        r"FINAL_MARKS:\s*(|d+)/10",
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
                #Ensure marks are within valid range
                if 0 <= marks <=10:
                    return marks
            except (ValueError, IndexError):
                continue
    return none
def apply_watermark(file_path, watermark_text="🌊 The N-Streamlines | Er. Nirajan Katuwal | Do Not Distribute"):
    """Stamps a watermark on every page of a PDF."""
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
    """
    Calculate days until deadline and return status
    Returns: (days_remaining, status, color)
    """
    from datetime import datetime, timedelta
    
    try:
        # Parse deadline
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        today = datetime.now()
        
        # Calculate difference
        days_remaining = (deadline - today).days
        
        # Determine status
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
    """
    Format deadline string for display with countdown
    """
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
        "Study Materilas"
    ])
        # DASHBOARD
    with tabs[0]:
        
        st.title("📊 Dashboard")
        
        # Get all assignments
        all_assignments = pd.read_sql_query("""
        SELECT 
            assignments.id,
            assignments.title,
            assignments.deadline,
            subjects.name as subject,
            semesters.name as semester
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        JOIN semesters ON subjects.semester_id = semesters.id
        ORDER BY assignments.deadline ASC
        """, conn)
        
        if all_assignments.empty:
            st.info("No assignments created yet.")
        else:
            st.subheader("⏰ Assignment Deadlines Overview")
            
            # Categorize assignments
            overdue = []
            due_today = []
            due_soon = []
            upcoming = []
            
            for _, assignment in all_assignments.iterrows():
                days, status, color = get_deadline_status(assignment['deadline'])
                
                assignment_info = {
                    'title': assignment['title'],
                    'subject': assignment['subject'],
                    'semester': assignment['semester'],
                    'deadline': assignment['deadline'],
                    'days': days,
                    'status': status,
                    'color': color,
                    'id': assignment['id']
                }
                
                if status == "Overdue":
                    overdue.append(assignment_info)
                elif status == "Due Today":
                    due_today.append(assignment_info)
                elif status == "Due Soon" or status == "This Week":
                    due_soon.append(assignment_info)
                else:
                    upcoming.append(assignment_info)
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🔴 Overdue", len(overdue))
            with col2:
                st.metric("🟠 Due Today", len(due_today))
            with col3:
                st.metric("🟡 Due This Week", len(due_soon))
            with col4:
                st.metric("🔵 Upcoming", len(upcoming))
            
            st.divider()
            
            # Show details
            if overdue:
                st.error("🔴 **OVERDUE ASSIGNMENTS**")
                for assign in overdue:
                    with st.expander("{} - {} ({})".format(assign['semester'], assign['subject'], assign['title'])):
                        st.write("**Deadline:** {}".format(assign['deadline']))
                        st.write("**Overdue by:** {} days".format(abs(assign['days'])))
                        
                        # Show submission stats
                        submissions = pd.read_sql_query("""
                        SELECT COUNT(*) as count FROM submissions
                        WHERE assignment_id=?
                        """, conn, params=(assign['id'],))
                        
                        st.metric("Submissions Received", submissions.iloc[0]['count'])
            
            if due_today:
                st.warning("🟠 **DUE TODAY**")
                for assign in due_today:
                    st.info("{} - {} - {}".format(assign['semester'], assign['subject'], assign['title']))
            
            if due_soon:
                st.info("🟡 **DUE THIS WEEK**")
                for assign in due_soon:
                    st.write("📌 {} - {} - {} ({} days left)".format(
                        assign['semester'],
                        assign['subject'],
                        assign['title'],
                        assign['days']
                    ))
            
            st.divider()
            
            # Submission statistics
            st.subheader("📈 Submission Statistics")
            
            for _, assignment in all_assignments.iterrows():
                # Count submissions
                total_submissions = pd.read_sql_query("""
                SELECT COUNT(*) as count FROM submissions
                WHERE assignment_id=?
                """, conn, params=(assignment['id'],)).iloc[0]['count']
                
                # Count total students in semester
                semester_id = pd.read_sql_query("""
                SELECT semester_id FROM subjects WHERE id=?
                """, conn, params=(assignment['subject'],))
                
                deadline_display = format_deadline_display(assignment['deadline'])
                
                with st.expander("{} - {} | {}".format(assignment['subject'], assignment['title'], deadline_display)):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.metric("Total Submissions", total_submissions)
                    
                    with col_b:
                        graded = pd.read_sql_query("""
                        SELECT COUNT(*) as count FROM submissions
                        WHERE assignment_id=? AND marks IS NOT NULL AND marks != ''
                        """, conn, params=(assignment['id'],)).iloc[0]['count']
                        
                        st.metric("Graded", graded)
    # SEMESTERS
    with tabs[1]:
        name = st.text_input("New Semester")

        if st.button("Add Semester"):
            if not name.strip():
                st.error("Semester name cannot be empty.")
            else:
                try:
                    c.execute("INSERT INTO semesters(name) VALUES(?)", (name.strip(),))
                    conn.commit()
                    st.success("✅ Semester Added")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("⚠️ Semester already exists.")

        st.dataframe(
            pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn),
            use_container_width=True,
            hide_index=True
        )
        st.divider()
        st.subheader("Delete Semester")

        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn) 
        if not sems.empty:
            semester_options={
                f"{row['name']} (ID:{row['id']})": row['id']
                for _, row in sems.iterrows()
            }

            selected_sem = st.selectbox(
                "select Semester to Delete",
                list(semester_options.keys()),
                key="delete_semester"
            )
            if st.button("Delete Selected Semester"):

                sem_id = semester_options[selected_sem]
                subject_ids=pd.read_sql_query(
                    "SELECT id FROM subjects WHERE semester_id=?",
                    conn,
                    params=(int(sem_id),)
                )
                for _, row in subject_ids.iterrows():
                    c.execute("DELETE FROM assignments WHERE subject_id=?", (row["id"],)) 
                c.execute("DELETE FROM subjects WHERE semester_id=?", (sem_id,))
                c.execute("UPDATE users SET semester_id=NULL WHERE semester_id=?", (sem_id,))
                c.execute("DELETE FROM semesters WHERE id=?", (sem_id,))

                conn.commit()
                st.success("✅ Semester deleted successfully.")
                st.rerun()

        # SUBJECTS
    with tabs[2]:  # Adjust index based on your setup
        
        st.title("📚 Subject Management")
        
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            # ========== ADD SUBJECT ==========
            st.subheader("➕ Add New Subject")
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                sem = st.selectbox("Select Semester", sems["name"], key="subject_semester")
                sem_id = int(sems[sems["name"] == sem]["id"].values[0])
            
            with col2:
                sub = st.text_input("Subject Name", key="subject_name", placeholder="e.g., Structural Analysis")
            
            if st.button("➕ Add Subject", use_container_width=True):
                if not sub.strip():
                    st.error("Subject name cannot be empty.")
                else:
                    try:
                        c.execute(
                            "INSERT INTO subjects(name,semester_id) VALUES(?,?)",
                            (sub.strip(), int(sem_id))
                        )
                        conn.commit()
                        st.success("✅ Subject '{}' added to {}".format(sub.strip(), sem))
                        st.rerun()
                    except Exception as e:
                        st.error("Error adding subject: {}".format(str(e)))
            
            st.divider()
            
            # ========== VIEW SUBJECTS ==========
            st.subheader("📋 Subjects for: {}".format(sem))
            
            subjects_for_sem = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=? ORDER BY name ASC",
                conn,
                params=(int(sem_id),)
            )
            
            if subjects_for_sem.empty:
                st.info("No subjects found for this semester.")
            else:
                st.dataframe(
                    subjects_for_sem[['id', 'name']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "id": "Subject ID",
                        "name": "Subject Name"
                    }
                )
                
                st.info("📊 Total Subjects: **{}**".format(len(subjects_for_sem)))
            
            st.divider()
            
            # ========== DELETE SUBJECT ==========
            st.subheader("🗑️ Delete Subject")
            
            if not subjects_for_sem.empty:
                
                # Create options for deletion
                subject_options = {
                    "{} (ID: {})".format(row['name'], row['id']): row['id']
                    for _, row in subjects_for_sem.iterrows()
                }
                
                selected_subject = st.selectbox(
                    "Select Subject to Delete from {}".format(sem),
                    list(subject_options.keys()),
                    key="delete_subject_select"
                )
                
                col_warn1, col_warn2 = st.columns([2, 1])
                
                with col_warn1:
                    st.warning("⚠️ **Warning:** Deleting a subject will also delete:\n- All assignments under this subject\n- All submissions for those assignments")
                
                with col_warn2:
                    if st.button("🗑️ Confirm Delete Subject", type="primary", use_container_width=True):
                        
                        subject_id = subject_options[selected_subject]
                        
                        try:
                            # Get all assignment IDs for this subject
                            assignment_ids = pd.read_sql_query(
                                "SELECT id FROM assignments WHERE subject_id=?",
                                conn,
                                params=(int(subject_id),)
                            )
                            
                            # Delete submissions for each assignment
                            for _, row in assignment_ids.iterrows():
                                c.execute("DELETE FROM submissions WHERE assignment_id=?", (row["id"],))
                            
                            # Delete all assignments for this subject
                            c.execute("DELETE FROM assignments WHERE subject_id=?", (int(subject_id),))
                            
                            # Delete all study materials for this subject
                            materials = pd.read_sql_query(
                                "SELECT file_path FROM study_materials WHERE subject_id=?",
                                conn,
                                params=(int(subject_id),)
                            )
                            for _, mat in materials.iterrows():
                                if mat['file_path'] and os.path.exists(mat['file_path']):
                                    os.remove(mat['file_path'])
                            
                            c.execute("DELETE FROM study_materials WHERE subject_id=?", (int(subject_id),))
                            
                            # Finally, delete the subject
                            c.execute("DELETE FROM subjects WHERE id=?", (int(subject_id),))
                            
                            conn.commit()
                            st.success("✅ Subject deleted successfully!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error("Error deleting subject: {}".format(str(e)))
            else:
                st.info("No subjects available to delete in this semester.")
            
            st.divider()
            
            # ========== ALL SUBJECTS DEBUG ==========
            with st.expander("🔍 View All Subjects (All Semesters)"):
                all_subjects_debug = pd.read_sql_query("""
                SELECT 
                    subjects.id as ID,
                    subjects.name as Subject,
                    semesters.name as Semester
                FROM subjects
                JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY semesters.name, subjects.name
                """, conn)
                
                if not all_subjects_debug.empty:
                    st.dataframe(all_subjects_debug, use_container_width=True, hide_index=True)
                else:
                    st.info("No subjects created yet.")

        # ASSIGNMENTS
    with tabs[3]:  # Adjust index based on your setup
        
        st.title("📝 Assignment Management")
        
        # ========== CREATE NEW ASSIGNMENT ==========
        st.subheader("➕ Create New Assignment")

        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                sem_name = st.selectbox("Select Semester", sems["name"], key="assign_sem")
                sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])

                subjects = pd.read_sql_query(
                    "SELECT * FROM subjects WHERE semester_id=?",
                    conn,
                    params=(sem_id,)
                )

                if subjects.empty:
                    st.warning("Please create a subject for this semester first.")
                    subject_selected = None
                else:
                    subject_options = {
                        row['name']: row['id']
                        for _, row in subjects.iterrows()
                    }

                    selected_subject = st.selectbox("Select Subject", list(subject_options.keys()))
                    sub_id = int(subject_options[selected_subject])
                    subject_selected = True
            
            with col2:
                title = st.text_input("Assignment Title", placeholder="e.g., Design of RCC Beam")
                deadline = st.date_input("Deadline")
            
            file = st.file_uploader("📎 Upload Assignment Question PDF (Optional)", type=["pdf"])

            if st.button("➕ Create Assignment", use_container_width=True, type="primary"):

                if not subject_selected:
                    st.error("Please select a subject.")
                elif not title.strip():
                    st.error("Title cannot be empty.")
                else:
                    file_path = ""

                    if file:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        file_path = "assignment_files/{}_{}.pdf".format(timestamp, file.name.replace(" ", "_"))
                        with open(file_path, "wb") as f:
                            f.write(file.getbuffer())

                    try:
                        c.execute("""
                        INSERT INTO assignments(title,subject_id,deadline,question_file)
                        VALUES(?,?,?,?)
                        """, (title.strip(), int(sub_id), str(deadline), file_path))

                        conn.commit()
                        st.success("✅ Assignment '{}' created successfully!".format(title.strip()))
                        st.balloons()
                        st.rerun()

                    except Exception as e:
                        st.error("Error: {}".format(str(e)))

        st.divider()
        
        # ========== VIEW ASSIGNMENTS ==========
        st.subheader("📋 Existing Assignments")
        
        # Filter option
        view_sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not view_sems.empty:
            view_filter = st.selectbox("Filter by Semester", ["All"] + view_sems["name"].tolist(), key="view_assign_filter")
            
            if view_filter == "All":
                all_assignments = pd.read_sql_query("""
                SELECT 
                    assignments.id as ID,
                    assignments.title as Title,
                    subjects.name as Subject,
                    semesters.name as Semester,
                    assignments.deadline as Deadline,
                    assignments.question_file as File
                FROM assignments
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY assignments.deadline DESC
                """, conn)
            else:
                filter_sem_id = int(view_sems[view_sems["name"] == view_filter]["id"].values[0])
                all_assignments = pd.read_sql_query("""
                SELECT 
                    assignments.id as ID,
                    assignments.title as Title,
                    subjects.name as Subject,
                    semesters.name as Semester,
                    assignments.deadline as Deadline,
                    assignments.question_file as File
                FROM assignments
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                WHERE semesters.id = ?
                ORDER BY assignments.deadline DESC
                """, conn, params=(filter_sem_id,))

            if all_assignments.empty:
                st.info("No assignments created yet.")
            else:
                # Show table without file path
                st.dataframe(
                    all_assignments[['ID', 'Semester', 'Subject', 'Title', 'Deadline']],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info("📊 Total Assignments: **{}**".format(len(all_assignments)))
                
                st.divider()
                
                # ========== ASSIGNMENT DETAILS WITH DELETE ==========
                st.subheader("📄 Assignment Details")
                
                for _, assignment in all_assignments.iterrows():
                    
                    # Get submission count
                    submission_count = pd.read_sql_query("""
                    SELECT COUNT(*) as count FROM submissions
                    WHERE assignment_id=?
                    """, conn, params=(assignment['ID'],)).iloc[0]['count']
                    
                    deadline_display = format_deadline_display(assignment['Deadline'])
                    
                    with st.expander("{} - {} - {} | {}".format(
                        assignment['Semester'],
                        assignment['Subject'],
                        assignment['Title'],
                        deadline_display
                    )):
                        
                        col_detail1, col_detail2 = st.columns([2, 1])
                        
                        with col_detail1:
                            st.write("**Semester:** {}".format(assignment['Semester']))
                            st.write("**Subject:** {}".format(assignment['Subject']))
                            st.write("**Title:** {}".format(assignment['Title']))
                            st.write("**Deadline:** {}".format(assignment['Deadline']))
                            st.metric("📊 Total Submissions", submission_count)
                        
                        with col_detail2:
                            # Download assignment file
                            if assignment['File'] and os.path.exists(assignment['File']):
                                with open(assignment['File'], "rb") as f:
                                    st.download_button(
                                        "📥 Download Question",
                                        f,
                                        file_name=os.path.basename(assignment['File']),
                                        key="download_assign_{}".format(assignment['ID']),
                                        use_container_width=True
                                    )
                            else:
                                st.info("No file uploaded")
                        
                        st.divider()
                        
                        # Delete button
                        col_del1, col_del2 = st.columns([2, 1])
                        
                        with col_del1:
                            st.warning("⚠️ **Delete Assignment:** This will remove all student submissions for this assignment.")
                        
                        with col_del2:
                            if st.button("🗑️ Delete Assignment", key="delete_assign_{}".format(assignment['ID']), type="primary", use_container_width=True):
                                
                                try:
                                    # Delete all submissions first
                                    submissions = pd.read_sql_query("""
                                    SELECT submission_file FROM submissions
                                    WHERE assignment_id=?
                                    """, conn, params=(assignment['ID'],))
                                    
                                    # Delete submission files
                                    for _, sub in submissions.iterrows():
                                        if sub['submission_file'] and os.path.exists(sub['submission_file']):
                                            os.remove(sub['submission_file'])
                                    
                                    # Delete submissions from database
                                    c.execute("DELETE FROM submissions WHERE assignment_id=?", (assignment['ID'],))
                                    
                                    # Delete assignment file
                                    if assignment['File'] and os.path.exists(assignment['File']):
                                        os.remove(assignment['File'])
                                    
                                    # Delete assignment from database
                                    c.execute("DELETE FROM assignments WHERE id=?", (assignment['ID'],))
                                    
                                    conn.commit()
                                    st.success("✅ Assignment '{}' deleted successfully!".format(assignment['Title']))
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error("Error deleting assignment: {}".format(str(e)))
    # SUBMISSIONS & AI
    with tabs[4]:

        st.subheader("Student Submissions & AI Grading")

        # filter by semester
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if not sems.empty:
            selected_sem = st.selectbox("Filter by Semester", ["All"] + sems["name"].tolist(), key="filter_sem")

            if selected_sem == "All":
                df = pd.read_sql_query("""
                SELECT
                    submissions.id,
                    users.username,
                    users.full_name,
                    semesters.name as semester,
                    subjects.name as subject,
                    assignments.title as assignment,
                    submissions.submission_time,
                    submissions.submission_file,
                    submissions.marks,
                    submissions.ai_summary
                FROM submissions
                JOIN users ON submissions.student_id = users.id 
                JOIN assignments ON submissions.assignment_id = assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY submissions.submission_time DESC
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = pd.read_sql_query("""
                SELECT
                    submissions.id, 
                    users.username,
                    users.full_name,
                    semesters.name as semester,
                    subjects.name as subject,
                    assignments.title as assignment,
                    submissions.submission_time,
                    submissions.submission_file,
                    submissions.marks,
                    submissions.ai_summary
                FROM submissions
                JOIN users ON submissions.student_id = users.id
                JOIN assignments ON submissions.assignment_id = assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                WHERE semesters.id = ?
                ORDER BY submissions.submission_time DESC
                """, conn, params=(sem_id,))
        else:
            df = pd.DataFrame()

        if df.empty:
            st.info("No submissions yet.")
        else:
            # Display summary
            st.dataframe(
                df[["semester", "subject", "assignment", "username", "full_name", "submission_time", "marks"]],
                use_container_width=True,
                hide_index=True
            )
            st.divider()
            st.subheader("AI Grading Tool")

            rubric = st.text_area("Enter Model Answer / Rubric for AI Grading (applies to all below)", height=150)
            
            for _, row in df.iterrows():
                expander_title = "{} - {} ({})".format(row['username'], row['assignment'], row['subject'])
                
                with st.expander(expander_title):
                    col1, col2 = st.columns([2, 1])

                    with col1:
                        st.write("**Student:** {} ({})".format(row['full_name'], row['username']))
                        st.write("**Semester:** {}".format(row['semester']))
                        st.write("**Subject:** {}".format(row['subject']))
                        st.write("**Assignment:** {}".format(row['assignment']))
                        st.write("**Submitted:** {}".format(row['submission_time']))

                        if row['marks'] and str(row['marks']).strip():
                            st.metric("Current Marks", "{}/10".format(row['marks']))
                        else:
                            st.info("Not graded yet")

                    with col2:
                        if row["submission_file"] and os.path.exists(row["submission_file"]):
                            with open(row["submission_file"], "rb") as f:
                                st.download_button(
                                    "Download Submission", 
                                    f,
                                    file_name=os.path.basename(row["submission_file"]),
                                    key="dl_{}".format(row['id'])
                                )
                    
                    st.divider()

                    # AI Grading 
                    if row["submission_file"] and os.path.exists(row["submission_file"]):
                        col_a, col_b = st.columns(2)
                            
                        with col_a:
                            if st.button("AI Grade", key="grade_{}".format(row['id'])):
                                if not rubric.strip():
                                    st.warning("Please enter a rubric/model answer first")
                                else:
                                    with st.spinner("AI is grading..."):
                                        try:
                                            result = vision_grade(row["submission_file"], rubric)
                                            with st.expander("**AI Response:**", expanded= True):
                                                st.write(result)

                                            #check if result contains error
                                            if result and "Error" not in str(result):
                                                marks = extract_marks(result)
                                                
                                                if marks is not None:
                                                    c.execute(
                                                        "UPDATE submissions SET marks=?, ai_summary=? WHERE id=?",
                                                        (marks, result, row["id"])
                                                    )
                                                    conn.commit()
                                                    st.success("Updated marks: {}/10".format(marks))
                                                    st.rerun()
                                                else:
                                                    st.warning("Could not extract marks from AI response.Please enter manually below")
                                                    st.info("Tip: Make sure AI response contains 'FINAL_MARKS: X/10'")
                                                    #still save the AI summary even if marks extraction failed
                                                    c. execute(
                                                        "UPDATE submissions SER ai_summary=? WHERE id=?",
                                                        (str(result), int(row["id"]))
                                                    )
                                                    conn.commit()
                                            else:
                                                st.error("AI returned an error. Check the response above.")
                                        except Exception as e:
                                            st.error("Error during AI grading: {}".format(str(e)))
                                            import traceback 
                                            st.code(traceback.format_exc())
                        
                        with col_b:
                            # Manual grade override
                            default_marks = 0
                            if row['marks'] and str(row['marks']).strip():
                                try:
                                    default_marks = int(row['marks'])
                                except:
                                    default_marks = 0
                            
                            manual_marks = st.number_input(
                                "Or enter marks manually",
                                min_value=0,
                                max_value=10,
                                value=default_marks,
                                key="manual_{}".format(row['id'])
                            )
                            if st.button("Save Manual Marks", key="save_{}".format(row['id'])):
                                c.execute(
                                    "UPDATE submissions SET marks=? WHERE id=?",
                                    (manual_marks, row["id"])
                                )
                                conn.commit()
                                st.success("Marks updated to {}/10".format(manual_marks))
                                st.rerun()
                    
                    # Show previous AI summary if exists
                    if row['ai_summary'] and str(row['ai_summary']).strip():
                        with st.expander("Previous AI Feedback"):
                            st.write(row['ai_summary'])

        # ANALYTICS
    with tabs[5]:  # Adjust index if needed
        
        st.title("📈 Performance Analytics")
        
        st.subheader("📊 Grade Statistics")
        
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not sems.empty:
            selected_sem = st.selectbox("Select Semester", ["All"] + sems["name"].tolist(), key="analytics_sem")
            
            if selected_sem == "All":
                df = pd.read_sql_query("""
                SELECT 
                    semesters.name as Semester,
                    subjects.name as Subject,
                    assignments.title as Assignment,
                    users.full_name as Student_Name,
                    users.username as Username,
                    submissions.submission_time as Submission_Date,
                    assignments.deadline as Deadline,
                    submissions.marks as Marks,
                    submissions.ai_summary as AI_Feedback
                FROM submissions
                JOIN assignments ON submissions.assignment_id=assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                JOIN users ON submissions.student_id = users.id
                WHERE submissions.marks IS NOT NULL AND submissions.marks != ''
                ORDER BY semesters.name, subjects.name, assignments.title, users.full_name
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = pd.read_sql_query("""
                SELECT 
                    semesters.name as Semester,
                    subjects.name as Subject,
                    assignments.title as Assignment,
                    users.full_name as Student_Name,
                    users.username as Username,
                    submissions.submission_time as Submission_Date,
                    assignments.deadline as Deadline,
                    submissions.marks as Marks,
                    submissions.ai_summary as AI_Feedback
                FROM submissions
                JOIN assignments ON submissions.assignment_id=assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                JOIN users ON submissions.student_id = users.id
                WHERE semesters.id = ? AND submissions.marks IS NOT NULL AND submissions.marks != ''
                ORDER BY subjects.name, assignments.title, users.full_name
                """, conn, params=(sem_id,))

            if not df.empty:
                df["marks"] = pd.to_numeric(df["Marks"], errors="coerce")
                
                # ========== DOWNLOAD OPTIONS ==========
                st.subheader("📥 Download Grade Reports")
                
                col1, col2, col3 = st.columns(3)
                
                # Option 1: Detailed Report (with feedback)
                with col1:
                    csv_detailed = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📄 Detailed Report (with AI Feedback)",
                        data=csv_detailed,
                        file_name="Grades_Detailed_{}.csv".format(selected_sem),
                        mime='text/csv',
                        use_container_width=True
                    )
                
                # Option 2: Summary Report (without feedback)
                with col2:
                    df_summary = df[['Semester', 'Subject', 'Assignment', 'Student_Name', 'Username', 'Submission_Date', 'Deadline', 'Marks']]
                    csv_summary = df_summary.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📊 Summary Report (No Feedback)",
                        data=csv_summary,
                        file_name="Grades_Summary_{}.csv".format(selected_sem),
                        mime='text/csv',
                        use_container_width=True
                    )
                
                # Option 3: Student-wise Aggregated Report
                with col3:
                    # Create pivot table: Students x Assignments
                    df_pivot = df.pivot_table(
                        index=['Semester', 'Student_Name', 'Username', 'Subject'],
                        columns='Assignment',
                        values='marks',
                        aggfunc='first'
                    ).reset_index()
                    
                    # Add average column
                    assignment_cols = [col for col in df_pivot.columns if col not in ['Semester', 'Student_Name', 'Username', 'Subject']]
                    df_pivot['Average'] = df_pivot[assignment_cols].mean(axis=1).round(2)
                    
                    csv_pivot = df_pivot.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📈 Student-wise Summary",
                        data=csv_pivot,
                        file_name="Grades_StudentWise_{}.csv".format(selected_sem),
                        mime='text/csv',
                        use_container_width=True
                    )
                
                st.divider()
                
                # ========== VISUALIZATIONS ==========
                st.subheader("📊 Average Marks by Assignment")
                avg_marks = df.groupby("Assignment")["marks"].mean()
                st.bar_chart(avg_marks)
                
                st.divider()
                
                # Metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Submissions", len(df))
                with col2:
                    st.metric("Average Score", "{:.2f}/10".format(df['marks'].mean()))
                with col3:
                    st.metric("Highest Score", "{}/10".format(df['marks'].max()))
                
                st.divider()
                
                # ========== SUBJECT-WISE BREAKDOWN ==========
                st.subheader("📚 Subject-wise Performance")
                
                subject_stats = df.groupby('Subject').agg({
                    'marks': ['count', 'mean', 'min', 'max']
                }).round(2)
                subject_stats.columns = ['Total Submissions', 'Average', 'Lowest', 'Highest']
                st.dataframe(subject_stats, use_container_width=True)
                
                st.divider()
                
                # ========== RAW DATA TABLE ==========
                st.subheader("📋 Detailed Grade Table")
                st.dataframe(
                    df[['Semester', 'Subject', 'Assignment', 'Student_Name', 'Username', 'Marks']],
                    use_container_width=True,
                    hide_index=True
                )
                
            else:
                st.info("📭 No graded submissions yet for this semester.")
        else:
            st.warning("⚠️ Please create semesters first.")

    # MANAGE STUDENTS
    with tabs[6]:
        
        # TEMPORARY FIX BUTTON - Remove after fixing all students
        st.subheader("⚠️ Emergency Fix for Existing Students")
        
        if st.button("🔧 Fix ALL Students with NULL semester"):
            # Get first semester as default
            default_sem = pd.read_sql_query("SELECT id FROM semesters ORDER BY id ASC LIMIT 1", conn)
            
            if not default_sem.empty:
                default_sem_id = int(default_sem.iloc[0]['id'])
                
                # Update all students with NULL semester_id
                c.execute("""
                UPDATE users 
                SET semester_id = ? 
                WHERE role = 'student' AND semester_id IS NULL
                """, (default_sem_id,))
                
                conn.commit()
                
                affected = c.rowcount
                st.success("✅ Fixed {} students - assigned to semester_id {}".format(affected, default_sem_id))
                st.rerun()
            else:
                st.error("No semesters available to assign")
        
        st.divider()
        
        st.subheader("Add Student Manually")

        col1, col2 = st.columns(2)

        with col1:
            student_name = st.text_input("Full Name", key="student_name")
            username = st.text_input("Username", key="student_username")
            password = st.text_input("Password", type="password", key="student_password")

        with col2:
            sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

            if sems.empty:
                st.warning("Please create semesters first.")
            else:
                semester_name = st.selectbox("Assign Semester", sems["name"], key="student_semester")
                semester_id = int(sems[sems["name"] == semester_name]["id"].values[0])
                
                # Show what will be inserted
                st.info("Will assign semester_id: {}".format(semester_id))

                if st.button("Create Student"):

                    if not username or not password:
                        st.error("Username and password required.")
                    elif not student_name:
                        st.error("Full name is required.")
                    else:
                        try:
                            # Use explicit integer conversion
                            semester_id_to_insert = int(semester_id)
                            
                            st.write("DEBUG: Inserting with semester_id = {} (type: {})".format(
                                semester_id_to_insert, 
                                type(semester_id_to_insert)
                            ))
                            
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(?, ?, ?, ?, ?)
                            """, (
                                student_name.strip(),
                                username.strip(),
                                hash_password(password.strip()),
                                "student",
                                semester_id_to_insert
                            ))
                            conn.commit()
                            
                            # Verify insertion
                            verify = pd.read_sql_query(
                                "SELECT * FROM users WHERE username=?",
                                conn,
                                params=(username.strip(),)
                            )
                            
                            if not verify.empty:
                                st.success("✅ Student '{}' created!".format(username))
                                st.write("**Verification:** semester_id saved as: {}".format(verify.iloc[0]['semester_id']))
                                st.rerun()
                            else:
                                st.error("Student created but verification failed")
                                
                        except sqlite3.IntegrityError:
                            st.error("Username already exists.")
                        except Exception as e:
                            st.error("Error creating student: {}".format(str(e)))
                            import traceback
                            st.code(traceback.format_exc())

        st.divider()

        st.subheader("Bulk Upload Students via CSV")
        st.info("CSV format: name,username,password,semester")

        csv_file = st.file_uploader("Upload CSV", type=["csv"], key="student_csv")

        if csv_file:
            df_csv = pd.read_csv(csv_file)
            required_cols = {"name", "username", "password", "semester"}

            if not required_cols.issubset(df_csv.columns):
                st.error("CSV must contain columns: name, username, password, semester")
            else:
                if st.button("Upload Students"):
                    sems = pd.read_sql_query("SELECT * FROM semesters", conn)
                    success_count = 0
                    error_count = 0

                    for _, row in df_csv.iterrows():
                        sem_match = sems[sems["name"] == row["semester"]]

                        if sem_match.empty:
                            error_count += 1
                            continue

                        sem_id = int(sem_match["id"].values[0])

                        try:
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(?,?,?,?,?)
                            """, (
                                row["name"],
                                row["username"],
                                hash_password(str(row["password"])),
                                "student",
                                int(sem_id)
                            ))
                            success_count += 1
                        except:
                            error_count += 1
                            continue

                    conn.commit()
                    st.success("{} students uploaded successfully. {} failed.".format(success_count, error_count))
                    st.rerun()

                st.divider()
        st.subheader("📋 Registered Student List")

        # 1. Filter Dropdown for Sorting/Viewing
        all_sems_list = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        filter_col1, filter_col2 = st.columns([1, 2])
        
        with filter_col1:
            list_filter = st.selectbox("View Students by Semester", ["All"] + all_sems_list["name"].tolist(), key="view_filter")

        # 2. Build Query: Sorted by Semester, then Alphabetically by Name
        if list_filter == "All":
            students_df = pd.read_sql_query("""
                SELECT 
                    users.id as ID,
                    users.full_name as Name, 
                    users.username as Username, 
                    COALESCE(semesters.name, 'No Semester') as Semester
                FROM users 
                LEFT JOIN semesters ON users.semester_id = semesters.id 
                WHERE users.role='student' 
                ORDER BY semesters.name ASC, users.full_name ASC
            """, conn)
        else:
            students_df = pd.read_sql_query("""
                SELECT 
                    users.id as ID,
                    users.full_name as Name, 
                    users.username as Username, 
                    semesters.name as Semester
                FROM users 
                JOIN semesters ON users.semester_id = semesters.id 
                WHERE users.role='student' AND semesters.name = ?
                ORDER BY users.full_name ASC
            """, conn, params=(list_filter,))

        # 3. Display the List (hide ID column from view)
        if not students_df.empty:
            st.dataframe(
                students_df[['Name', 'Username', 'Semester']], 
                use_container_width=True, 
                hide_index=True
            )
            
            # Show total count
            st.info(f"📊 Total Students: **{len(students_df)}**")
        else:
            st.info("No students found.")

        # 4. DOWNLOAD STUDENT LIST AS CSV
        if not students_df.empty:
            csv_students = students_df[['Name', 'Username', 'Semester']].to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download {list_filter} Student List (CSV)",
                data=csv_students,
                file_name=f"Students_{list_filter}.csv",
                mime='text/csv',
                use_container_width=True
            )

        st.divider()
        st.subheader("🗑️ Delete Student")

        # Create options list for deletion based on current filtered view
        if not students_df.empty:
            # Use ID as the unique key for deletion
            student_options = {
                "{} | {} | {}".format(
                    row['Semester'] if row['Semester'] else 'No Semester', 
                    row['Username'], 
                    row['Name']
                ): row['ID']
                for _, row in students_df.iterrows()
            }

            selected_student = st.selectbox(
                "Select Student to Remove",
                list(student_options.keys()),
                key="delete_student_select"
            )

            col_del1, col_del2 = st.columns([1, 3])
            
            with col_del1:
                if st.button("🗑️ Confirm Delete", type="primary", use_container_width=True):
                    student_id = student_options[selected_student]
                    
                    try:
                        # Delete submissions first (foreign key constraint)
                        c.execute("DELETE FROM submissions WHERE student_id=?", (int(student_id),))
                        # Then delete user
                        c.execute("DELETE FROM users WHERE id=?", (int(student_id),))
                        conn.commit()
                        
                        st.success("✅ Student removed successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error("Error deleting student: {}".format(str(e)))
            
            with col_del2:
                st.warning("⚠️ This action cannot be undone. All submissions will be deleted.")

        else:
            st.info("No students to delete.")

        st.divider()
        st.subheader("🔧 Update Student Semester Assignment")

        # Get all students for semester update
        all_students = pd.read_sql_query("""
        SELECT id, username, full_name, semester_id 
        FROM users 
        WHERE role='student'
        ORDER BY username ASC
        """, conn)

        if not all_students.empty:
            student_update_options = {
                "{} ({})".format(row['username'], row['full_name']): row['id']
                for _, row in all_students.iterrows()
            }
            
            col_update1, col_update2 = st.columns(2)
            
            with col_update1:
                selected_student_update = st.selectbox(
                    "Select Student",
                    list(student_update_options.keys()),
                    key="update_student_select"
                )
            
            with col_update2:
                sems_update = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
                
                if not sems_update.empty:
                    new_semester = st.selectbox(
                        "Assign to Semester",
                        sems_update["name"].tolist(),
                        key="update_semester_select"
                    )
                    
                    if st.button("💾 Update Semester Assignment", use_container_width=True):
                        student_id_update = student_update_options[selected_student_update]
                        new_sem_id = int(sems_update[sems_update["name"] == new_semester]["id"].values[0])
                        
                        try:
                            c.execute(
                                "UPDATE users SET semester_id=? WHERE id=?",
                                (int(new_sem_id), int(student_id_update))
                            )
                            conn.commit()
                            
                            st.success("✅ Student assigned to {} successfully!".format(new_semester))
                            st.rerun()
                            
                        except Exception as e:
                            st.error("Error updating: {}".format(str(e)))
                else:
                    st.warning("No semesters available. Please create semesters first.")
        else:
            st.info("No students to update.")
            
    # STUDY MATERIALS
    with tabs[7]:
        
        st.title("📚 Study Materials Management")
        
        # ========== UPLOAD NEW MATERIAL ==========
        st.subheader("📤 Upload New Study Material")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Select Semester
            sems_material = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            
            if sems_material.empty:
                st.warning("Please create semesters first.")
            else:
                material_semester = st.selectbox("Select Semester", sems_material["name"], key="material_semester")
                material_sem_id = int(sems_material[sems_material["name"] == material_semester]["id"].values[0])
                
                # Get subjects for selected semester
                subjects_material = pd.read_sql_query(
                    "SELECT * FROM subjects WHERE semester_id=?",
                    conn,
                    params=(material_sem_id,)
                )
                
                if subjects_material.empty:
                    st.warning("No subjects found for this semester. Please create subjects first.")
                    material_subject_id = None
                else:
                    material_subject = st.selectbox(
                        "Select Subject", 
                        subjects_material["name"], 
                        key="material_subject"
                    )
                    material_subject_id = int(subjects_material[subjects_material["name"] == material_subject]["id"].values[0])
        
        with col2:
            material_title = st.text_input("Material Title", placeholder="e.g., Chapter 3 - Structural Analysis")
            material_description = st.text_area("Description (Optional)", placeholder="Brief description of the material...")
        
        # File Upload
        uploaded_file = st.file_uploader(
            "Upload Study Material (PDF, DOCX, PPTX, ZIP)",
            type=["pdf", "docx", "pptx", "zip", "jpg", "png"],
            key="study_material_upload"
        )
        
        if st.button("📤 Upload Material", type="primary", use_container_width=True):
            
            if not material_title.strip():
                st.error("⚠️ Please enter a title for the material.")
            elif not uploaded_file:
                st.error("⚠️ Please select a file to upload.")
            elif material_subject_id is None:
                st.error("⚠️ Please select a subject.")
            else:
                try:
                    # Save file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_extension = uploaded_file.name.split(".")[-1]
                    file_path = "study_materials/{}_{}.{}".format(
                        timestamp,
                        material_title.replace(" ", "_"),
                        file_extension
                    )
                    
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    if file_extension.lower() == "pdf":
                        apply_watermark(file_path)
                    
                    # Save to database
                    c.execute("""
                    INSERT INTO study_materials(
                        title, 
                        subject_id, 
                        semester_id, 
                        file_path, 
                        description, 
                        upload_date, 
                        uploaded_by
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """, (
                        material_title.strip(),
                        int(material_subject_id),
                        int(material_sem_id),
                        file_path,
                        material_description.strip(),
                        str(datetime.now()),
                        int(st.session_state.user_id)
                    ))
                    
                    conn.commit()
                    st.success("✅ Study material uploaded successfully!")
                    st.balloons()
                    st.rerun()
                    
                except Exception as e:
                    st.error("Error uploading material: {}".format(str(e)))
        
        st.divider()
        
        # ========== VIEW/MANAGE MATERIALS ==========
        st.subheader("📋 Uploaded Study Materials")
        
        # Filter by semester
        filter_sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not filter_sems.empty:
            filter_semester = st.selectbox(
                "Filter by Semester", 
                ["All"] + filter_sems["name"].tolist(), 
                key="filter_materials_sem"
            )
            
            # Query materials
            if filter_semester == "All":
                materials_df = pd.read_sql_query("""
                SELECT 
                    study_materials.id,
                    study_materials.title,
                    subjects.name as subject,
                    semesters.name as semester,
                    study_materials.description,
                    study_materials.file_path,
                    study_materials.upload_date
                FROM study_materials
                JOIN subjects ON study_materials.subject_id = subjects.id
                JOIN semesters ON study_materials.semester_id = semesters.id
                ORDER BY study_materials.upload_date DESC
                """, conn)
            else:
                filter_sem_id = int(filter_sems[filter_sems["name"] == filter_semester]["id"].values[0])
                materials_df = pd.read_sql_query("""
                SELECT 
                    study_materials.id,
                    study_materials.title,
                    subjects.name as subject,
                    semesters.name as semester,
                    study_materials.description,
                    study_materials.file_path,
                    study_materials.upload_date
                FROM study_materials
                JOIN subjects ON study_materials.subject_id = subjects.id
                JOIN semesters ON study_materials.semester_id = semesters.id
                WHERE study_materials.semester_id = ?
                ORDER BY study_materials.upload_date DESC
                """, conn, params=(filter_sem_id,))
            
            if materials_df.empty:
                st.info("📭 No study materials uploaded yet.")
            else:
                st.dataframe(
                    materials_df[["semester", "subject", "title", "upload_date"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info("📊 Total Materials: **{}**".format(len(materials_df)))
                
                st.divider()
                
                # Individual material cards with download and delete
                st.subheader("📚 Material Details")
                
                for _, material in materials_df.iterrows():
                    with st.expander("📄 {} - {}".format(material['subject'], material['title'])):
                        
                        col_a, col_b = st.columns([3, 1])
                        
                        with col_a:
                            st.write("**Semester:** {}".format(material['semester']))
                            st.write("**Subject:** {}".format(material['subject']))
                            st.write("**Title:** {}".format(material['title']))
                            st.write("**Uploaded:** {}".format(material['upload_date']))
                            if material['description']:
                                st.write("**Description:** {}".format(material['description']))
                        
                        with col_b:
                            # Download button
                            if material['file_path'] and os.path.exists(material['file_path']):
                                with open(material['file_path'], "rb") as f:
                                    st.download_button(
                                        "📥 Download",
                                        f,
                                        file_name=os.path.basename(material['file_path']),
                                        key="download_material_{}".format(material['id']),
                                        use_container_width=True
                                    )
                            
                            # Delete button
                            if st.button("🗑️ Delete", key="delete_material_{}".format(material['id']), use_container_width=True):
                                try:
                                    # Delete file
                                    if os.path.exists(material['file_path']):
                                        os.remove(material['file_path'])
                                    
                                    # Delete from database
                                    c.execute("DELETE FROM study_materials WHERE id=?", (material['id'],))
                                    conn.commit()
                                    
                                    st.success("✅ Material deleted!")
                                    st.rerun()
                                except Exception as e:
                                    st.error("Error deleting: {}".format(str(e)))
# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs = st.tabs(["Assignments","Study Materials", "My Results"])

        # ================= ASSIGNMENTS =================
    with tabs[0]:

        st.title("📝 My Assignments")

        # Get student's semester
        student_info = pd.read_sql_query(
            "SELECT semester_id, username FROM users WHERE id=?",
            conn,
            params=(int(st.session_state.user_id),)
        )

        if student_info.empty:
            st.error("Student record not found.")
            st.stop()

        sem_id_raw = student_info.iloc[0]["semester_id"]

        if sem_id_raw is None or str(sem_id_raw).strip() == "":
            st.warning("You are not assigned to a semester. Please Contact your Lecturer")
            st.stop()

        sem_id = int(sem_id_raw)

        # Get semester name
        semester_info = pd.read_sql_query(
            "SELECT name FROM semesters WHERE id=?",
            conn,
            params=(sem_id,)
        )
        
        if not semester_info.empty:
            st.info("📚 Semester: **{}**".format(semester_info.iloc[0]['name']))
        
        # ========== DEADLINE REMINDER DASHBOARD ==========
        st.subheader("⏰ Deadline Reminders")
        
        # Get all assignments for student's semester
        all_assignments = pd.read_sql_query("""
        SELECT 
            assignments.id,
            assignments.title,
            assignments.deadline,
            subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=?
        ORDER BY assignments.deadline ASC
        """, conn, params=(sem_id,))
        
        if not all_assignments.empty:
            # Check submission status
            overdue = []
            due_today = []
            due_soon = []
            upcoming = []
            completed = []
            
            for _, assignment in all_assignments.iterrows():
                # Check if submitted
                submission = pd.read_sql_query("""
                SELECT id FROM submissions
                WHERE assignment_id=? AND student_id=?
                """, conn, params=(int(assignment['id']), int(st.session_state.user_id)))
                
                days, status, color = get_deadline_status(assignment['deadline'])
                
                assignment_info = {
                    'id': assignment['id'],
                    'title': assignment['title'],
                    'subject': assignment['subject'],
                    'deadline': assignment['deadline'],
                    'days': days,
                    'status': status,
                    'color': color
                }
                
                if not submission.empty:
                    completed.append(assignment_info)
                elif status == "Overdue":
                    overdue.append(assignment_info)
                elif status == "Due Today":
                    due_today.append(assignment_info)
                elif status == "Due Soon":
                    due_soon.append(assignment_info)
                else:
                    upcoming.append(assignment_info)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🔴 Overdue", len(overdue))
            with col2:
                st.metric("🟠 Due Today", len(due_today))
            with col3:
                st.metric("🟡 Due Soon", len(due_soon))
            with col4:
                st.metric("✅ Completed", len(completed))
            
            st.divider()
            
            # Show overdue assignments (if any)
            if overdue:
                st.error("🔴 **OVERDUE ASSIGNMENTS - Submit Immediately!**")
                for assign in overdue:
                    st.warning("⚠️ **{}** - {} (Overdue by {} days)".format(
                        assign['subject'],
                        assign['title'],
                        abs(assign['days'])
                    ))
            
            # Show due today (if any)
            if due_today:
                st.warning("🟠 **DUE TODAY - Last Chance!**")
                for assign in due_today:
                    st.info("⏰ **{}** - {}".format(assign['subject'], assign['title']))
            
            # Show due soon (if any)
            if due_soon:
                st.info("🟡 **DUE SOON - Complete These First!**")
                for assign in due_soon:
                    st.write("📌 **{}** - {} ({} days left)".format(
                        assign['subject'],
                        assign['title'],
                        assign['days']
                    ))
            
            st.divider()
        
        # ========== ASSIGNMENT LIST WITH STATUS ==========
        st.subheader("📋 All Assignments")
        
        # Get assignments for student's semester
        assignments = pd.read_sql_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=?
        ORDER BY assignments.deadline ASC
        """, conn, params=(sem_id,))

        if assignments.empty:
            st.info("📭 No assignments available for your semester.")
        else:
            for index, row in assignments.iterrows():
                
                # Check submission status
                existing_submission = pd.read_sql_query("""
                SELECT * FROM submissions
                WHERE assignment_id=? AND student_id=?
                """, conn, params=(int(row["id"]), int(st.session_state.user_id)))
                
                # Get deadline status
                deadline_display = format_deadline_display(row['deadline'])
                
                # Create expander title with status
                if not existing_submission.empty:
                    expander_title = "✅ {} - {} | {}".format(
                        row['subject'],
                        row['title'],
                        deadline_display
                    )
                else:
                    expander_title = "{} - {} | {}".format(
                        row['subject'],
                        row['title'],
                        deadline_display
                    )
                
                with st.expander(expander_title):

                    # DOWNLOAD ASSIGNMENT FILE
                    if row["question_file"] and os.path.exists(row["question_file"]):
                        with open(row["question_file"], "rb") as f:
                            st.download_button(
                                "📥 Download Assignment Question",
                                f,
                                file_name=os.path.basename(row["question_file"]),
                                key="download_q_{}".format(row['id'])
                            )
                    else:
                        st.info("No assignment file attached by lecturer.")

                    st.divider()

                    # CHECK IF ALREADY SUBMITTED
                    if not existing_submission.empty:
                        st.success("✅ You have already submitted this assignment.")

                        submission_time = existing_submission.iloc[0]["submission_time"]
                        st.write("**Submitted on:** {}".format(submission_time))

                        # Show marks if graded
                        marks = existing_submission.iloc[0]["marks"]
                        if marks and str(marks).strip():
                            st.metric("🎯 Marks Awarded", str(marks) + "/10")
                        else:
                            st.info("⏳ Not graded yet")

                        # Allow download of submitted file
                        submitted_file = existing_submission.iloc[0]["submission_file"]
                        if submitted_file and os.path.exists(submitted_file):
                            with open(submitted_file, "rb") as f:
                                st.download_button(
                                    "📥 Download My Submission",
                                    f,
                                    file_name=os.path.basename(submitted_file),
                                    key="download_sub_{}".format(row['id'])
                                )

                    else:
                        # Show deadline warning
                        days, status, color = get_deadline_status(row['deadline'])
                        
                        if status == "Overdue":
                            st.error("🔴 **This assignment is OVERDUE by {} days!**".format(abs(days)))
                        elif status == "Due Today":
                            st.warning("🟠 **This assignment is DUE TODAY!**")
                        elif status == "Due Soon":
                            st.info("🟡 **Only {} days left to submit!**".format(days))
                        
                        # UPLOAD NEW SUBMISSION
                        uploaded = st.file_uploader(
                            "📤 Upload Your Answer PDF",
                            type=["pdf"],
                            key="upload_{}".format(row['id'])
                        )

                        if st.button("Submit Assignment", key="submit_{}".format(row['id']), type="primary"):

                            if not uploaded:
                                st.warning("⚠️ Please upload a PDF file before submitting.")
                            else:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                file_path = "submission_files/" + str(st.session_state.username) + "_" + str(row['id']) + "_" + timestamp + ".pdf"

                                with open(file_path, "wb") as f:
                                    f.write(uploaded.getbuffer())

                                c.execute("""
                                INSERT INTO submissions(
                                    assignment_id,
                                    student_id,
                                    submission_time,
                                    submission_file,
                                    marks,
                                    ai_summary
                                )
                                VALUES(?,?,?,?,?,?)
                                """, (
                                    int(row["id"]),
                                    int(st.session_state.user_id),
                                    str(datetime.now()),
                                    file_path,
                                    "",
                                    ""
                                ))

                                conn.commit()
                                
                                # Check if submitted on time
                                if days >= 0:
                                    st.success("✅ Assignment submitted successfully on time!")
                                else:
                                    st.warning("⚠️ Assignment submitted {} days late.".format(abs(days)))
                                
                                st.balloons()
                                st.rerun()

        # ================= STUDY MATERIALS =================
    with tabs[1]:
        
        st.title("📚 Study Materials")
        
        # Get student's semester
        student_info = pd.read_sql_query(
            "SELECT semester_id FROM users WHERE id=?",
            conn,
            params=(int(st.session_state.user_id),)
        )
        
        if student_info.empty or student_info.iloc[0]["semester_id"] is None:
            st.warning("⚠️ You are not assigned to a semester. Please contact your lecturer.")
        else:
            sem_id = int(student_info.iloc[0]["semester_id"])
            
            # Get semester name
            semester_info = pd.read_sql_query(
                "SELECT name FROM semesters WHERE id=?",
                conn,
                params=(sem_id,)
            )
            
            if not semester_info.empty:
                st.info("📚 Study Materials for: **{}**".format(semester_info.iloc[0]['name']))
            
            # Get all materials for student's semester
            materials = pd.read_sql_query("""
            SELECT 
                study_materials.id,
                study_materials.title,
                subjects.name as subject,
                study_materials.description,
                study_materials.file_path,
                study_materials.upload_date
            FROM study_materials
            JOIN subjects ON study_materials.subject_id = subjects.id
            WHERE study_materials.semester_id = ?
            ORDER BY subjects.name ASC, study_materials.upload_date DESC
            """, conn, params=(sem_id,))
            
            if materials.empty:
                st.info("📭 No study materials available yet.")
            else:
                # Group by subject
                subjects_list = materials['subject'].unique()
                
                for subject in subjects_list:
                    st.subheader("📖 {}".format(subject))
                    
                    subject_materials = materials[materials['subject'] == subject]
                    
                    for _, material in subject_materials.iterrows():
                        with st.expander("📄 {}".format(material['title'])):
                            
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write("**Subject:** {}".format(material['subject']))
                                st.write("**Uploaded:** {}".format(material['upload_date']))
                                if material['description']:
                                    st.write("**Description:**")
                                    st.info(material['description'])
                            
                            with col2:
                                # Download button
                                if material['file_path'] and os.path.exists(material['file_path']):
                                    with open(material['file_path'], "rb") as f:
                                        st.download_button(
                                            "📥 Download",
                                            f,
                                            file_name=os.path.basename(material['file_path']),
                                            key="student_download_{}".format(material['id']),
                                            use_container_width=True,
                                            type="primary"
                                        )
                                else:
                                    st.error("File not found")
                    
                    st.divider()

    # ================= RESULTS =================
    with tabs[2]:  # ← Changed from tabs[1] to tabs[2]
        
        results = pd.read_sql_query("""
        SELECT subjects.name as Subject, assignments.title, submissions.marks
        FROM submissions
        JOIN assignments ON submissions.assignment_id = assignments.id
        JOIN subjects ON assignment.subject_id = subjects.id
        WHERE submissions.student_id=?
        ORDER BY submissions.id DESC
        """, conn, params=(int(st.session_state.user_id,)))

        if results.empty:
            st.info("No results available yet.")
        else:
            st.dataframe(results, use_container_width=True, hide_index=True)
