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

# ================= CONFIG =================

st.set_page_config(
    page_title="water flows by Nirajan Katuwal",
    page_icon="🏗️",
    layout="wide"
)



# ================= FOLDERS =================

os.makedirs("data", exist_ok=True)
os.makedirs("assignment_files", exist_ok=True)
os.makedirs("submission_files", exist_ok=True)

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

    st.title("🏗️ Civil Engineering AI Platform")

    user = st.text_input("Username")
    pw = st.text_input("Password", type="password")

    if st.button("Login"):

        df = pd.read_sql_query(
            "SELECT * FROM users WHERE username=?",
            conn,
            params=(user,)
        )

        if not df.empty and check_password(pw, df.iloc[0]["password"]):
            st.session_state.logged_in = True
            st.session_state.user_id = df.iloc[0]["id"]
            st.session_state.role = df.iloc[0]["role"]
            st.session_state.username = df.iloc[0]["username"]
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

# ================= LOGOUT =================

st.sidebar.write(f"👤 {st.session_state.username} ({st.session_state.role})")

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

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
    

# ==========================================================
# ===================== LECTURER ============================
# ==========================================================

if role == "lecturer":

    tabs = st.tabs([
        "Semesters",
        "Subjects",
        "Assignments",
        "Submissions & AI",
        "Analytics",
        "Manage Students"
    ])

    # SEMESTERS
    with tabs[0]:
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
    with tabs[1]:
        
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            sem = st.selectbox("Semester", sems["name"], key="subject_semester")
            sem_id = int(sems[sems["name"] == sem]["id"].values[0])

            st.write("DEBUG selected semester id:", sem_id)
            
            sub = st.text_input("Subject Name", key="subject_name")
            
            if st.button("Add Subject"):
                if not sub.strip():
                    st.error("Subject name cannot be empty.")
                else:
                    try:
                        c.execute(
                            "INSERT INTO subjects(name,semester_id) VALUES(?,?)",
                            (sub.strip(), int(sem_id))
                        )
                        conn.commit()
                        st.success("Added")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error adding subject: {e}")
            st.divider()
            st.subheader("Subjects for Selected Semester")
            subjects_for_sem = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=?",
                conn,
                params=(int(sem_id),)
            )
                
            st.dataframe(
                pd.read_sql_query(
                    "SELECT * FROM subjects WHERE semester_id=?",
                    conn,
                    params=(sem_id,)
                ),
                use_container_width=True,
                hide_index=True
            )
            st.divider()
            st.subheader("All Subjects Debug")
            all_subjects_debug = pd.read_sql_query("SELECT * FROM subjects", conn)
            st.dataframe(all_subjects_debug, use_container_width=True, hide_index=True)

    # ASSIGNMENTS
    with tabs[2]:
        st.subheader("create New Assignment")

        sems = pd.read_sql_query("SELECT * FROM semesters ORDER by name ASC", conn)

        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            sem_name = st.selectbox("Select Semester", sems["name"], key="assign_sem")
            sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])

            subjects = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=?",
                conn,
                params=(sem_id,)
            )
            #TEMPORARY================
            st.write("DEBUG sem_id:", sem_id)
            st.write("DEBUG subjects returned:", subjects)
            st.write("DEBUG all subjects:", pd.read_sql_query("SELECT * FROM subjects", conn))

            if subjects.empty:
                st.warning("Please create a subject for this semester first.")
            else:
                subject_options = {
                    f"{row['name']} (ID:{row['id']})": row['id']
                    for _, row in subjects.iterrows()
                }

                selected_subject = st.selectbox("Select Subject", list(subject_options.keys()))
                sub_id = int(subject_options[selected_subject])

                title = st.text_input("Assignment Title")
                deadline = st.date_input("Deadline")
                file = st.file_uploader("Upload Assignment PDF", type=["pdf"])

                if st.button("Create Assignment"):

                    if not title.strip():
                        st.error("Title cannot be empty.")
                    else:
                        file_path = ""

                        if file:
                            file_path = f"assignment_files/{datetime.now().timestamp()}_{file.name}"
                            with open(file_path, "wb") as f:
                                f.write(file.getbuffer())

                        try:
                            c.execute("""
                            INSERT INTO assignments(title,subject_id,deadline,question_file)
                            VALUES(?,?,?,?)
                            """, (title.strip(), int(sub_id), str(deadline), file_path))

                            conn.commit()
                            st.success("✅ Assignment Created Successfully!")
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error: {e}")

        st.divider()
        st.subheader("Existing Assignments")

        all_assignments = pd.read_sql_query("""
            SELECT id, title, deadline, subject_id
            FROM assignments
            ORDER BY id DESC
        """, conn)

        if all_assignments.empty:
            st.info("No assignments created yet.")
        else:
            st.dataframe(all_assignments, use_container_width=True, hide_index=True)

    # SUBMISSIONS & AI
    with tabs[3]:

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
    with tabs[4]:
        
        st.subheader("Performance Analytics")
        
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not sems.empty:
            selected_sem = st.selectbox("Select Semester", ["All"] + sems["name"].tolist(), key="analytics_sem")
            
            if selected_sem == "All":
                df = pd.read_sql_query("""
                SELECT assignments.title, submissions.marks, subjects.name as subject
                FROM submissions
                JOIN assignments ON submissions.assignment_id=assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                WHERE submissions.marks IS NOT NULL AND submissions.marks != ''
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = pd.read_sql_query("""
                SELECT assignments.title, submissions.marks, subjects.name as subject
                FROM submissions
                JOIN assignments ON submissions.assignment_id=assignments.id
                JOIN subjects ON assignments.subject_id = subjects.id
                JOIN semesters ON subjects.semester_id = semesters.id
                WHERE semesters.id = ? AND submissions.marks IS NOT NULL AND submissions.marks != ''
                """, conn, params=(sem_id,))

            if not df.empty:
                df["marks"] = pd.to_numeric(df["marks"], errors="coerce")
                
                st.subheader("Average Marks by Assignment")
                avg_marks = df.groupby("title")["marks"].mean()
                st.bar_chart(avg_marks)
                
                st.divider()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Submissions", len(df))
                with col2:
                    st.metric("Average Score", "{:.2f}/10".format(df['marks'].mean()))
                with col3:
                    st.metric("Highest Score", "{}/10".format(df['marks'].max()))
                
                st.divider()
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No graded submissions yet for this semester.")

    # MANAGE STUDENTS
    with tabs[5]:
        
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

        st.subheader("Student List")

        # Enhanced query to debug
        students = pd.read_sql_query("""
        SELECT users.id, users.full_name, users.username, users.semester_id, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student'
        ORDER BY users.id DESC
        """, conn)

        if students.empty:
            st.info("No students added yet.")
        else:
            # Show ALL columns including semester_id for debugging
            st.dataframe(
                students,
                use_container_width=True,
                hide_index=True
            )
            
            # Show raw database data
            with st.expander("🔍 Debug: Raw Database Data"):
                raw_users = pd.read_sql_query("""
                SELECT id, username, full_name, semester_id, role 
                FROM users 
                WHERE role='student'
                ORDER BY id DESC
                """, conn)
                st.write("**Users table (students only):**")
                st.dataframe(raw_users, use_container_width=True, hide_index=True)
                
                all_semesters = pd.read_sql_query("SELECT * FROM semesters", conn)
                st.write("**Semesters table:**")
                st.dataframe(all_semesters, use_container_width=True, hide_index=True)

            student_options = {
                "{} | {} | {}".format(
                    row['semester'] if row['semester'] else 'NO SEMESTER', 
                    row['username'], 
                    row['full_name']
                ): row['id']
                for _, row in students.iterrows()
            }

            selected_student = st.selectbox(
                "Select Student to Delete",
                list(student_options.keys()),
                key="delete_student_select"
            )

            if st.button("Delete Selected Student"):
                student_id = student_options[selected_student]
                c.execute("DELETE FROM submissions WHERE student_id=?", (student_id,))
                c.execute("DELETE FROM users WHERE id=?", (student_id,))
                conn.commit()
                st.success("Student deleted successfully.")
                st.rerun()
        
        st.divider()
        st.subheader("🔧 Fix Student Semester Assignment")

        # Get all students
        all_students = pd.read_sql_query("""
        SELECT id, username, full_name, semester_id 
        FROM users 
        WHERE role='student'
        ORDER BY username ASC
        """, conn)

        if not all_students.empty:
            student_options_fix = {
                "{} ({})".format(row['username'], row['full_name']): row['id']
                for _, row in all_students.iterrows()
            }
            
            selected_student_fix = st.selectbox(
                "Select Student to Update",
                list(student_options_fix.keys()),
                key="fix_student_select"
            )
            
            sems_fix = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            
            if not sems_fix.empty:
                semester_to_assign = st.selectbox(
                    "Assign to Semester",
                    sems_fix["name"].tolist(),
                    key="fix_semester_select"
                )
                
                if st.button("Update Student Semester", key="update_semester_btn"):
                    student_id_to_fix = student_options_fix[selected_student_fix]
                    new_sem_id = int(sems_fix[sems_fix["name"] == semester_to_assign]["id"].values[0])
                    
                    try:
                        c.execute(
                            "UPDATE users SET semester_id=? WHERE id=?",
                            (int(new_sem_id), int(student_id_to_fix))
                        )
                        conn.commit()
                        
                        # Verify the update
                        verify = pd.read_sql_query(
                            "SELECT semester_id FROM users WHERE id=?",
                            conn,
                            params=(int(student_id_to_fix),)
                        )
                        
                        st.success("✅ Student updated! New semester_id: {}".format(verify.iloc[0]['semester_id']))
                        st.rerun()
                    except Exception as e:
                        st.error("Error updating: {}".format(str(e)))

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs = st.tabs(["Assignments", "My Results"])

    # ================= ASSIGNMENTS =================
    with tabs[0]:

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

        # Debug - Remove after fixing 
        st.write("DEBUG: Your user_id = {}".format(st.session_state.user_id))
        st.write("DEBUG: Your semester_id = {} (type: {})".format(sem_id_raw, type(sem_id_raw)))

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
            st.info("You are enrolled in: **{}**".format(semester_info.iloc[0]['name']))
            
        # Get assignments for student's semester
        assignments = pd.read_sql_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=?
        ORDER BY assignments.deadline ASC
        """, conn, params=(sem_id,))

        # Debug - remove after fixing
        st.write("DEBUG: Found {} assignments for semester {}".format(len(assignments), sem_id))

        if assignments.empty:
            st.info("No assignments available for your semester.")
        else:
            for index, row in assignments.iterrows():
                # Safe string creation to avoid any SyntaxErrors
                expander_title = str(row['subject']) + " - " + str(row['title']) + " (Due: " + str(row['deadline']) + ")"

                with st.expander(expander_title):

                    # DOWNLOAD ASSIGNMENT FILE
                    if row["question_file"] and os.path.exists(row["question_file"]):
                        with open(row["question_file"], "rb") as f:
                            st.download_button(
                                "Download Assignment",
                                f,
                                file_name=os.path.basename(row["question_file"]),
                                key="download_q_{}".format(row['id'])
                            )
                    else:
                        st.info("No assignment file attached by lecturer.")

                    st.divider()

                    # CHECK IF ALREADY SUBMITTED
                    existing_submission = pd.read_sql_query("""
                    SELECT * FROM submissions
                    WHERE assignment_id=? AND student_id=?
                    """, conn, params=(int(row["id"]), int(st.session_state.user_id)))

                    if not existing_submission.empty:
                        st.success("You have already submitted this assignment.")

                        submission_time = existing_submission.iloc[0]["submission_time"]
                        st.write("**Submitted on:** {}".format(submission_time))

                        # Show marks if graded
                        marks = existing_submission.iloc[0]["marks"]
                        if marks and str(marks).strip():
                            st.metric("Marks Awarded", str(marks) + "/10")
                        else:
                            st.info("Not graded yet")

                        # Allow download of submitted file
                        submitted_file = existing_submission.iloc[0]["submission_file"]
                        if submitted_file and os.path.exists(submitted_file):
                            with open(submitted_file, "rb") as f:
                                st.download_button(
                                    "Download My Submission",
                                    f,
                                    file_name=os.path.basename(submitted_file),
                                    key="download_sub_{}".format(row['id'])
                                )

                    else:
                        # UPLOAD NEW SUBMISSION
                        uploaded = st.file_uploader(
                            "Upload Your PDF",
                            type=["pdf"],
                            key="upload_{}".format(row['id'])
                        )

                        if st.button("Submit Assignment", key="submit_{}".format(row['id'])):

                            if not uploaded:
                                st.warning("Please upload a PDF file before submitting.")
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
                                st.success("Assignment submitted successfully.")
                                st.balloons()
                                st.rerun()

    # ================= RESULTS =================
    with tabs[1]:

        results = pd.read_sql_query("""
        SELECT assignments.title, submissions.marks
        FROM submissions
        JOIN assignments ON submissions.assignment_id = assignments.id
        WHERE submissions.student_id=?
        ORDER BY submissions.id DESC
        """, conn, params=(st.session_state.user_id,))

        if results.empty:
            st.info("No results available yet.")
        else:
            st.dataframe(results, use_container_width=True, hide_index=True)
