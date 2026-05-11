
import streamlit as st
import pandas as pd
import psycopg2
import subprocess
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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ================= CONFIG =================

st.set_page_config(
    page_title="The N-streamlines",
    page_icon="🌊",
    layout="wide"
)
# ================= MOBILE RESPONSIVENESS =================

st.markdown("""
<style>
    /* Mobile optimizations */
    @media (max-width: 768px) {
        .block-container {
            padding: 1rem 1rem 5rem 1rem !important;
        }
        
        .stButton>button {
            width: 100%;
        }
        
        .stDataFrame {
            font-size: 12px;
        }
        
        h1 {
            font-size: 1.5rem !important;
        }
        
        h2 {
            font-size: 1.3rem !important;
        }
        
        h3 {
            font-size: 1.1rem !important;
        }
    }
    
    /* Improve button visibility */
    .stButton>button {
        font-weight: 500;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Better expander styling */
    .streamlit-expanderHeader {
        background-color: #f0f2f6;
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Improve metric cards */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)
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
# Streamlit Cloud Secrets Compatibility
def get_db_credential(key, default):
    try:
        return st.secrets[key]
    except:
        return os.getenv(key, default)

DB_HOST = get_db_credential("DB_HOST", "localhost")
DB_PORT = get_db_credential("DB_PORT", "5432")
DB_NAME = get_db_credential("DB_NAME", "lecturer_db")
DB_USER = get_db_credential("DB_USER", "postgres")
DB_PASS = get_db_credential("DB_PASS", "postgres")

# Attempt Connection with SSL
try:
    conn = psycopg2.connect(
        DB_HOST = "your-actual-host-url.com",
        DB_PORT = "5432",
        DB_NAME = "your_db_name",
        DB_USER = "your_user",
        DB_PASS = "your_password,
        sslmode="require"  # <--- CRITICAL FOR CLOUD DATABASES
    )
    conn.autocommit = False
    c = conn.cursor()
except Exception as e:
    st.error(f"🚨 Database Connection Failed: {e}")
    st.info(f"Debug Info - Trying to connect to Host: {DB_HOST}")
    st.stop()

# USERS
c.execute("""
CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    full_name TEXT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT,
    semester_id INTEGER
)
""")
# Safe auto-migration for existing users table
try:
    c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.commit()
except:
    conn.rollback()
    pass # Column already exists

# SEMESTERS
c.execute("""
CREATE TABLE IF NOT EXISTS semesters(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
)
""")

# SUBJECTS
c.execute("""
CREATE TABLE IF NOT EXISTS subjects(
    id SERIAL PRIMARY KEY,
    name TEXT,
    semester_id INTEGER
)
""")

# ASSIGNMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS assignments(
    id SERIAL PRIMARY KEY,
    title TEXT,
    subject_id INTEGER,
    deadline TEXT,
    question_file TEXT,
    rubric TEXT
)
""")

# Safe auto-migration for existing databases
try:
    c.execute("ALTER TABLE assignments ADD COLUMN rubric TEXT")
    conn.commit()
except:
    conn.rollback()
    pass # Column already exists

# SUBMISSIONS
c.execute("""
CREATE TABLE IF NOT EXISTS submissions(
    id SERIAL PRIMARY KEY,
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
    id SERIAL PRIMARY KEY,
    title TEXT,
    subject_id INTEGER,
    semester_id INTEGER,
    file_path TEXT,
    description TEXT,
    upload_date TEXT,
    uploaded_by INTEGER
)
""")
# ANNOUNCEMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS announcements(
    id SERIAL PRIMARY KEY,
    title TEXT,
    message TEXT,
    semester_id INTEGER,
    created_by INTEGER,
    created_at TEXT,
    priority TEXT
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
    VALUES(%s,%s,%s,%s,%s)
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

# ================= SESSION SECURITY =================

# Session timeout in seconds (30 minutes)
SESSION_TIMEOUT = 1800

def check_session_timeout():
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()
        return True
    
    current_time = time.time()
    elapsed = current_time - st.session_state.last_activity
    
    if elapsed > SESSION_TIMEOUT:
        return False  # Session expired
    
    # Update last activity time
    st.session_state.last_activity = current_time
    return True


def require_login():
    if not st.session_state.get("logged_in", False):
        st.error("🔒 Please login to access this page")
        st.stop()
    
    if not check_session_timeout():
        st.warning("⏰ Your session has expired due to inactivity. Please login again.")
        st.session_state.clear()
        st.rerun()

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
                "SELECT * FROM users WHERE username=%s",
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

#check session timeout
require_login()

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
                tables = ["users", "submissions", "assignments", "subjects", "semesters", "study_materials", "announcements"]
                for t in tables: 
                    c.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
                conn.commit()
                st.rerun()

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

# ================= ANNOUNCEMENTS =================

def create_announcement(title, message, semester_id, priority, user_id):
    try:
        c.execute("""
        INSERT INTO announcements(title, message, semester_id, created_by, created_at, priority)
        VALUES(%s,%s,%s,%s,%s,%s)
        """, (
            title.strip(),
            message.strip(),
            int(semester_id) if semester_id else None,
            int(user_id),
            str(datetime.now()),
            priority
        ))
        
        conn.commit()
        return True, "Announcement created successfully"
    except Exception as e:
        conn.rollback()
        return False, "Error: {}".format(str(e))


def get_announcements_for_semester(semester_id=None):
    if semester_id:
        df = pd.read_sql_query("""
        SELECT announcements.*, users.full_name as author, semesters.name as semester
        FROM announcements
        LEFT JOIN users ON announcements.created_by = users.id
        LEFT JOIN semesters ON announcements.semester_id = semesters.id
        WHERE announcements.semester_id=%s OR announcements.semester_id IS NULL
        ORDER BY announcements.created_at DESC
        """, conn, params=(int(semester_id),))
    else:
        df = pd.read_sql_query("""
        SELECT announcements.*, users.full_name as author, semesters.name as semester
        FROM announcements
        LEFT JOIN users ON announcements.created_by = users.id
        LEFT JOIN semesters ON announcements.semester_id = semesters.id
        ORDER BY announcements.created_at DESC
        """, conn)
    
    return df

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
                if 0 <= marks <=10:
                    return marks
            except (ValueError, IndexError):
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

#===================PUSH Email===============================
def send_email_notification(target_semester_id, subject, message_body):
    if target_semester_id:
        df = pd.read_sql_query("SELECT email FROM users WHERE role='student' AND semester_id=%s AND email IS NOT NULL AND email != ''", conn, params=(int(target_semester_id),))
    else:
        df = pd.read_sql_query("SELECT email FROM users WHERE role='student' AND email IS NOT NULL AND email != ''", conn)
    
    emails = df['email'].tolist()
    if not emails:
        return False, "No valid student emails found."

    SENDER_EMAIL = "your_platform_email@gmail.com" 
    APP_PASSWORD = "your_16_digit_app_password"

    try:
        msg = MIMEMultipart()
        msg['From'] = f"The N-Streamlines <{SENDER_EMAIL}>"
        msg['Subject'] = subject
        msg.attach(MIMEText(message_body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        
        server.sendmail(SENDER_EMAIL, emails, msg.as_string())
        server.quit()
        return True, f"Emailed {len(emails)} students."
    except Exception as e:
        return False, f"Email error: {str(e)}"

# ================= DEADLINE HELPER FUNCTIONS =================

def get_deadline_status(deadline_str):
    from datetime import datetime, timedelta
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

# ================= FILE CLEANUP UTILITIES =================

def cleanup_orphaned_files():
    deleted_count = 0
    space_freed = 0
    db_files = set()
    
    assignments = pd.read_sql_query("SELECT question_file FROM assignments WHERE question_file IS NOT NULL AND question_file != ''", conn)
    for _, row in assignments.iterrows():
        if row['question_file']:
            db_files.add(row['question_file'])
    
    submissions = pd.read_sql_query("SELECT submission_file FROM submissions WHERE submission_file IS NOT NULL AND submission_file != ''", conn)
    for _, row in submissions.iterrows():
        if row['submission_file']:
            db_files.add(row['submission_file'])
    
    materials = pd.read_sql_query("SELECT file_path FROM study_materials WHERE file_path IS NOT NULL AND file_path != ''", conn)
    for _, row in materials.iterrows():
        if row['file_path']:
            db_files.add(row['file_path'])
    
    folders = ['assignment_files', 'submission_files', 'study_materials']
    
    for folder in folders:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if file_path not in db_files and os.path.isfile(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        space_freed += file_size
                    except Exception as e:
                        st.warning("Could not delete {}: {}".format(file_path, str(e)))
    
    space_freed_mb = space_freed / (1024 * 1024)
    return deleted_count, round(space_freed_mb, 2)

def get_storage_stats():
    stats = {}
    folders = {
        'assignment_files': 'Assignment Questions',
        'submission_files': 'Student Submissions',
        'study_materials': 'Study Materials',
        'data': 'Database Files'
    }
    
    for folder, label in folders.items():
        if os.path.exists(folder):
            total_size = 0
            file_count = 0
            for dirpath, dirnames, filenames in os.walk(folder):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.isfile(file_path):
                        try:
                            total_size += os.path.getsize(file_path)
                            file_count += 1
                        except:
                            continue
            stats[label] = {
                'size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count
            }
    return stats

# ================= FILE VALIDATION & SECURITY =================

MAX_FILE_SIZE_MB = 25
ALLOWED_ASSIGNMENT_TYPES = ['pdf']
ALLOWED_SUBMISSION_TYPES = ['pdf']
ALLOWED_MATERIAL_TYPES = ['pdf', 'docx', 'pptx', 'zip', 'jpg', 'png']

def validate_file_upload(uploaded_file, allowed_types, max_size_mb=MAX_FILE_SIZE_MB):
    if uploaded_file is None:
        return False, "No file uploaded"
    file_extension = uploaded_file.name.split('.')[-1].lower()
    if file_extension not in allowed_types:
        return False, "Invalid file type. Allowed: {}".format(', '.join(allowed_types))
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, "File too large! Maximum size: {} MB (Your file: {:.2f} MB)".format(max_size_mb, file_size_mb)
    if file_extension == 'pdf':
        uploaded_file.seek(0)
        header = uploaded_file.read(5)
        uploaded_file.seek(0)
        if header != b'%PDF-':
            return False, "File appears to be corrupted or not a valid PDF"
    return True, "File is valid"

def safe_file_operation(operation, *args, **kwargs):
    try:
        result = operation(*args, **kwargs)
        return True, result
    except PermissionError:
        return False, "Permission denied. File may be in use."
    except FileNotFoundError:
        return False, "File not found."
    except Exception as e:
        return False, "Error: {}".format(str(e))

def check_deadline_passed(deadline_str):
    try:
        deadline_date = datetime.strptime(str(deadline_str), '%Y-%m-%d').date()
        current_date = datetime.now().date()
        if current_date > deadline_date:
            days_late = (current_date - deadline_date).days
            return True, "Deadline passed {} days ago".format(days_late)
        else:
            return False, "Deadline not passed"
    except:
        return False, "Invalid deadline format"

# ================= DATABASE BACKUP SYSTEM (POSTGRESQL VERSION) =================

def create_database_backup():
    try:
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = "lecturer_backup_{}.sql".format(timestamp)
        backup_path = os.path.join(backup_dir, backup_filename)
        
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASS
        result = subprocess.run(
            ["pg_dump", "-U", DB_USER, "-h", DB_HOST, "-p", str(DB_PORT), "-d", DB_NAME, "-f", backup_path],
            env=env, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return False, "Backup failed: {}".format(result.stderr)
        
        backup_size = os.path.getsize(backup_path) / 1024
        cleanup_old_backups(backup_dir, keep_count=10)
        return True, "Backup created: {} ({:.2f} KB)".format(backup_filename, backup_size)
    except Exception as e:
        return False, "Backup failed: {}".format(str(e))

def cleanup_old_backups(backup_dir, keep_count=10):
    try:
        if not os.path.exists(backup_dir):
            return
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.startswith("lecturer_backup_") and filename.endswith(".sql"):
                file_path = os.path.join(backup_dir, filename)
                try:
                    mod_time = os.path.getmtime(file_path)
                    backups.append((file_path, mod_time))
                except:
                    continue
        backups.sort(key=lambda x: x[1], reverse=True)
        for file_path, _ in backups[keep_count:]:
            try:
                os.remove(file_path)
            except:
                pass
    except:
        pass

def restore_database_from_backup(backup_path):
    try:
        if not os.path.exists(backup_path):
            return False, "Backup file not found: {}".format(backup_path)
        
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASS
        result = subprocess.run(
            ["psql", "-U", DB_USER, "-h", DB_HOST, "-p", str(DB_PORT), "-d", DB_NAME, "-f", backup_path],
            env=env, capture_output=True, text=True
        )
        
        if result.returncode != 0:
            return False, "Restore failed: {}".format(result.stderr)
        
        return True, "✅ Database restored from backup. IMPORTANT: Please RESTART the app (refresh page) to reconnect to the restored database."
    except Exception as e:
        return False, "Restore error: {}".format(str(e))

def get_backup_list():
    backup_dir = "data/backups"
    backups = []
    if not os.path.exists(backup_dir):
        return backups
    for filename in os.listdir(backup_dir):
        if filename.startswith("lecturer_backup_") and filename.endswith(".sql"):
            file_path = os.path.join(backup_dir, filename)
            try:
                size_kb = os.path.getsize(file_path) / 1024
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                backups.append({
                    'filename': filename,
                    'path': file_path,
                    'size_kb': round(size_kb, 2),
                    'date': mod_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            except:
                continue
    backups.sort(key=lambda x: x['date'], reverse=True)
    return backups

# ================= SEARCH & UPDATE FUNCTIONS =================

def search_students(query, semester_id=None):
    query = query.strip().lower()
    if not query:
        return pd.DataFrame()
    
    if semester_id:
        results = pd.read_sql_query("""
        SELECT users.id, users.full_name, users.username, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student' 
        AND users.semester_id=%s
        AND (LOWER(users.full_name) LIKE %s OR LOWER(users.username) LIKE %s)
        ORDER BY users.full_name ASC
        """, conn, params=(semester_id, '%{}%'.format(query), '%{}%'.format(query)))
    else:
        results = pd.read_sql_query("""
        SELECT users.id, users.full_name, users.username, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student' 
        AND (LOWER(users.full_name) LIKE %s OR LOWER(users.username) LIKE %s)
        ORDER BY users.full_name ASC
        """, conn, params=('%{}%'.format(query), '%{}%'.format(query)))
    return results

def search_assignments(query):
    query = query.strip().lower()
    if not query:
        return pd.DataFrame()
    
    results = pd.read_sql_query("""
    SELECT 
        assignments.id,
        assignments.title,
        subjects.name as subject,
        semesters.name as semester,
        assignments.deadline
    FROM assignments
    JOIN subjects ON assignments.subject_id = subjects.id
    JOIN semesters ON subjects.semester_id = semesters.id
    WHERE LOWER(assignments.title) LIKE %s OR LOWER(subjects.name) LIKE %s
    ORDER BY assignments.deadline DESC
    """, conn, params=('%{}%'.format(query), '%{}%'.format(query)))
    return results

def update_assignment(assignment_id, new_title, new_deadline, new_rubric):
    try:
        c.execute("""
        UPDATE assignments 
        SET title=%s, deadline=%s, rubric=%s
        WHERE id=%s
        """, (new_title.strip(), str(new_deadline), new_rubric.strip(), int(assignment_id)))
        conn.commit()
        return True, "Assignment updated successfully"
    except Exception as e:
        conn.rollback()
        return False, "Update failed: {}".format(str(e))

def get_student_profile(student_id):
    try:
        student_info = pd.read_sql_query("""
        SELECT users.*, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.id=%s
        """, conn, params=(int(student_id),))
        
        if student_info.empty:
            return None
        
        submissions = pd.read_sql_query("""
        SELECT 
            subjects.name as subject,
            assignments.title as assignment,
            assignments.deadline,
            submissions.submission_time,
            submissions.marks
        FROM submissions
        JOIN assignments ON submissions.assignment_id = assignments.id
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE submissions.student_id=%s
        ORDER BY submissions.submission_time DESC
        """, conn, params=(int(student_id),))
        
        total_submissions = len(submissions)
        graded = submissions[submissions['marks'].notna() & (submissions['marks'] != '')]
        total_graded = len(graded)
        
        if total_graded > 0:
            graded['marks_numeric'] = pd.to_numeric(graded['marks'], errors='coerce')
            avg_marks = graded['marks_numeric'].mean()
            highest = graded['marks_numeric'].max()
            lowest = graded['marks_numeric'].min()
        else:
            avg_marks = 0
            highest = 0
            lowest = 0
        
        return {
            'info': student_info.iloc[0].to_dict(),
            'submissions': submissions,
            'stats': {
                'total_submissions': total_submissions,
                'total_graded': total_graded,
                'average': round(avg_marks, 2) if total_graded > 0 else 0,
                'highest': highest,
                'lowest': lowest
            }
        }
    except Exception as e:
        st.error("Error loading profile: {}".format(str(e)))
        return None

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
        "Study Materials",
        "Storage Management",
        "Student Profiles"
    ])
    
    # DASHBOARD
    with tabs[0]:
        st.title("📊 Dashboard")
        
        with st.expander("📢 Create New Announcement"):
            col_ann1, col_ann2 = st.columns([2, 1])
            with col_ann1:
                ann_title = st.text_input("Announcement Title", key="ann_title")
                ann_message = st.text_area("Message", key="ann_message", height=100)
            with col_ann2:
                sems_ann = pd.read_sql_query("SELECT * FROM semesters", conn)
                ann_sem_options = ["All Semesters"] + sems_ann["name"].tolist()
                ann_sem = st.selectbox("Target Audience", ann_sem_options, key="ann_sem")
                ann_priority = st.selectbox("Priority", ["Normal", "Important", "Urgent"], key="ann_priority")
            
            if st.button("📢 Post Announcement", type="primary"):
                if not ann_title.strip() or not ann_message.strip():
                    st.error("Title and message required")
                else:
                    sem_id = None
                    if ann_sem != "All Semesters":
                        sem_id = int(sems_ann[sems_ann["name"] == ann_sem]["id"].values[0])
                    
                    success, msg = create_announcement(ann_title, ann_message, sem_id, ann_priority, st.session_state.user_id)
                    
                    if success:
                        with st.spinner("Broadcasting emails to students..."):
                            email_subject = f"📢 The N-Streamlines: {ann_title}"
                            email_body = f"Hello,\n\nA new announcement has been posted by Er. Nirajan Katuwal:\n\nTitle: {ann_title}\nPriority: {ann_priority}\n\nMessage:\n{ann_message}\n\nPlease log into the platform to view the details."
                            e_success, e_msg = send_email_notification(sem_id, email_subject, email_body)
                        if e_success:
                            st.success(f"✅ {msg} & {e_msg}")
                        else:
                            st.warning(f"✅ {msg}, but emails were skipped: {e_msg}")
                        st.rerun()
                    else:
                        st.error("❌ {}".format(msg))
        
        st.divider()
        
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
            overdue, due_today, due_soon, upcoming = [], [], [], []
            
            for _, assignment in all_assignments.iterrows():
                days, status, color = get_deadline_status(assignment['deadline'])
                assignment_info = {
                    'title': assignment['title'], 'subject': assignment['subject'],
                    'semester': assignment['semester'], 'deadline': assignment['deadline'],
                    'days': days, 'status': status, 'color': color, 'id': assignment['id']
                }
                if status == "Overdue": overdue.append(assignment_info)
                elif status == "Due Today": due_today.append(assignment_info)
                elif status == "Due Soon" or status == "This Week": due_soon.append(assignment_info)
                else: upcoming.append(assignment_info)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1: st.metric("🔴 Overdue", len(overdue))
            with col2: st.metric("🟠 Due Today", len(due_today))
            with col3: st.metric("🟡 Due This Week", len(due_soon))
            with col4: st.metric("🔵 Upcoming", len(upcoming))
            
            st.divider()
            
            if overdue:
                st.error("🔴 **OVERDUE ASSIGNMENTS**")
                for assign in overdue:
                    with st.expander("{} - {} ({})".format(assign['semester'], assign['subject'], assign['title'])):
                        st.write("**Deadline:** {}".format(assign['deadline']))
                        st.write("**Overdue by:** {} days".format(abs(assign['days'])))
                        submissions = pd.read_sql_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s", conn, params=(assign['id'],))
                        st.metric("Submissions Received", submissions.iloc[0]['count'])
            
            if due_today:
                st.warning("🟠 **DUE TODAY**")
                for assign in due_today:
                    st.info("{} - {} - {}".format(assign['semester'], assign['subject'], assign['title']))
            
            if due_soon:
                st.info("🟡 **DUE THIS WEEK**")
                for assign in due_soon:
                    st.write("📌 {} - {} - {} ({} days left)".format(assign['semester'], assign['subject'], assign['title'], assign['days']))
            
            st.divider()
            st.subheader("📈 Submission Statistics")
            for _, assignment in all_assignments.iterrows():
                total_submissions = pd.read_sql_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s", conn, params=(assignment['id'],)).iloc[0]['count']
                deadline_display = format_deadline_display(assignment['deadline'])
                with st.expander("{} - {} | {}".format(assignment['subject'], assignment['title'], deadline_display)):
                    col_a, col_b = st.columns(2)
                    with col_a: st.metric("Total Submissions", total_submissions)
                    with col_b:
                        graded = pd.read_sql_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s AND marks IS NOT NULL AND marks != ''", conn, params=(assignment['id'],)).iloc[0]['count']
                        st.metric("Graded", graded)

    # SEMESTERS
    with tabs[1]:
        name = st.text_input("New Semester")
        if st.button("Add Semester"):
            if not name.strip():
                st.error("Semester name cannot be empty.")
            else:
                try:
                    c.execute("INSERT INTO semesters(name) VALUES(%s)", (name.strip(),))
                    conn.commit()
                    st.success("✅ Semester Added")
                    st.rerun()
                except psycopg2.IntegrityError:
                    conn.rollback()
                    st.warning("⚠️ Semester already exists.")

        st.dataframe(pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn), use_container_width=True, hide_index=True)
        st.divider()
        st.subheader("Delete Semester")

        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn) 
        if not sems.empty:
            semester_options = {f"{row['name']} (ID:{row['id']})": row['id'] for _, row in sems.iterrows()}
            selected_sem = st.selectbox("select Semester to Delete", list(semester_options.keys()), key="delete_semester")
            if st.button("Delete Selected Semester"):
                sem_id = semester_options[selected_sem]
                try:
                    deleted_files = 0
                    subject_ids = pd.read_sql_query("SELECT id FROM subjects WHERE semester_id=%s", conn, params=(int(sem_id),))
                    for _, subject_row in subject_ids.iterrows():
                        assignments = pd.read_sql_query("SELECT id, question_file FROM assignments WHERE subject_id=%s", conn, params=(subject_row["id"],))
                        for _, assign_row in assignments.iterrows():
                            submissions = pd.read_sql_query("SELECT submission_file FROM submissions WHERE assignment_id=%s", conn, params=(assign_row["id"],))
                            for _, sub_row in submissions.iterrows():
                                if sub_row['submission_file'] and os.path.exists(sub_row['submission_file']):
                                    try: os.remove(sub_row['submission_file']); deleted_files += 1
                                    except: pass
                            c.execute("DELETE FROM submissions WHERE assignment_id=%s", (assign_row["id"],))
                            if assign_row['question_file'] and os.path.exists(assign_row['question_file']):
                                try: os.remove(assign_row['question_file']); deleted_files += 1
                                except: pass
                        c.execute("DELETE FROM assignments WHERE subject_id=%s", (subject_row["id"],))
                        materials = pd.read_sql_query("SELECT file_path FROM study_materials WHERE subject_id=%s", conn, params=(subject_row["id"],))
                        for _, mat_row in materials.iterrows():
                            if mat_row['file_path'] and os.path.exists(mat_row['file_path']):
                                try: os.remove(mat_row['file_path']); deleted_files += 1
                                except: pass
                        c.execute("DELETE FROM study_materials WHERE subject_id=%s", (subject_row["id"],))
                    c.execute("DELETE FROM subjects WHERE semester_id=%s", (sem_id,))
                    c.execute("UPDATE users SET semester_id=NULL WHERE semester_id=%s", (sem_id,))
                    c.execute("DELETE FROM semesters WHERE id=%s", (sem_id,))
                    conn.commit()
                    st.success("✅ Semester deleted! Removed {} files from disk.".format(deleted_files))
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error("Error deleting semester: {}".format(str(e)))

    # SUBJECTS
    with tabs[2]:
        st.title("📚 Subject Management")
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if sems.empty:
            st.warning("Please create a semester first.")
        else:
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
                        c.execute("INSERT INTO subjects(name,semester_id) VALUES(%s,%s)", (sub.strip(), int(sem_id)))
                        conn.commit()
                        st.success("✅ Subject '{}' added to {}".format(sub.strip(), sem))
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("Error adding subject: {}".format(str(e)))
            
            st.divider()
            st.subheader("📋 Subjects for: {}".format(sem))
            subjects_for_sem = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=%s ORDER BY name ASC", conn, params=(int(sem_id),))
            
            if subjects_for_sem.empty:
                st.info("No subjects found for this semester.")
            else:
                st.dataframe(subjects_for_sem[['id', 'name']], use_container_width=True, hide_index=True, column_config={"id": "Subject ID", "name": "Subject Name"})
                st.info("📊 Total Subjects: **{}**".format(len(subjects_for_sem)))
            
            st.divider()
            st.subheader("🗑️ Delete Subject")
            if not subjects_for_sem.empty:
                subject_options = {"{} (ID: {})".format(row['name'], row['id']): row['id'] for _, row in subjects_for_sem.iterrows()}
                selected_subject = st.selectbox("Select Subject to Delete from {}".format(sem), list(subject_options.keys()), key="delete_subject_select")
                col_warn1, col_warn2 = st.columns([2, 1])
                with col_warn1:
                    st.warning("⚠️ **Warning:** Deleting a subject will also delete:\n- All assignments under this subject\n- All submissions for those assignments")
                with col_warn2:
                    if st.button("🗑️ Confirm Delete Subject", type="primary", use_container_width=True):
                        subject_id = subject_options[selected_subject]
                        try:
                            assignment_ids = pd.read_sql_query("SELECT id FROM assignments WHERE subject_id=%s", conn, params=(int(subject_id),))
                            for _, row in assignment_ids.iterrows():
                                c.execute("DELETE FROM submissions WHERE assignment_id=%s", (row["id"],))
                            c.execute("DELETE FROM assignments WHERE subject_id=%s", (int(subject_id),))
                            materials = pd.read_sql_query("SELECT file_path FROM study_materials WHERE subject_id=%s", conn, params=(int(subject_id),))
                            for _, mat in materials.iterrows():
                                if mat['file_path'] and os.path.exists(mat['file_path']): os.remove(mat['file_path'])
                            c.execute("DELETE FROM study_materials WHERE subject_id=%s", (int(subject_id),))
                            c.execute("DELETE FROM subjects WHERE id=%s", (int(subject_id),))
                            conn.commit()
                            st.success("✅ Subject deleted successfully!")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error("Error deleting subject: {}".format(str(e)))
            else:
                st.info("No subjects available to delete in this semester.")
            
            st.divider()
            with st.expander("🔍 View All Subjects (All Semesters)"):
                all_subjects_debug = pd.read_sql_query("""
                SELECT subjects.id as ID, subjects.name as Subject, semesters.name as Semester
                FROM subjects JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY semesters.name, subjects.name
                """, conn)
                if not all_subjects_debug.empty:
                    st.dataframe(all_subjects_debug, use_container_width=True, hide_index=True)
                else:
                    st.info("No subjects created yet.")

    # ASSIGNMENTS
    with tabs[3]:
        st.title("📝 Assignment Management")
        st.subheader("➕ Create New Assignment")
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                sem_name = st.selectbox("Select Semester", sems["name"], key="assign_sem")
                sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])
                subjects = pd.read_sql_query("SELECT * FROM subjects WHERE semester_id=%s", conn, params=(sem_id,))
                if subjects.empty:
                    st.warning("Please create a subject for this semester first.")
                    subject_selected = None
                else:
                    subject_options = {row['name']: row['id'] for _, row in subjects.iterrows()}
                    selected_subject = st.selectbox("Select Subject", list(subject_options.keys()))
                    sub_id = int(subject_options[selected_subject])
                    subject_selected = True
            with col2:
                title = st.text_input("Assignment Title", placeholder="e.g., Design of RCC Beam")
                deadline = st.date_input("Deadline")
                rubric_text = st.text_area("🎯 Marking Rubric / Model Answer", placeholder="Key steps, formulas, or point breakdowns...")
                file = st.file_uploader("📎 Upload Assignment Question PDF (Optional)", type=["pdf"])

            if st.button("➕ Create Assignment", use_container_width=True, type="primary"):
                if not subject_selected:
                    st.error("Please select a subject.")
                elif not title.strip():
                    st.error("Title cannot be empty.")
                else:
                    file_path = ""
                    if file:
                        is_valid, validation_msg = validate_file_upload(file, ALLOWED_ASSIGNMENT_TYPES, MAX_FILE_SIZE_MB)
                        if not is_valid:
                            st.error("❌ File Validation Failed: {}".format(validation_msg))
                        else:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_path = "assignment_files/{}_{}.pdf".format(timestamp, file.name.replace(" ", "_"))
                            success, result = safe_file_operation(lambda: open(file_path, "wb").write(file.getbuffer()))
                            if not success:
                                st.error("❌ File Save Failed: {}".format(result))
                                file_path = ""
                    try:
                        c.execute("""
                        INSERT INTO assignments(title,subject_id,deadline,question_file,rubric)
                        VALUES(%s,%s,%s,%s,%s)
                        """, (title.strip(), int(sub_id), str(deadline), file_path, rubric_text.strip()))
                        conn.commit()
                        st.success("✅ Assignment '{}' created successfully!".format(title.strip()))
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("Database Error: {}".format(str(e)))
                        if file_path and os.path.exists(file_path):
                            try: os.remove(file_path)
                            except: pass

        st.divider()
        st.subheader("📋 Existing Assignments")
        view_sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not view_sems.empty:
            view_filter = st.selectbox("Filter by Semester", ["All"] + view_sems["name"].tolist(), key="view_assign_filter")
            if view_filter == "All":
                all_assignments = pd.read_sql_query("""
                SELECT assignments.id as ID, assignments.title as Title, subjects.name as Subject, semesters.name as Semester, assignments.deadline as Deadline, assignments.question_file as File
                FROM assignments JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY assignments.deadline DESC
                """, conn)
            else:
                filter_sem_id = int(view_sems[view_sems["name"] == view_filter]["id"].values[0])
                all_assignments = pd.read_sql_query("""
                SELECT assignments.id as ID, assignments.title as Title, subjects.name as Subject, semesters.name as Semester, assignments.deadline as Deadline, assignments.question_file as File
                FROM assignments JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id
                WHERE semesters.id = %s ORDER BY assignments.deadline DESC
                """, conn, params=(filter_sem_id,))

            if all_assignments.empty:
                st.info("No assignments created yet.")
            else:
                st.dataframe(all_assignments[['ID', 'Semester', 'Subject', 'Title', 'Deadline']], use_container_width=True, hide_index=True)
                st.info("📊 Total Assignments: **{}**".format(len(all_assignments)))
                st.divider()
                st.subheader("📄 Assignment Details")
                for _, assignment in all_assignments.iterrows():
                    submission_count = pd.read_sql_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s", conn, params=(assignment['ID'],)).iloc[0]['count']
                    deadline_display = format_deadline_display(assignment['Deadline'])
                    with st.expander("{} - {} - {} | {}".format(assignment['Semester'], assignment['Subject'], assignment['Title'], deadline_display)):
                        col_detail1, col_detail2 = st.columns([2, 1])
                        with col_detail1:
                            st.write("**Semester:** {}".format(assignment['Semester']))
                            st.write("**Subject:** {}".format(assignment['Subject']))
                            st.write("**Title:** {}".format(assignment['Title']))
                            st.write("**Deadline:** {}".format(assignment['Deadline']))
                            st.metric("📊 Total Submissions", submission_count)
                        with col_detail2:
                            if assignment['File'] and os.path.exists(assignment['File']):
                                with open(assignment['File'], "rb") as f:
                                    st.download_button("📥 Download Question", f, file_name=os.path.basename(assignment['File']), key="download_assign_{}".format(assignment['ID']), use_container_width=True)
                            else:
                                st.info("No file uploaded")
                        st.divider()
                        with st.expander("✏️ Edit Assignment Details"):
                            col_edit1, col_edit2 = st.columns(2)
                            with col_edit1:
                                new_title = st.text_input("New Title", value=assignment['Title'], key="edit_title_{}".format(assignment['ID']))
                            with col_edit2:
                                current_deadline = datetime.strptime(assignment['Deadline'], '%Y-%m-%d').date()
                                new_deadline = st.date_input("New Deadline", value=current_deadline, key="edit_deadline_{}".format(assignment['ID']))
                            if st.button("💾 Save Changes", key="save_edit_{}".format(assignment['ID']), type="primary"):
                                if not new_title.strip():
                                    st.error("Title cannot be empty")
                                elif new_title == assignment['Title'] and str(new_deadline) == assignment['Deadline']:
                                    st.info("No changes made")
                                else:
                                    success, message = update_assignment(assignment['ID'], new_title, new_deadline, assignment.get('rubric', ''))
                                    if success:
                                        st.success("✅ {}".format(message))
                                        st.rerun()
                                    else:
                                        st.error("❌ {}".format(message))
                        col_del1, col_del2 = st.columns([2, 1])
                        with col_del1:
                            st.warning("⚠️ **Delete Assignment:** This will remove all student submissions for this assignment.")
                        with col_del2:
                            if st.button("🗑️ Delete Assignment", key="delete_assign_{}".format(assignment['ID']), type="primary", use_container_width=True):
                                try:
                                    submissions = pd.read_sql_query("SELECT submission_file FROM submissions WHERE assignment_id=%s", conn, params=(assignment['ID'],))
                                    for _, sub in submissions.iterrows():
                                        if sub['submission_file'] and os.path.exists(sub['submission_file']): os.remove(sub['submission_file'])
                                    c.execute("DELETE FROM submissions WHERE assignment_id=%s", (assignment['ID'],))
                                    if assignment['File'] and os.path.exists(assignment['File']): os.remove(assignment['File'])
                                    c.execute("DELETE FROM assignments WHERE id=%s", (assignment['ID'],))
                                    conn.commit()
                                    st.success("✅ Assignment '{}' deleted successfully!".format(assignment['Title']))
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error("Error deleting assignment: {}".format(str(e)))

    # SUBMISSIONS & AI
    with tabs[4]:
        st.subheader("Student Submissions & AI Grading")
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems.empty:
            selected_sem = st.selectbox("Filter by Semester", ["All"] + sems["name"].tolist(), key="filter_sem")
            if selected_sem == "All":
                df = pd.read_sql_query("""
                SELECT submissions.id, users.username, users.full_name, semesters.name as semester, subjects.name as subject, assignments.title as assignment, assignments.rubric, submissions.submission_time, submissions.submission_file, submissions.marks, submissions.ai_summary
                FROM submissions JOIN users ON submissions.student_id = users.id JOIN assignments ON submissions.assignment_id = assignments.id JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY submissions.submission_time DESC
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = pd.read_sql_query("""
                SELECT submissions.id, users.username, users.full_name, semesters.name as semester, subjects.name as subject, assignments.title as assignment, assignments.rubric, submissions.submission_time, submissions.submission_file, submissions.marks, submissions.ai_summary
                FROM submissions JOIN users ON submissions.student_id = users.id JOIN assignments ON submissions.assignment_id = assignments.id JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id
                WHERE semesters.id = %s ORDER BY submissions.submission_time DESC
                """, conn, params=(sem_id,))
        else:
            df = pd.DataFrame()

        if df.empty:
            st.info("No submissions yet.")
        else:
            st.dataframe(df[["semester", "subject", "assignment", "username", "full_name", "submission_time", "marks"]], use_container_width=True, hide_index=True)
            st.divider()
            st.subheader("AI Grading Tool")
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
                                st.download_button("Download Submission", f, file_name=os.path.basename(row["submission_file"]), key="dl_{}".format(row['id']))
                    st.divider()
                    if row["submission_file"] and os.path.exists(row["submission_file"]):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("AI Grade", key="grade_{}".format(row['id'])):
                                if not row['rubric'] or not str(row['rubric']).strip():
                                    st.warning("Please enter a rubric/model answer first")
                                else:
                                    with st.spinner("AI is grading..."):
                                        try:
                                            result = vision_grade(row["submission_file"], row["rubric"])
                                            with st.expander("**AI Response:**", expanded=True):
                                                st.write(result)
                                            if result and "Error" not in str(result):
                                                marks = extract_marks(result)
                                                if marks is not None:
                                                    c.execute("UPDATE submissions SET marks=%s, ai_summary=%s WHERE id=%s", (marks, result, row["id"]))
                                                    conn.commit()
                                                    st.success("Updated marks: {}/10".format(marks))
                                                    st.rerun()
                                                else:
                                                    st.warning("Could not extract marks from AI response.Please enter manually below")
                                                    c.execute("UPDATE submissions SET ai_summary=%s WHERE id=%s", (str(result), int(row["id"])))
                                                    conn.commit()
                                            else:
                                                st.error("AI returned an error. Check the response above.")
                                        except Exception as e:
                                            st.error("Error during AI grading: {}".format(str(e)))
                        with col_b:
                            default_marks = 0
                            if row['marks'] and str(row['marks']).strip():
                                try: default_marks = int(row['marks'])
                                except: default_marks = 0
                            manual_marks = st.number_input("Or enter marks manually", min_value=0, max_value=10, value=default_marks, key="manual_{}".format(row['id']))
                            if st.button("Save Manual Marks", key="save_{}".format(row['id'])):
                                c.execute("UPDATE submissions SET marks=%s WHERE id=%s", (manual_marks, row["id"]))
                                conn.commit()
                                st.success("Marks updated to {}/10".format(manual_marks))
                                st.rerun()
                    if row['ai_summary'] and str(row['ai_summary']).strip():
                        with st.expander("Previous AI Feedback"):
                            st.write(row['ai_summary'])

    # ANALYTICS
    with tabs[5]:
        st.title(" Performance Analytics")
        st.subheader("📈 Class Performance Trend")
        trend_data = pd.read_sql_query("""
        SELECT assignments.title as Assignment, AVG(CAST(submissions.marks AS FLOAT)) as Average_Marks
        FROM submissions JOIN assignments ON submissions.assignment_id = assignments.id
        WHERE submissions.marks IS NOT NULL AND submissions.marks != ''
        GROUP BY assignments.id, assignments.title, assignments.deadline
        ORDER BY assignments.deadline ASC
        """, conn)
        if not trend_data.empty:
            trend_data.set_index('Assignment', inplace=True)
            st.area_chart(trend_data['Average_Marks'])
        else:
            st.info("Not enough graded submissions to generate a trend chart yet.")
        st.divider() 

        st.subheader("📊 Grade Statistics")
        sems = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems.empty:
            selected_sem = st.selectbox("Select Semester", ["All"] + sems["name"].tolist(), key="analytics_sem")
            if selected_sem == "All":
                df = pd.read_sql_query("""
                SELECT semesters.name as Semester, subjects.name as Subject, assignments.title as Assignment, users.full_name as Student_Name, users.username as Username, submissions.submission_time as Submission_Date, assignments.deadline as Deadline, submissions.marks as Marks, submissions.ai_summary as AI_Feedback
                FROM submissions JOIN assignments ON submissions.assignment_id=assignments.id JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id JOIN users ON submissions.student_id = users.id
                WHERE submissions.marks IS NOT NULL AND submissions.marks != ''
                ORDER BY semesters.name, subjects.name, assignments.title, users.full_name
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = pd.read_sql_query("""
                SELECT semesters.name as Semester, subjects.name as Subject, assignments.title as Assignment, users.full_name as Student_Name, users.username as Username, submissions.submission_time as Submission_Date, assignments.deadline as Deadline, submissions.marks as Marks, submissions.ai_summary as AI_Feedback
                FROM submissions JOIN assignments ON submissions.assignment_id=assignments.id JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id JOIN users ON submissions.student_id = users.id
                WHERE semesters.id = %s AND submissions.marks IS NOT NULL AND submissions.marks != ''
                ORDER BY subjects.name, assignments.title, users.full_name
                """, conn, params=(sem_id,))

            if not df.empty:
                df["marks"] = pd.to_numeric(df["Marks"], errors="coerce")
                st.subheader("📥 Download Grade Reports")
                col1, col2, col3 = st.columns(3)
                with col1:
                    csv_detailed = df.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📄 Detailed Report (with AI Feedback)", data=csv_detailed, file_name="Grades_Detailed_{}.csv".format(selected_sem), mime='text/csv', use_container_width=True)
                with col2:
                    df_summary = df[['Semester', 'Subject', 'Assignment', 'Student_Name', 'Username', 'Submission_Date', 'Deadline', 'Marks']]
                    csv_summary = df_summary.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📊 Summary Report (No Feedback)", data=csv_summary, file_name="Grades_Summary_{}.csv".format(selected_sem), mime='text/csv', use_container_width=True)
                with col3:
                    df_pivot = df.pivot_table(index=['Semester', 'Student_Name', 'Username', 'Subject'], columns='Assignment', values='marks', aggfunc='first').reset_index()
                    assignment_cols = [col for col in df_pivot.columns if col not in ['Semester', 'Student_Name', 'Username', 'Subject']]
                    df_pivot['Average'] = df_pivot[assignment_cols].mean(axis=1).round(2)
                    csv_pivot = df_pivot.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📈 Student-wise Summary", data=csv_pivot, file_name="Grades_StudentWise_{}.csv".format(selected_sem), mime='text/csv', use_container_width=True)
                st.divider()
                st.subheader("📊 Average Marks by Assignment")
                avg_marks = df.groupby("Assignment")["marks"].mean()
                st.bar_chart(avg_marks)
                st.divider()
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("Total Submissions", len(df))
                with col2: st.metric("Average Score", "{:.2f}/10".format(df['marks'].mean()))
                with col3: st.metric("Highest Score", "{}/10".format(df['marks'].max()))
                st.divider()
                st.subheader("📚 Subject-wise Performance")
                subject_stats = df.groupby('Subject').agg({'marks': ['count', 'mean', 'min', 'max']}).round(2)
                subject_stats.columns = ['Total Submissions', 'Average', 'Lowest', 'Highest']
                st.dataframe(subject_stats, use_container_width=True)
                st.divider()
                st.subheader("📋 Detailed Grade Table")
                st.dataframe(df[['Semester', 'Subject', 'Assignment', 'Student_Name', 'Username', 'Marks']], use_container_width=True, hide_index=True)
            else:
                st.info("📭 No graded submissions yet for this semester.")
        else:
            st.warning("⚠️ Please create semesters first.")

    # MANAGE STUDENTS
    with tabs[6]:
        st.subheader("⚠️ Emergency Fix for Existing Students")
        if st.button("🔧 Fix ALL Students with NULL semester"):
            default_sem = pd.read_sql_query("SELECT id FROM semesters ORDER BY id ASC LIMIT 1", conn)
            if not default_sem.empty:
                default_sem_id = int(default_sem.iloc[0]['id'])
                c.execute("UPDATE users SET semester_id = %s WHERE role = 'student' AND semester_id IS NULL", (default_sem_id,))
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
                st.info("Will assign semester_id: {}".format(semester_id))
                if st.button("Create Student"):
                    if not username or not password:
                        st.error("Username and password required.")
                    elif not student_name:
                        st.error("Full name is required.")
                    else:
                        try:
                            semester_id_to_insert = int(semester_id)
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(%s, %s, %s, %s, %s)
                            """, (student_name.strip(), username.strip(), hash_password(password.strip()), "student", semester_id_to_insert))
                            conn.commit()
                            verify = pd.read_sql_query("SELECT * FROM users WHERE username=%s", conn, params=(username.strip(),))
                            if not verify.empty:
                                st.success("✅ Student '{}' created!".format(username))
                                st.rerun()
                            else:
                                st.error("Student created but verification failed")
                        except psycopg2.IntegrityError:
                            conn.rollback()
                            st.error("Username already exists.")
                        except Exception as e:
                            conn.rollback()
                            st.error("Error creating student: {}".format(str(e)))
        st.divider()
        st.subheader("Bulk Upload Students via CSV")
        st.info("CSV format: name,username,password,semester")
        csv_file = st.file_uploader("Upload CSV", type=["csv"], key="student_csv")
        if csv_file:
            df_csv = pd.read_csv(csv_file)
            df_csv.columns=df_csv.columns.str.strip().str.lower()
            required_cols = {"name", "username", "password", "semester"}
            if not required_cols.issubset(df_csv.columns):
                st.error("CSV must contain columns: Name, Username, password, Semester")
            else:
                if st.button("🚀 Process & Register Students"):
                    sems = pd.read_sql_query("SELECT * FROM semesters", conn)
                    success_count = 0
                    error_count = 0
                    for _, row in df_csv.iterrows():
                        clean_name = str(row["name"]).strip()
                        clean_user = str(row["username"]).strip()
                        clean_sem = str(row["semester"]).strip()
                        raw_pw = str(row["password"]).replace('.0', '').strip()
                        sem_match = sems[sems["name"] == clean_sem]
                        if sem_match.empty:
                            error_count += 1
                            continue
                        sem_id = int
