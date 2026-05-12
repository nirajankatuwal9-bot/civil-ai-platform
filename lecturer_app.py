import streamlit as st
import pandas as pd
import psycopg2
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

# ================= DATABASE CONNECTION =================

@st.cache_resource(ttl=600)
def init_connection():
    # Added connect_timeout=10 so the app NEVER hangs for more than 10 seconds
    return psycopg2.connect(st.secrets["DATABASE_URL"], connect_timeout=10)

conn = init_connection()

# 1. First, check if psycopg2 already knows the connection is dead
if conn.closed != 0:
    st.cache_resource.clear()
    conn = init_connection()

# 2. Safe Ping & Clean
try:
    c = conn.cursor()
    c.execute("SELECT 1") # Ping the server
    conn.rollback()       # Clean up only IF the server responds
except Exception:
    # If the ping fails or times out, burn it down and reconnect
    st.cache_resource.clear()
    conn = init_connection()
    c = conn.cursor()

# ================= ANNOUNCEMENTS =================

def create_announcement(title, message, semester_id, priority, user_id):
    """
    Create a new announcement
    Returns: (success, message)
    """
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
    """
    Get announcements for a specific semester or all
    """
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

# ================= DATABASE TABLES =================

# First, ensure we start with a completely clean connection state
conn.rollback()

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
conn.commit() # <-- CRITICAL: Save the table BEFORE attempting to alter it!

# Safe auto-migration for existing users table
try:
    c.execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.commit()
except Exception:
    conn.rollback() 
    pass 

# SEMESTERS
c.execute("CREATE TABLE IF NOT EXISTS semesters(id SERIAL PRIMARY KEY, name TEXT UNIQUE)")
conn.commit()

# SUBJECTS
c.execute("CREATE TABLE IF NOT EXISTS subjects(id SERIAL PRIMARY KEY, name TEXT, semester_id INTEGER)")
conn.commit()

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
conn.commit() # <-- Save before alter

try:
    c.execute("ALTER TABLE assignments ADD COLUMN rubric TEXT")
    conn.commit()
except Exception:
    conn.rollback()
    pass

# SUBMISSIONS
c.execute("""
CREATE TABLE IF NOT EXISTS submissions(
    id SERIAL PRIMARY KEY, assignment_id INTEGER, student_id INTEGER, submission_time TEXT, 
    submission_file TEXT, marks TEXT, ai_summary TEXT
)
""")
conn.commit()

# STUDY MATERIALS
c.execute("""
CREATE TABLE IF NOT EXISTS study_materials(
    id SERIAL PRIMARY KEY, title TEXT, subject_id INTEGER, semester_id INTEGER, 
    file_path TEXT, description TEXT, upload_date TEXT, uploaded_by INTEGER
)
""")
conn.commit()

# ANNOUNCEMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS announcements(
    id SERIAL PRIMARY KEY, title TEXT, message TEXT, semester_id INTEGER, 
    created_by INTEGER, created_at TEXT, priority TEXT
)
""")
conn.commit()

# Final safety net before the rest of the app runs
conn.rollback()


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

import time

# Session timeout in seconds (30 minutes)
SESSION_TIMEOUT = 1800

def check_session_timeout():
    """
    Check if session has timed out
    Returns: True if session is valid, False if timed out
    """
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
    """
    Check login and session validity
    """
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
    return None

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

#===================PUSH Email===============================
def send_email_notification(target_semester_id, subject, message_body):
    """Fetches student emails and sends a secure BCC email broadcast."""
    
    # 1. Fetch student emails for this semester
    if target_semester_id:
        df = pd.read_sql_query("SELECT email FROM users WHERE role='student' AND semester_id=%s AND email IS NOT NULL AND email != ''", conn, params=(int(target_semester_id),))
    else:
        df = pd.read_sql_query("SELECT email FROM users WHERE role='student' AND email IS NOT NULL AND email != ''", conn)
    
    emails = df['email'].tolist()
    if not emails:
        return False, "No valid student emails found."

    # 2. Your Platform Credentials (Update these!)
    SENDER_EMAIL = "your_platform_email@gmail.com" 
    APP_PASSWORD = "your_16_digit_app_password"

    try:
        # 3. Construct the Email
        msg = MIMEMultipart()
        msg['From'] = f"The N-Streamlines <{SENDER_EMAIL}>"
        msg['Subject'] = subject
        msg.attach(MIMEText(message_body, 'plain'))
        
        # 4. Connect to Gmail and Send
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        
        # We send as BCC to protect student privacy!
        server.sendmail(SENDER_EMAIL, emails, msg.as_string())
        server.quit()
        return True, f"Emailed {len(emails)} students."
    except Exception as e:
        return False, f"Email error: {str(e)}"

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
# ================= FILE CLEANUP UTILITIES =================

def cleanup_orphaned_files():
    """
    Clean up files that exist on disk but not in database
    Returns: (files_deleted, space_freed_mb)
    """
    deleted_count = 0
    space_freed = 0
    
    # Get all files referenced in database
    db_files = set()
    
    # 1. Assignment question files
    assignments = pd.read_sql_query("SELECT question_file FROM assignments WHERE question_file IS NOT NULL AND question_file != ''", conn)
    for _, row in assignments.iterrows():
        if row['question_file']:
            db_files.add(row['question_file'])
    
    # 2. Submission files
    submissions = pd.read_sql_query("SELECT submission_file FROM submissions WHERE submission_file IS NOT NULL AND submission_file != ''", conn)
    for _, row in submissions.iterrows():
        if row['submission_file']:
            db_files.add(row['submission_file'])
    
    # 3. Study material files
    materials = pd.read_sql_query("SELECT file_path FROM study_materials WHERE file_path IS NOT NULL AND file_path != ''", conn)
    for _, row in materials.iterrows():
        if row['file_path']:
            db_files.add(row['file_path'])
    
    # Check each folder for orphaned files
    folders = ['assignment_files', 'submission_files', 'study_materials']
    
    for folder in folders:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                
                # If file exists on disk but not in database
                if file_path not in db_files and os.path.isfile(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        space_freed += file_size
                    except Exception as e:
                        st.warning("Could not delete {}: {}".format(file_path, str(e)))
    
    space_freed_mb = space_freed / (1024 * 1024)  # Convert to MB
    return deleted_count, round(space_freed_mb, 2)


def get_storage_stats():
    """
    Get storage usage statistics
    Returns: dict with folder sizes
    """
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

# Configuration constants
MAX_FILE_SIZE_MB = 25  # Maximum file size in MB
ALLOWED_ASSIGNMENT_TYPES = ['pdf']
ALLOWED_SUBMISSION_TYPES = ['pdf']
ALLOWED_MATERIAL_TYPES = ['pdf', 'docx', 'pptx', 'zip', 'jpg', 'png']

def validate_file_upload(uploaded_file, allowed_types, max_size_mb=MAX_FILE_SIZE_MB):
    """
    Validate uploaded file for type and size
    Returns: (is_valid, error_message)
    """
    if uploaded_file is None:
        return False, "No file uploaded"
    
    # Check file extension
    file_extension = uploaded_file.name.split('.')[-1].lower()
    if file_extension not in allowed_types:
        return False, "Invalid file type. Allowed: {}".format(', '.join(allowed_types))
    
    # Check file size
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, "File too large! Maximum size: {} MB (Your file: {:.2f} MB)".format(max_size_mb, file_size_mb)
    
    # Check if file is actually a PDF (magic number check for PDFs)
    if file_extension == 'pdf':
        uploaded_file.seek(0)
        header = uploaded_file.read(5)
        uploaded_file.seek(0)
        if header != b'%PDF-':
            return False, "File appears to be corrupted or not a valid PDF"
    
    return True, "File is valid"


def safe_file_operation(operation, *args, **kwargs):
    """
    Wrapper for safe file operations with error handling
    Returns: (success, result_or_error_message)
    """
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
    """
    Check if deadline has passed
    Returns: (is_late, message)
    """
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

# ================= DATABASE BACKUP SYSTEM (SAFE VERSION) =================

def create_database_backup():
    """
    Create a timestamped backup of the database
    Returns: (success, message)
    """
    try:
        import sqlite3
        import shutil
        
        # Create backup directory
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = "lecturer_backup_{}.db".format(timestamp)
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Postgres backup logic
        backup_conn = sqlite3.connect(backup_path)
        tables = ['users', 'semesters', 'subjects', 'assignments', 'submissions', 'study_materials', 'announcements']
        for t in tables:
            df = pd.read_sql_query("SELECT * FROM {}".format(t), conn)
            df.to_sql(t, backup_conn, index=False, if_exists='replace')
        backup_conn.close()
        
        # Verify backup was created
        if not os.path.exists(backup_path):
            return False, "Backup file was not created"
        
        # Get backup file size
        backup_size = os.path.getsize(backup_path) / 1024  # KB
        
        # Clean old backups (keep only last 10)
        cleanup_old_backups(backup_dir, keep_count=10)
        
        return True, "Backup created: {} ({:.2f} KB)".format(backup_filename, backup_size)
    
    except PermissionError:
        return False, "Permission denied. Database may be locked."
    except Exception as e:
        return False, "Backup failed: {}".format(str(e))


def cleanup_old_backups(backup_dir, keep_count=10):
    """
    Keep only the most recent N backups
    """
    try:
        if not os.path.exists(backup_dir):
            return
        
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.startswith("lecturer_backup_") and filename.endswith(".db"):
                file_path = os.path.join(backup_dir, filename)
                try:
                    mod_time = os.path.getmtime(file_path)
                    backups.append((file_path, mod_time))
                except:
                    continue
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        # Delete old backups
        for file_path, _ in backups[keep_count:]:
            try:
                os.remove(file_path)
            except:
                pass
    
    except:
        pass  # Silently fail


def restore_database_from_backup(backup_path):
    """
    Restore database from a backup file
    
    ⚠️ WARNING: This will replace the current database!
    The app needs to be restarted after restore.
    
    Returns: (success, message)
    """
    try:
        import sqlite3
        from sqlalchemy import create_engine
        
        if not os.path.exists(backup_path):
            return False, "Backup file not found: {}".format(backup_path)
        
        # Verify backup file is valid
        backup_size = os.path.getsize(backup_path)
        if backup_size < 1000:  # Less than 1KB is suspicious
            return False, "Backup file appears to be corrupted (too small)"
            
        backup_conn = sqlite3.connect(backup_path)
        db_url = "postgresql://{}:{}@{}:{}/{}".format(
            st.secrets["DATABASE_URL"].split(':')[1].strip('/'), # Minimal parse for SQLAlchemy if needed, but since you are using full URL:
        ) # Fallback to standard connection if URL parsing fails
        
        # Better safe way using secrets
        engine = create_engine(st.secrets["DATABASE_URL"])
        
        tables = ['users', 'semesters', 'subjects', 'assignments', 'submissions', 'study_materials', 'announcements']
        for t in tables:
            df = pd.read_sql_query("SELECT * FROM {}".format(t), backup_conn)
            c.execute("TRUNCATE TABLE {} RESTART IDENTITY CASCADE".format(t))
            conn.commit()
            df.to_sql(t, engine, index=False, if_exists='append')
        backup_conn.close()
        
        return True, "✅ Database restored from backup. IMPORTANT: Please RESTART the app (refresh page) to reconnect to the restored database."
    
    except Exception as e:
        conn.rollback()
        return False, "Restore error: {}".format(str(e))


def get_backup_list():
    """
    Get list of available backups with metadata
    Returns: list of dicts with backup info
    """
    backup_dir = "data/backups"
    backups = []
    
    if not os.path.exists(backup_dir):
        return backups
    
    for filename in os.listdir(backup_dir):
        if filename.startswith("lecturer_backup_") and filename.endswith(".db"):
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
    
    # Sort by date (newest first)
    backups.sort(key=lambda x: x['date'], reverse=True)
    
    return backups

# ================= CONFIRMATION DIALOGS =================

def confirm_delete(item_name, item_type="item"):
    """
    Create a two-step confirmation for delete actions
    Returns: True if confirmed, False otherwise
    """
    confirm_key = "confirm_delete_{}".format(item_name.replace(" ", "_"))
    
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False
    
    if not st.session_state[confirm_key]:
        if st.button("🗑️ Delete {}".format(item_type), key="first_{}".format(confirm_key)):
            st.session_state[confirm_key] = True
            st.rerun()
        return False
    else:
        st.warning("⚠️ Are you sure? This cannot be undone!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Delete", key="confirm_{}".format(confirm_key), type="primary"):
                st.session_state[confirm_key] = False
                return True
        with col2:
            if st.button("❌ Cancel", key="cancel_{}".format(confirm_key)):
                st.session_state[confirm_key] = False
                st.rerun()
        return False
# ================= SEARCH FUNCTIONALITY =================

def search_students(query, semester_id=None):
    """
    Search students by name or username
    Returns: DataFrame of matching students
    """
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
        """, conn, params=(int(semester_id), '%{}%'.format(query), '%{}%'.format(query)))
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
    """
    Search assignments by title or subject
    Returns: DataFrame of matching assignments
    """
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
# ================= EDIT ASSIGNMENT =================

def update_assignment(assignment_id, new_title, new_deadline,new_rubric):
    """
    Update assignment title, deadline, and rubric
    Returns: (success, message)
    """
    try:
        c.execute("""
        UPDATE assignments 
        SET title=%s, deadline=%s,rubric=%s
        WHERE id=%s
        """, (new_title.strip(), str(new_deadline), new_rubric.strip(), int(assignment_id)))
        
        conn.commit()
        return True, "Assignment updated successfully"
    except Exception as e:
        conn.rollback()
        return False, "Update failed: {}".format(str(e))
# ================= STUDENT PROFILE =================

def get_student_profile(student_id):
    """
    Get complete student profile with all statistics
    Returns: dict with student data
    """
    try:
        # Basic info
        student_info = pd.read_sql_query("""
        SELECT users.*, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.id=%s
        """, conn, params=(int(student_id),))
        
        if student_info.empty:
            return None
        
        # Submission stats
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
        
        # Calculate statistics
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
        
        # ========== CREATE ANNOUNCEMENT ==========
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
                    
                    success, msg = create_announcement(
                        ann_title,
                        ann_message,
                        sem_id,
                        ann_priority,
                        st.session_state.user_id
                    )
                    
                    if success:
                        with st.spinner("Broadcasting emails to students..."):
                            # Format the email content
                            email_subject = f"📢 The N-Streamlines: {ann_title}"
                            email_body = f"Hello,\n\nA new announcement has been posted by Er. Nirajan Katuwal:\n\nTitle: {ann_title}\nPriority: {ann_priority}\n\nMessage:\n{ann_message}\n\nPlease log into the platform to view the details."

                            # Fire the email engine
                            e_success, e_msg = send_email_notification(sem_id, email_subject, email_body)
                        if e_success:
                            st.success(f"✅ {msg} & {e_msg}")
                        else:
                            st.warning(f"✅ {msg}, but emails were skipped: {e_msg}")
                        st.rerun()
                            
                        st.success("✅ {}".format(msg))
                        st.rerun()
                    else:
                        st.error("❌ {}".format(msg))
        
        st.divider()
        
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
                        WHERE assignment_id=%s
                        """, conn, params=(int(assign['id']),))
                        
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
                WHERE assignment_id=%s
                """, conn, params=(int(assignment['id']),)).iloc[0]['count']
                
                # Count total students in semester
                semester_id = pd.read_sql_query("""
                SELECT semester_id FROM subjects WHERE id=%s
                """, conn, params=(assignment['subject'],))
                
                deadline_display = format_deadline_display(assignment['deadline'])
                
                with st.expander("{} - {} | {}".format(assignment['subject'], assignment['title'], deadline_display)):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.metric("Total Submissions", total_submissions)
                    
                    with col_b:
                        graded = pd.read_sql_query("""
                        SELECT COUNT(*) as count FROM submissions
                        WHERE assignment_id=%s AND marks IS NOT NULL AND marks != ''
                        """, conn, params=(int(assignment['id']),)).iloc[0]['count']
                        
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
                
                try:
                    deleted_files = 0
                    
                    # Step 1: Get all subjects in this semester
                    subject_ids = pd.read_sql_query(
                        "SELECT id FROM subjects WHERE semester_id=%s",
                        conn,
                        params=(int(sem_id),)
                    )
                    
                    # Step 2: For each subject, delete all related files
                    for _, subject_row in subject_ids.iterrows():
                        
                        # Get all assignments for this subject
                        assignments = pd.read_sql_query(
                            "SELECT id, question_file FROM assignments WHERE subject_id=%s",
                            conn,
                            params=(int(subject_row["id"]),)
                        )
                        
                        # For each assignment
                        for _, assign_row in assignments.iterrows():
                            
                            # Delete all submission files
                            submissions = pd.read_sql_query(
                                "SELECT submission_file FROM submissions WHERE assignment_id=%s",
                                conn,
                                params=(int(assign_row["id"]),)
                            )
                            
                            for _, sub_row in submissions.iterrows():
                                if sub_row['submission_file'] and os.path.exists(sub_row['submission_file']):
                                    try:
                                        os.remove(sub_row['submission_file'])
                                        deleted_files += 1
                                    except:
                                        pass
                            
                            # Delete all submissions (database)
                            c.execute("DELETE FROM submissions WHERE assignment_id=%s", (int(assign_row["id"]),))
                            
                            # Delete assignment question file
                            if assign_row['question_file'] and os.path.exists(assign_row['question_file']):
                                try:
                                    os.remove(assign_row['question_file'])
                                    deleted_files += 1
                                except:
                                    pass
                        
                        # Delete all assignments for this subject
                        c.execute("DELETE FROM assignments WHERE subject_id=%s", (int(subject_row["id"]),))
                        
                        # Delete all study materials for this subject
                        materials = pd.read_sql_query(
                            "SELECT file_path FROM study_materials WHERE subject_id=%s",
                            conn,
                            params=(int(subject_row["id"]),)
                        )
                        
                        for _, mat_row in materials.iterrows():
                            if mat_row['file_path'] and os.path.exists(mat_row['file_path']):
                                try:
                                    os.remove(mat_row['file_path'])
                                    deleted_files += 1
                                except:
                                    pass
                        
                        c.execute("DELETE FROM study_materials WHERE subject_id=%s", (int(subject_row["id"]),))
                    
                    # Step 3: Delete all subjects
                    c.execute("DELETE FROM subjects WHERE semester_id=%s", (int(sem_id),))
                    
                    # Step 4: Update students (set semester_id to NULL)
                    c.execute("UPDATE users SET semester_id=NULL WHERE semester_id=%s", (int(sem_id),))
                    
                    # Step 5: Delete semester
                    c.execute("DELETE FROM semesters WHERE id=%s", (int(sem_id),))
                    
                    conn.commit()
                    st.success("✅ Semester deleted! Removed {} files from disk.".format(deleted_files))
                    st.rerun()
                    
                except Exception as e:
                    conn.rollback()
                    st.error("Error deleting semester: {}".format(str(e)))
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
                            "INSERT INTO subjects(name,semester_id) VALUES(%s,%s)",
                            (sub.strip(), int(sem_id))
                        )
                        conn.commit()
                        st.success("✅ Subject '{}' added to {}".format(sub.strip(), sem))
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("Error adding subject: {}".format(str(e)))
            
            st.divider()
            
            # ========== VIEW SUBJECTS ==========
            st.subheader("📋 Subjects for: {}".format(sem))
            
            subjects_for_sem = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=%s ORDER BY name ASC",
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
                                "SELECT id FROM assignments WHERE subject_id=%s",
                                conn,
                                params=(int(subject_id),)
                            )
                            
                            # Delete submissions for each assignment
                            for _, row in assignment_ids.iterrows():
                                c.execute("DELETE FROM submissions WHERE assignment_id=%s", (int(row["id"]),))
                            
                            # Delete all assignments for this subject
                            c.execute("DELETE FROM assignments WHERE subject_id=%s", (int(subject_id),))
                            
                            # Delete all study materials for this subject
                            materials = pd.read_sql_query(
                                "SELECT file_path FROM study_materials WHERE subject_id=%s",
                                conn,
                                params=(int(subject_id),)
                            )
                            for _, mat in materials.iterrows():
                                if mat['file_path'] and os.path.exists(mat['file_path']):
                                    os.remove(mat['file_path'])
                            
                            c.execute("DELETE FROM study_materials WHERE subject_id=%s", (int(subject_id),))
                            
                            # Finally, delete the subject
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
                    "SELECT * FROM subjects WHERE semester_id=%s",
                    conn,
                    params=(int(sem_id),)
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
                        # ✅ VALIDATE FILE
                        is_valid, validation_msg = validate_file_upload(file, ALLOWED_ASSIGNMENT_TYPES, MAX_FILE_SIZE_MB)
                        
                        if not is_valid:
                            st.error("❌ File Validation Failed: {}".format(validation_msg))
                        else:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_path = "assignment_files/{}_{}.pdf".format(timestamp, file.name.replace(" ", "_"))
                            
                            # Safe file save operation
                            success, result = safe_file_operation(
                                lambda: open(file_path, "wb").write(file.getbuffer())
                            )
                            
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
                        # Cleanup file if database insert failed
                        if file_path and os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                            except:
                                pass

        st.divider()
