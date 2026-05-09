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

# ================= ANNOUNCEMENTS =================

def create_announcement(title, message, semester_id, priority, user_id):
    """
    Create a new announcement
    Returns: (success, message)
    """
    try:
        c.execute("""
        INSERT INTO announcements(title, message, semester_id, created_by, created_at, priority)
        VALUES(?,?,?,?,?,?)
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
        WHERE announcements.semester_id=? OR announcements.semester_id IS NULL
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

# ASSIGNMENTS - Updated with Rubric column
c.execute("""
CREATE TABLE IF NOT EXISTS assignments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    subject_id INTEGER,
    deadline TEXT,
    question_file TEXT,
    rubric TEXT  -- Stores the model answer/grading key
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
# ANNOUNCEMENTS
c.execute("""
CREATE TABLE IF NOT EXISTS announcements(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                tables = ["users", "submissions", "assignments", "subjects", "semesters", "announcements", "study_materials"]
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
        
        # CONFIGURE WITH api KEY
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

        # CONVERT pdf TO IMAGES
        images = convert_from_path(pdf_path)

        # Use Gemini Flash Model
        model = genai.GenerativeModel('gemini-3-flash-preview')

        # Prepare the text prompt using only f-string for consistency
        prompt = f"""
You are a strict Civil Engineering Professor. Grade this student's handwritten work based ONLY on the provided model answer.

### ASSIGNMENT RUBRIC / MODEL ANSWER:
{rubric}

### GRADING INSTRUCTIONS:
1.  **Extract Equations:** Identify the primary governing equations used by the student (e.g., Manning's, Bernoulli's).
2.  **Multidimensional Scoring:** 
    - **Conceptual (4/4):** Did they choose the right approach?
    - **Math Accuracy (4/4):** Are the step-by-step calculations correct?
    - **Units & Presentation (2/2):** Are the final units (m, m³/s, etc.) present and correct?

### RESPONSE FORMAT (STRICT):
FINAL_MARKS: X/10
SCORECARD:
- Concepts: X/4
- Math: X/4
- Units: X/2

DETECTED_EQUATIONS:
[List extracted LaTeX equations here]

FEEDBACK:
- [Point 1: What they did well]
- [Point 2: Specific error in calculation or unit]
- [Point 3: Guidance for improvement]

Now grade the assignment shown in the images below:"""

        # Prepare content-parts
        content_parts = [prompt]

        # ADD images (limit to first 5 pages to avoid token limits)
        for idx, img in enumerate(images[:5]):
            content_parts.append(img)
            
        # Generate Response
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
    Returns an integer between 1-10, or None if not found.
    """
    if not text:
        return None
    
    text = str(text)
    
    # Try multiple patterns to extract marks 
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
                # Ensure marks are within valid range
                if 0 <= marks <= 10:
                    return marks
            except (ValueError, IndexError):
                continue
    return None 

def apply_watermark(file_path, watermark_text="🌊 The N-Streamlines | Er. Nirajan Katuwal | Do Not Distribute"):
    """Stamps a watermark on every page of a PDF."""
    try:
        import fitz
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
    try:
        # Parse deadline
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        
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
        import shutil
        
        # Create backup directory
        backup_dir = "data/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = "lecturer_backup_{}.db".format(timestamp)
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy database file
        shutil.copy2(DB_PATH, backup_path)
        
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
    
    WARNING: This will replace the current database!
    The app needs to be restarted after restore.
    
    Returns: (success, message)
    """
    try:
        import shutil
        
        if not os.path.exists(backup_path):
            return False, "Backup file not found: {}".format(backup_path)
        
        # Verify backup file is valid
        backup_size = os.path.getsize(backup_path)
        if backup_size < 1000:  # Less than 1KB is suspicious
            return False, "Backup file appears to be corrupted (too small)"
        
        # Create emergency backup of current database
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        emergency_backup = "{}.before_restore_{}".format(DB_PATH, timestamp)
        
        try:
            shutil.copy2(DB_PATH, emergency_backup)
        except:
            return False, "Could not create emergency backup of current database"
        
        # Perform restore
        try:
            shutil.copy2(backup_path, DB_PATH)
        except PermissionError:
            return False, "Permission denied. Close all database connections first."
        except Exception as e:
            # Try to restore emergency backup
            try:
                shutil.copy2(emergency_backup, DB_PATH)
            except:
                pass
            return False, "Restore failed: {}".format(str(e))
        
        return True, "✅ Database restored from backup. IMPORTANT: Please RESTART the app (refresh page) to reconnect to the restored database."
    
    except Exception as e:
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
        AND users.semester_id=?
        AND (LOWER(users.full_name) LIKE ? OR LOWER(users.username) LIKE ?)
        ORDER BY users.full_name ASC
        """, conn, params=(semester_id, '%{}%'.format(query), '%{}%'.format(query)))
    else:
        results = pd.read_sql_query("""
        SELECT users.id, users.full_name, users.username, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student' 
        AND (LOWER(users.full_name) LIKE ? OR LOWER(users.username) LIKE ?)
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
    WHERE LOWER(assignments.title) LIKE ? OR LOWER(subjects.name) LIKE ?
    ORDER BY assignments.deadline DESC
    """, conn, params=('%{}%'.format(query), '%{}%'.format(query)))
    
    return results
# ================= EDIT ASSIGNMENT =================

def update_assignment(assignment_id, new_title, new_deadline):
    """
    Update assignment title and deadline
    Returns: (success, message)
    """
    try:
        c.execute("""
        UPDATE assignments 
        SET title=?, deadline=?
        WHERE id=?
        """, (new_title.strip(), str(new_deadline), int(assignment_id)))
        
        conn.commit()
        return True, "Assignment updated successfully"
    except Exception as e:
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
        WHERE users.id=?
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
        WHERE submissions.student_id=?
        ORDER BY submissions.submission_time DESC
        """, conn, params=(int(student_id),))
        
        # Calculate statistics
        total_submissions = len(submissions)
        graded = submissions[submissions['marks'].notna() & (submissions['marks'] != '')]
        total_graded = len(graded)
        
        if total_graded > 0:
            graded = graded.copy()
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
                        st.success("✅ {}".format(msg))
                        st.rerun()
                    else:
                        st.error("❌ {}".format(msg))
        
        st.divider()
        
        # Get all assignments
        all_assignments_dash = pd.read_sql_query("""
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
        
        if all_assignments_dash.empty:
            st.info("No assignments created yet.")
        else:
            st.subheader("⏰ Assignment Deadlines Overview")
            
            # Categorize assignments
            overdue = []
            due_today = []
            due_soon = []
            upcoming = []
            
            for _, assignment in all_assignments_dash.iterrows():
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
                        
                        submissions_count = pd.read_sql_query("""
                        SELECT COUNT(*) as count FROM submissions
                        WHERE assignment_id=?
                        """, conn, params=(assign['id'],))
                        st.metric("Submissions Received", submissions_count.iloc[0]['count'])
            
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
            
            for _, assignment in all_assignments_dash.iterrows():
                # Count submissions
                total_submissions_count = pd.read_sql_query("""
                SELECT COUNT(*) as count FROM submissions
                WHERE assignment_id=?
                """, conn, params=(assignment['id'],)).iloc[0]['count']
                
                deadline_display_dash = format_deadline_display(assignment['deadline'])
                
                with st.expander("{} - {} | {}".format(assignment['subject'], assignment['title'], deadline_display_dash)):
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.metric("Total Submissions", total_submissions_count)
                    
                    with col_b:
                        graded_count = pd.read_sql_query("""
                        SELECT COUNT(*) as count FROM submissions
                        WHERE assignment_id=? AND marks IS NOT NULL AND marks != ''
                        """, conn, params=(assignment['id'],)).iloc[0]['count']
                        st.metric("Graded", graded_count)

    # SEMESTERS
    with tabs[1]:
        name_sem = st.text_input("New Semester")

        if st.button("Add Semester"):
            if not name_sem.strip():
                st.error("Semester name cannot be empty.")
            else:
                try:
                    c.execute("INSERT INTO semesters(name) VALUES(?)", (name_sem.strip(),))
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

        sems_list = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn) 
        if not sems_list.empty:
            semester_options_del = {
                f"{row['name']} (ID:{row['id']})": row['id']
                for _, row in sems_list.iterrows()
            }

            selected_sem_del = st.selectbox(
                "select Semester to Delete",
                list(semester_options_del.keys()),
                key="delete_semester"
            )
            if st.button("Delete Selected Semester"):

                sem_id_del = semester_options_del[selected_sem_del]
                
                try:
                    deleted_files_sem = 0
                    
                    # Step 1: Get all subjects in this semester
                    subject_ids_sem = pd.read_sql_query(
                        "SELECT id FROM subjects WHERE semester_id=?",
                        conn,
                        params=(int(sem_id_del),)
                    )
                    
                    # Step 2: For each subject, delete all related files
                    for _, subject_row in subject_ids_sem.iterrows():
                        
                        # Get all assignments for this subject
                        assignments_sem = pd.read_sql_query(
                            "SELECT id, question_file FROM assignments WHERE subject_id=?",
                            conn,
                            params=(subject_row["id"],)
                        )
                        
                        # For each assignment
                        for _, assign_row in assignments_sem.iterrows():
                            
                            # Delete all submission files
                            submissions_sem = pd.read_sql_query(
                                "SELECT submission_file FROM submissions WHERE assignment_id=?",
                                conn,
                                params=(assign_row["id"],)
                            )
                            
                            for _, sub_row in submissions_sem.iterrows():
                                if sub_row['submission_file'] and os.path.exists(sub_row['submission_file']):
                                    try:
                                        os.remove(sub_row['submission_file'])
                                        deleted_files_sem += 1
                                    except:
                                        pass
                            
                            # Delete all submissions (database)
                            c.execute("DELETE FROM submissions WHERE assignment_id=?", (assign_row["id"],))
                            
                            # Delete assignment question file
                            if assign_row['question_file'] and os.path.exists(assign_row['question_file']):
                                try:
                                    os.remove(assign_row['question_file'])
                                    deleted_files_sem += 1
                                except:
                                    pass
                        
                        # Delete all assignments for this subject
                        c.execute("DELETE FROM assignments WHERE subject_id=?", (subject_row["id"],))
                        
                        # Delete all study materials for this subject
                        materials_sem = pd.read_sql_query(
                            "SELECT file_path FROM study_materials WHERE subject_id=?",
                            conn,
                            params=(subject_row["id"],)
                        )
                        
                        for _, mat_row in materials_sem.iterrows():
                            if mat_row['file_path'] and os.path.exists(mat_row['file_path']):
                                try:
                                    os.remove(mat_row['file_path'])
                                    deleted_files_sem += 1
                                except:
                                    pass
                        
                        c.execute("DELETE FROM study_materials WHERE subject_id=?", (subject_row["id"],))
                    
                    # Step 3: Delete all subjects
                    c.execute("DELETE FROM subjects WHERE semester_id=?", (sem_id_del,))
                    
                    # Step 4: Update students (set semester_id to NULL)
                    c.execute("UPDATE users SET semester_id=NULL WHERE semester_id=?", (sem_id_del,))
                    
                    # Step 5: Delete semester
                    c.execute("DELETE FROM semesters WHERE id=?", (sem_id_del,))
                    
                    conn.commit()
                    st.success("✅ Semester deleted! Removed {} files from disk.".format(deleted_files_sem))
                    st.rerun()
                    
                except Exception as e:
                    st.error("Error deleting semester: {}".format(str(e)))
    
    # SUBJECTS
    with tabs[2]: 
        st.title("📚 Subject Management")
        
        sems_list_sub = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if sems_list_sub.empty:
            st.warning("Please create a semester first.")
        else:
            st.subheader("➕ Add New Subject")
            
            col1_sub, col2_sub = st.columns([1, 2])
            
            with col1_sub:
                sem_sel_sub = st.selectbox("Select Semester", sems_list_sub["name"], key="subject_semester")
                sem_id_sub = int(sems_list_sub[sems_list_sub["name"] == sem_sel_sub]["id"].values[0])
            
            with col2_sub:
                sub_name_input = st.text_input("Subject Name", key="subject_name", placeholder="e.g., Structural Analysis")
            
            if st.button("➕ Add Subject", use_container_width=True):
                if not sub_name_input.strip():
                    st.error("Subject name cannot be empty.")
                else:
                    try:
                        c.execute(
                            "INSERT INTO subjects(name,semester_id) VALUES(?,?)",
                            (sub_name_input.strip(), int(sem_id_sub))
                        )
                        conn.commit()
                        st.success("✅ Subject '{}' added to {}".format(sub_name_input.strip(), sem_sel_sub))
                        st.rerun()
                    except Exception as e:
                        st.error("Error adding subject: {}".format(str(e)))
            
            st.divider()
            st.subheader("📋 Subjects for: {}".format(sem_sel_sub))
            
            subjects_for_sem_view = pd.read_sql_query(
                "SELECT * FROM subjects WHERE semester_id=? ORDER BY name ASC",
                conn,
                params=(int(sem_id_sub),)
            )
            
            if subjects_for_sem_view.empty:
                st.info("No subjects found for this semester.")
            else:
                st.dataframe(
                    subjects_for_sem_view[['id', 'name']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "id": "Subject ID",
                        "name": "Subject Name"
                    }
                )
                st.info("📊 Total Subjects: **{}**".format(len(subjects_for_sem_view)))
            
            st.divider()
            st.subheader("🗑️ Delete Subject")
            
            if not subjects_for_sem_view.empty:
                subject_options_del = {
                    "{} (ID: {})".format(row['name'], row['id']): row['id']
                    for _, row in subjects_for_sem_view.iterrows()
                }
                
                selected_subject_del = st.selectbox(
                    "Select Subject to Delete from {}".format(sem_sel_sub),
                    list(subject_options_del.keys()),
                    key="delete_subject_select"
                )
                
                col_warn1_sub, col_warn2_sub = st.columns([2, 1])
                
                with col_warn1_sub:
                    st.warning("⚠️ **Warning:** Deleting a subject will also delete:\n- All assignments under this subject\n- All submissions for those assignments")
                
                with col_warn2_sub:
                    if st.button("🗑️ Confirm Delete Subject", type="primary", use_container_width=True):
                        subject_id_final = subject_options_del[selected_subject_del]
                        try:
                            assignment_ids_sub = pd.read_sql_query(
                                "SELECT id FROM assignments WHERE subject_id=?",
                                conn,
                                params=(int(subject_id_final),)
                            )
                            for _, row in assignment_ids_sub.iterrows():
                                c.execute("DELETE FROM submissions WHERE assignment_id=?", (row["id"],))
                            
                            c.execute("DELETE FROM assignments WHERE subject_id=?", (int(subject_id_final),))
                            
                            materials_sub = pd.read_sql_query(
                                "SELECT file_path FROM study_materials WHERE subject_id=?",
                                conn,
                                params=(int(subject_id_final),)
                            )
                            for _, mat in materials_sub.iterrows():
                                if mat['file_path'] and os.path.exists(mat['file_path']):
                                    os.remove(mat['file_path'])
                            
                            c.execute("DELETE FROM study_materials WHERE subject_id=?", (int(subject_id_final),))
                            c.execute("DELETE FROM subjects WHERE id=?", (int(subject_id_final),))
                            conn.commit()
                            st.success("✅ Subject deleted successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error("Error deleting subject: {}".format(str(e)))
            else:
                st.info("No subjects available to delete in this semester.")
            
            st.divider()
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

    # ================= ASSIGNMENT MANAGEMENT TAB =================
    with tabs[3]:
        st.title("📝 Assignment Management")
        
        # ========== CREATE NEW ASSIGNMENT ==========
        st.subheader("➕ Create New Assignment")

        sems_list_assign = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if sems_list_assign.empty:
            st.warning("Please create a semester first.")
        else:
            col1_assign, col2_assign = st.columns(2)
            
            with col1_assign:
                sem_name_assign = st.selectbox("Select Semester", sems_list_assign["name"], key="assign_sem")
                sem_id_assign = int(sems_list_assign[sems_list_assign["name"] == sem_name_assign]["id"].values[0])

                subjects_assign = pd.read_sql_query(
                    "SELECT * FROM subjects WHERE semester_id=?",
                    conn,
                    params=(sem_id_assign,)
                )

                if subjects_assign.empty:
                    st.warning("Please create a subject for this semester first.")
                    subject_selected = False
                else:
                    subject_options_assign = {
                        row['name']: row['id']
                        for _, row in subjects_assign.iterrows()
                    }
                    selected_subject_assign = st.selectbox("Select Subject", list(subject_options_assign.keys()))
                    sub_id_assign = int(subject_options_assign[selected_subject_assign])
                    subject_selected = True
            
            with col2_assign:
                title_assign = st.text_input("Assignment Title", placeholder="e.g., Design of Ogee Weir")
                deadline_assign = st.date_input("Deadline")
                
                # Rubric / Model Answer Input
                rubric_input = st.text_area(
                    "🎯 Marking Rubric / Model Answer", 
                    placeholder="Enter key steps, final values, or formulas you want the AI to check...",
                    help="The AI will use this specific key to grade submissions for this assignment."
                )
                
                file_assign = st.file_uploader("📎 Upload Assignment Question PDF (Optional)", type=["pdf"])

            if st.button("➕ Create Assignment", use_container_width=True, type="primary"):
                if not subject_selected:
                    st.error("Please select a subject.")
                elif not title_assign.strip():
                    st.error("Title cannot be empty.")
                else:
                    file_path_assign = ""
                    validation_passed = True

                    # 1. Handle File Upload & Validation
                    if file_assign:
                        is_valid, validation_msg = validate_file_upload(file_assign, ALLOWED_ASSIGNMENT_TYPES, MAX_FILE_SIZE_MB)
                        if not is_valid:
                            st.error(f"❌ File Validation Failed: {validation_msg}")
                            validation_passed = False
                        else:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_path_assign = f"assignment_files/{timestamp}_{file_assign.name.replace(' ', '_')}"
                            
                            success, result = safe_file_operation(
                                lambda: open(file_path_assign, "wb").write(file_assign.getbuffer())
                            )
                            
                            if not success:
                                st.error(f"❌ File Save Failed: {result}")
                                file_path_assign = ""
                                validation_passed = False

                    # 2. Database Insertion
                    if validation_passed:
                        try:
                            c.execute("""
                            INSERT INTO assignments(title, subject_id, deadline, question_file, rubric)
                            VALUES(?,?,?,?,?)
                            """, (title_assign.strip(), int(sub_id_assign), str(deadline_assign), file_path_assign, rubric_input.strip()))

                            conn.commit()
                            st.success(f"✅ Assignment '{title_assign.strip()}' created successfully!")
                            st.balloons()
                            st.rerun()

                        except Exception as e:
                            st.error(f"Database Error: {str(e)}")
                            # Cleanup file if database insert failed
                            if file_path_assign and os.path.exists(file_path_assign):
                                try:
                                    os.remove(file_path_assign)
                                except:
                                    pass

        st.divider()

        # ========== VIEW ASSIGNMENTS ==========
        st.subheader("📋 Existing Assignments")
        
        # Filter option
        view_sems_list = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not view_sems_list.empty:
            view_filter_sel = st.selectbox("Filter by Semester", ["All"] + view_sems_list["name"].tolist(), key="view_assign_filter")
            
            if view_filter_sel == "All":
                all_assignments_view = pd.read_sql_query("""
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
                filter_sem_id_view = int(view_sems_list[view_sems_list["name"] == view_filter_sel]["id"].values[0])
                all_assignments_view = pd.read_sql_query("""
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
                """, conn, params=(filter_sem_id_view,))

            if all_assignments_view.empty:
                st.info("No assignments created yet.")
            else:
                # Show table without file path
                st.dataframe(
                    all_assignments_view[['ID', 'Semester', 'Subject', 'Title', 'Deadline']],
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info("📊 Total Assignments: **{}**".format(len(all_assignments_view)))
                
                st.divider()
                
                # ========== ASSIGNMENT DETAILS WITH DELETE ==========
                st.subheader("📄 Assignment Details")
                
                for _, assignment_row in all_assignments_view.iterrows():
                    
                    # Get submission count
                    submission_count_view = pd.read_sql_query("""
                    SELECT COUNT(*) as count FROM submissions
                    WHERE assignment_id=?
                    """, conn, params=(assignment_row['ID'],)).iloc[0]['count']
                    
                    deadline_display_view = format_deadline_display(assignment_row['Deadline'])
                    
                    with st.expander("{} - {} - {} | {}".format(
                        assignment_row['Semester'],
                        assignment_row['Subject'],
                        assignment_row['Title'],
                        deadline_display_view
                    )):
                        
                        col_detail1_v, col_detail2_v = st.columns([2, 1])
                        
                        with col_detail1_v:
                            st.write("**Semester:** {}".format(assignment_row['Semester']))
                            st.write("**Subject:** {}".format(assignment_row['Subject']))
                            st.write("**Title:** {}".format(assignment_row['Title']))
                            st.write("**Deadline:** {}".format(assignment_row['Deadline']))
                            st.metric("📊 Total Submissions", submission_count_view)
                        
                        with col_detail2_v:
                            # Download assignment file
                            if assignment_row['File'] and os.path.exists(assignment_row['File']):
                                with open(assignment_row['File'], "rb") as f:
                                    st.download_button(
                                        "📥 Download Question",
                                        f,
                                        file_name=os.path.basename(assignment_row['File']),
                                        key="download_assign_{}".format(assignment_row['ID']),
                                        use_container_width=True
                                    )
                            else:
                                st.info("No file uploaded")
                        
                        st.divider()
                        
                        # ========== EDIT ASSIGNMENT ==========
                        with st.expander("✏️ Edit Assignment Details"):
                            
                            col_edit1_v, col_edit2_v = st.columns(2)
                            
                            with col_edit1_v:
                                new_title_v = st.text_input(
                                    "New Title",
                                    value=assignment_row['Title'],
                                    key="edit_title_{}".format(assignment_row['ID'])
                                )
                            
                            with col_edit2_v:
                                current_deadline_v = datetime.strptime(assignment_row['Deadline'], '%Y-%m-%d').date()
                                new_deadline_v = st.date_input(
                                    "New Deadline",
                                    value=current_deadline_v,
                                    key="edit_deadline_{}".format(assignment_row['ID'])
                                )
                            
                            if st.button("💾 Save Changes", key="save_edit_{}".format(assignment_row['ID']), type="primary"):
                                
                                if not new_title_v.strip():
                                    st.error("Title cannot be empty")
                                elif new_title_v == assignment_row['Title'] and str(new_deadline_v) == assignment_row['Deadline']:
                                    st.info("No changes made")
                                else:
                                    success_v, message_v = update_assignment(assignment_row['ID'], new_title_v, new_deadline_v)
                                    
                                    if success_v:
                                        st.success("✅ {}".format(message_v))
                                        st.rerun()
                                    else:
                                        st.error("❌ {}".format(message_v))
                        
                        # Delete button
                        col_del1_v, col_del2_v = st.columns([2, 1])
                        
                        with col_del1_v:
                            st.warning("⚠️ **Delete Assignment:** This will remove all student submissions for this assignment.")
                        
                        with col_del2_v:
                            if st.button("🗑️ Delete Assignment", key="delete_assign_{}".format(assignment_row['ID']), type="primary", use_container_width=True):
                                
                                try:
                                    # Delete all submissions first
                                    submissions_to_del = pd.read_sql_query("""
                                    SELECT submission_file FROM submissions
                                    WHERE assignment_id=?
                                    """, conn, params=(assignment_row['ID'],))
                                    
                                    # Delete submission files
                                    for _, sub_row_del in submissions_to_del.iterrows():
                                        if sub_row_del['submission_file'] and os.path.exists(sub_row_del['submission_file']):
                                            os.remove(sub_row_del['submission_file'])
                                    
                                    # Delete submissions from database
                                    c.execute("DELETE FROM submissions WHERE assignment_id=?", (assignment_row['ID'],))
                                    
                                    # Delete assignment file
                                    if assignment_row['File'] and os.path.exists(assignment_row['File']):
                                        os.remove(assignment_row['File'])
                                    
                                    # Delete assignment from database
                                    c.execute("DELETE FROM assignments WHERE id=?", (assignment_row['ID'],))
                                    
                                    conn.commit()
                                    st.success("✅ Assignment '{}' deleted successfully!".format(assignment_row['Title']))
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error("Error deleting assignment: {}".format(str(e)))

    # SUBMISSIONS & AI
    with tabs[4]:

        st.subheader("Student Submissions & AI Grading")

        # filter by semester
        sems_sub_ai = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

        if not sems_sub_ai.empty:
            selected_sem_sub = st.selectbox("Filter by Semester", ["All"] + sems_sub_ai["name"].tolist(), key="filter_sem")

            if selected_sem_sub == "All":
                df_sub = pd.read_sql_query("""
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
                sem_id_sub = int(sems_sub_ai[sems_sub_ai["name"] == selected_sem_sub]["id"].values[0])
                df_sub = pd.read_sql_query("""
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
                """, conn, params=(sem_id_sub,))
        else:
            df_sub = pd.DataFrame()

        if df_sub.empty:
            st.info("No submissions yet.")
        else:
            # Display summary
            st.dataframe(
                df_sub[["semester", "subject", "assignment", "username", "full_name", "submission_time", "marks"]],
                use_container_width=True,
                hide_index=True
            )
            st.divider()
            st.subheader("AI Grading Tool")

            rubric_manual = st.text_area("Enter Model Answer / Rubric for AI Grading (applies to all below)", height=150)
            
            for _, row_s in df_sub.iterrows():
                expander_title_s = "{} - {} ({})".format(row_s['username'], row_s['assignment'], row_s['subject'])
                
                with st.expander(expander_title_s):
                    col1_s, col2_s = st.columns([2, 1])

                    with col1_s:
                        st.write("**Student:** {} ({})".format(row_s['full_name'], row_s['username']))
                        st.write("**Semester:** {}".format(row_s['semester']))
                        st.write("**Subject:** {}".format(row_s['subject']))
                        st.write("**Assignment:** {}".format(row_s['assignment']))
                        st.write("**Submitted:** {}".format(row_s['submission_time']))

                        if row_s['marks'] and str(row_s['marks']).strip():
                            st.metric("Current Marks", "{}/10".format(row_s['marks']))
                        else:
                            st.info("Not graded yet")

                    with col2_s:
                        if row_s["submission_file"] and os.path.exists(row_s["submission_file"]):
                            with open(row_s["submission_file"], "rb") as f:
                                st.download_button(
                                    "Download Submission", 
                                    f,
                                    file_name=os.path.basename(row_s["submission_file"]),
                                    key="dl_{}".format(row_s['id'])
                                )
                    
                    st.divider()

                    # AI Grading 
                    if row_s["submission_file"] and os.path.exists(row_s["submission_file"]):
                        col_a_s, col_b_s = st.columns(2)
                            
                        with col_a_s:
                            if st.button("AI Grade", key="grade_{}".format(row_s['id'])):
                                if not rubric_manual.strip():
                                    st.warning("Please enter a rubric/model answer first")
                                else:
                                    with st.spinner("AI is grading..."):
                                        try:
                                            result_ai = vision_grade(row_s["submission_file"], rubric_manual)
                                            with st.expander("**AI Response:**", expanded=True):
                                                st.write(result_ai)

                                            #check if result contains error
                                            if result_ai and "Error" not in str(result_ai):
                                                marks_ai = extract_marks(result_ai)
                                                
                                                if marks_ai is not None:
                                                    c.execute(
                                                        "UPDATE submissions SET marks=?, ai_summary=? WHERE id=?",
                                                        (marks_ai, result_ai, row_s["id"])
                                                    )
                                                    conn.commit()
                                                    st.success("Updated marks: {}/10".format(marks_ai))
                                                    st.rerun()
                                                else:
                                                    st.warning("Could not extract marks from AI response.Please enter manually below")
                                                    st.info("Tip: Make sure AI response contains 'FINAL_MARKS: X/10'")
                                                    c.execute(
                                                        "UPDATE submissions SET ai_summary=? WHERE id=?",
                                                        (str(result_ai), int(row_s["id"]))
                                                    )
                                                    conn.commit()
                                            else:
                                                st.error("AI returned an error. Check the response above.")
                                        except Exception as e:
                                            st.error("Error during AI grading: {}".format(str(e)))
                                            import traceback 
                                            st.code(traceback.format_exc())
                        
                        with col_b_s:
                            # Manual grade override
                            default_marks_s = 0
                            if row_s['marks'] and str(row_s['marks']).strip():
                                try:
                                    default_marks_s = int(row_s['marks'])
                                except:
                                    default_marks_s = 0
                            
                            manual_marks_s = st.number_input(
                                "Or enter marks manually",
                                min_value=0,
                                max_value=10,
                                value=default_marks_s,
                                key="manual_{}".format(row_s['id'])
                            )
                            if st.button("Save Manual Marks", key="save_{}".format(row_s['id'])):
                                c.execute(
                                    "UPDATE submissions SET marks=? WHERE id=?",
                                    (manual_marks_s, row_s["id"])
                                )
                                conn.commit()
                                st.success("Marks updated to {}/10".format(manual_marks_s))
                                st.rerun()
                    
                    # Show previous AI summary if exists
                    if row_s['ai_summary'] and str(row_s['ai_summary']).strip():
                        with st.expander("Previous AI Feedback"):
                            st.write(row_s['ai_summary'])

    # ANALYTICS
    with tabs[5]: 
        st.title("📈 Performance Analytics")
        st.subheader("📊 Grade Statistics")
        
        sems_list_ana = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not sems_list_ana.empty:
            selected_sem_ana = st.selectbox("Select Semester", ["All"] + sems_list_ana["name"].tolist(), key="analytics_sem")
            
            # --- STEP 1: THE MASTER QUERY (Identifies every student and every assignment) ---
            master_query_ana = """
            SELECT 
                semesters.name as Semester,
                users.full_name as Student_Name,
                users.username as Username,
                subjects.name as Subject,
                assignments.title as Assignment,
                assignments.deadline as Deadline,
                submissions.marks as Marks,
                submissions.submission_time as Submission_Date,
                submissions.ai_summary as AI_Feedback
            FROM users
            CROSS JOIN assignments 
            JOIN subjects ON assignments.subject_id = subjects.id
            JOIN semesters ON subjects.semester_id = semesters.id
            LEFT JOIN submissions ON users.id = submissions.student_id AND assignments.id = submissions.assignment_id
            WHERE users.role = 'student' 
            AND users.semester_id = semesters.id
            """
            
            if selected_sem_ana != "All":
                raw_df_ana = pd.read_sql_query(master_query_ana + " AND semesters.name = ?", conn, params=(selected_sem_ana,))
            else:
                raw_df_ana = pd.read_sql_query(master_query_ana, conn)

            if not raw_df_ana.empty:
                # --- STEP 2: DATA PROCESSING (Assigning 0 for Negligence) ---
                processed_list_ana = []
                current_date_ana = datetime.now().date()

                for _, row_a in raw_df_ana.iterrows():
                    # 1. Standardize Inputs
                    deadline_date_a = datetime.strptime(str(row_a['Deadline']), '%Y-%m-%d').date()
                    
                    # Check if marks are valid
                    raw_marks_a = row_a['Marks']
                    has_marks_a = raw_marks_a is not None and str(raw_marks_a).lower() != 'nan' and str(raw_marks_a).strip() != ""
                    
                    # Check if submission date is actually there (Strict Check)
                    is_actually_submitted_a = not pd.isna(row_a['Submission_Date']) and str(row_a['Submission_Date']).strip() != ""

                    # 2. Determine Status and Marks
                    if is_actually_submitted_a:
                        status_a = "✅ Submitted"
                        final_score_a = raw_marks_a if has_marks_a else "Pending"
                    elif current_date_ana > deadline_date_a:
                        status_a = "🔴 MISSED"
                        final_score_a = 0  # Force 0 for negligence
                    else:
                        status_a = "🟡 Pending"
                        final_score_a = "TBD"

                    processed_list_ana.append({
                        "Semester": row_a['Semester'],
                        "Student_Name": row_a['Student_Name'],
                        "Username": row_a['Username'],
                        "Subject": row_a['Subject'],
                        "Assignment": row_a['Assignment'],
                        "Deadline": row_a['Deadline'],
                        "Marks": final_score_a,
                        "Status": status_a,
                        "AI_Feedback": row_a['AI_Feedback'] if row_a['AI_Feedback'] else "No Feedback"
                    })

                df_ana_proc = pd.DataFrame(processed_list_ana)
                # Helper for calculations
                df_ana_proc["numeric_marks"] = pd.to_numeric(df_ana_proc["Marks"], errors="coerce").fillna(0)

                # ========== DOWNLOAD OPTIONS ==========
                st.subheader("📥 Download Grade Reports")
                col1_dl, col2_dl, col3_dl = st.columns(3)
                
                with col1_dl:
                    csv_detailed_ana = df_ana_proc.to_csv(index=False).encode('utf-8')
                    st.download_button("📄 Detailed Report (With Feedbacks)", csv_detailed_ana, f"Detailed_{selected_sem_ana}.csv", 'text/csv', use_container_width=True)
                
                with col2_dl:
                    df_summary_ana = df_ana_proc[['Semester', 'Subject', 'Assignment', 'Student_Name', 'Username', 'Deadline', 'Status', 'Marks']]
                    st.download_button("📊 Summary Report (Incl. 0s)", df_summary_ana.to_csv(index=False).encode('utf-8'), f"Summary_{selected_sem_ana}.csv", 'text/csv', use_container_width=True)
                
                with col3_dl:
                    # Student-wise Summary (Pivot Table)
                    df_pivot_ana = df_ana_proc.pivot_table(index=['Semester', 'Student_Name', 'Username', 'Subject'], 
                                            columns='Assignment', values='numeric_marks', aggfunc='first').reset_index()
                    assign_cols_ana = [c_a for c_a in df_pivot_ana.columns if c_a not in ['Semester', 'Student_Name', 'Username', 'Subject']]
                    df_pivot_ana['Avg_Score'] = df_pivot_ana[assign_cols_ana].mean(axis=1).round(2)
                    st.download_button("📈 Student-wise Summary", df_pivot_ana.to_csv(index=False).encode('utf-8'), f"Student_Pivot_{selected_sem_ana}.csv", 'text/csv', use_container_width=True)

                st.divider()
                
                # ========== VISUALIZATIONS ==========
                st.subheader("📊 Average Marks by Assignment")
                avg_marks_ana = df_ana_proc.groupby("Assignment")["numeric_marks"].mean()
                st.bar_chart(avg_marks_ana)
                
                col_m1_a, col_m2_a, col_m3_a = st.columns(3)
                col_m1_a.metric("Total Expectations", len(df_ana_proc))
                col_m2_a.metric("Class Average", f"{df_ana_proc['numeric_marks'].mean():.2f}/10")
                col_m3_a.metric("Negligence Cases", len(df_ana_proc[df_ana_proc['Status'] == "🔴 MISSED"]))

                st.divider()
                st.subheader("📚 Subject-wise Performance")
                subject_stats_ana = df_ana_proc.groupby('Subject').agg({'numeric_marks': ['count', 'mean', 'min', 'max']}).round(2)
                subject_stats_ana.columns = ['Total Assignments', 'Avg Grade', 'Min', 'Max']
                st.dataframe(subject_stats_ana, use_container_width=True)

                st.divider()
                with st.expander("🔍 AI 'Common Error' Insight"):
                    target_assign_ana = st.selectbox("Select Assignment to Analyze Trends", df_ana_proc["Assignment"].unique()) 
                    if st.button("Analyze Class Trends"):
                        # Collect all feedback for this assignment
                        all_feedback_ana = " ".join(df_ana_proc[df_ana_proc["Assignment"] == target_assign_ana]["AI_Feedback"].astype(str))
                        with st.spinner("Analyzing common pitfalls..."):
                            trend_model_ana = genai.GenerativeModel('gemini-1.5-flash')
                            trend_prompt_ana = f"Summarize the top 3 most common technical errors in these civil engineering grading feedbacks: {all_feedback_ana}"
                            trend_res_ana = trend_model_ana.generate_content(trend_prompt_ana)
                            st.info(trend_res_ana.text)

                # --- STEP 3: CREATE HORIZONTAL STATUS BOARD ---
                st.divider()
                st.subheader("📋 Master Submission & Grade Board")
                
                if not df_ana_proc.empty:
                    # 1. Create a display string for each cell
                    def format_cell_ana(row_cell):
                        if row_cell['Status'] == "✅ Submitted":
                            return str(row_cell['Marks'])
                        elif row_cell['Status'] == "🔴 MISSED":
                            return "🔴 MISSED"
                        else:
                            return "🟡 Pending"

                    display_df_ana = df_ana_proc.copy()
                    display_df_ana['Display_Value'] = display_df_ana.apply(format_cell_ana, axis=1)

                    # 2. Pivot the table
                    status_pivot_ana = display_df_ana.pivot_table(
                        index=['Student_Name', 'Username', 'Subject'],
                        columns='Assignment',
                        values='Display_Value',
                        aggfunc='first'
                    ).reset_index()

                    # 3. Clean up column names and display
                    st.info("💡 **Legend:** Numeric value = Grade received | 🔴 MISSED = Deadline passed | 🟡 Pending = Due in future")
                    
                    st.dataframe(
                        status_pivot_ana, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config={
                            "Username": "Roll No",
                            "Student_Name": "Student Name"
                        }
                    )

                    # Show a summary count for the lecturer
                    total_missed_ana = len(df_ana_proc[df_ana_proc['Status'] == "🔴 MISSED"])
                    if total_missed_ana > 0:
                        st.warning(f"🚩 Total negligent instances detected: **{total_missed_ana}**")
                else:
                    st.info("No data available to generate the status board.")
        else:
            st.warning("⚠️ Please create semesters first.")

    # MANAGE STUDENTS
    with tabs[6]:
        
        st.subheader("⚠️ Emergency Fix for Existing Students")
        st.divider()
        
        # ========== SEARCH STUDENTS ==========
        st.subheader("🔍 Search Students")
        
        col_search1_st, col_search2_st = st.columns([2, 1])
        
        with col_search1_st:
            search_query_st = st.text_input(
                "Search by name or username",
                placeholder="e.g., John or john123",
                key="search_students_input"
            )
        
        with col_search2_st:
            sems_search_st = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            search_sem_filter_st = st.selectbox(
                "Filter by Semester",
                ["All"] + sems_search_st["name"].tolist(),
                key="search_sem_filter"
            )
        
        if search_query_st:
            sem_filter_id_st = None
            if search_sem_filter_st != "All":
                sem_filter_id_st = int(sems_search_st[sems_search_st["name"] == search_sem_filter_st]["id"].values[0])
            
            search_results_st = search_students(search_query_st, sem_filter_id_st)
            
            if search_results_st.empty:
                st.info("🔍 No students found matching '{}'".format(search_query_st))
            else:
                st.success("✅ Found {} student(s)".format(len(search_results_st)))
                st.dataframe(
                    search_results_st[['full_name', 'username', 'semester']],
                    use_container_width=True,
                    hide_index=True
                )

        if st.button("🔧 Fix ALL Students with NULL semester"):
            default_sem_fix = pd.read_sql_query("SELECT id FROM semesters ORDER BY id ASC LIMIT 1", conn)
            if not default_sem_fix.empty:
                default_sem_id_fix = int(default_sem_fix.iloc[0]['id'])
                c.execute("""
                UPDATE users 
                SET semester_id = ? 
                WHERE role = 'student' AND semester_id IS NULL
                """, (default_sem_id_fix,))
                conn.commit()
                affected_st = c.rowcount
                st.success("✅ Fixed {} students - assigned to semester_id {}".format(affected_st, default_sem_id_fix))
                st.rerun()
            else:
                st.error("No semesters available to assign")
        
        st.divider()
        st.subheader("Add Student Manually")

        col1_st, col2_st = st.columns(2)

        with col1_st:
            student_name_man = st.text_input("Full Name", key="student_name")
            username_man = st.text_input("Username", key="student_username")
            password_man = st.text_input("Password", type="password", key="student_password")

        with col2_st:
            sems_list_man = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)

            if sems_list_man.empty:
                st.warning("Please create semesters first.")
            else:
                semester_name_man = st.selectbox("Assign Semester", sems_list_man["name"], key="student_semester")
                semester_id_man = int(sems_list_man[sems_list_man["name"] == semester_name_man]["id"].values[0])
                
                st.info("Will assign semester_id: {}".format(semester_id_man))

                if st.button("Create Student"):
                    if not username_man or not password_man:
                        st.error("Username and password required.")
                    elif not student_name_man:
                        st.error("Full name is required.")
                    else:
                        try:
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(?, ?, ?, ?, ?)
                            """, (
                                student_name_man.strip(),
                                username_man.strip(),
                                hash_password(password_man.strip()),
                                "student",
                                int(semester_id_man)
                            ))
                            conn.commit()
                            st.success("✅ Student '{}' created!".format(username_man))
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already exists.")
                        except Exception as e:
                            st.error("Error creating student: {}".format(str(e)))

        st.divider()
        st.subheader("Bulk Upload Students via CSV")
        st.info("CSV format: name,username,password,semester")

        csv_file_st = st.file_uploader("Upload CSV", type=["csv"], key="student_csv")

        if csv_file_st:
            df_csv_st = pd.read_csv(csv_file_st)
            required_cols_st = {"name", "username", "password", "semester"}

            if not required_cols_st.issubset(df_csv_st.columns):
                st.error("CSV must contain columns: name, username, password, semester")
            else:
                if st.button("Upload Students"):
                    sems_list_bulk = pd.read_sql_query("SELECT * FROM semesters", conn)
                    success_count_st = 0
                    error_count_st = 0

                    for _, row_csv in df_csv_st.iterrows():
                        sem_match_st = sems_list_bulk[sems_list_bulk["name"] == row_csv["semester"]]

                        if sem_match_st.empty:
                            error_count_st += 1
                            continue

                        sem_id_bulk = int(sem_match_st["id"].values[0])

                        try:
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(?,?,?,?,?)
                            """, (
                                row_csv["name"],
                                row_csv["username"],
                                hash_password(str(row_csv["password"])),
                                "student",
                                int(sem_id_bulk)
                            ))
                            success_count_st += 1
                        except:
                            error_count_st += 1
                            continue

                    conn.commit()
                    st.success("{} students uploaded successfully. {} failed.".format(success_count_st, error_count_st))
                    st.rerun()

        st.divider()
        st.subheader("📋 Registered Student List")

        all_sems_list_view = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        filter_col1_st, filter_col2_st = st.columns([1, 2])
        
        with filter_col1_st:
            list_filter_st = st.selectbox("View Students by Semester", ["All"] + all_sems_list_view["name"].tolist(), key="view_filter")

        if list_filter_st == "All":
            students_df_view = pd.read_sql_query("""
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
            students_df_view = pd.read_sql_query("""
                SELECT 
                    users.id as ID,
                    users.full_name as Name, 
                    users.username as Username, 
                    semesters.name as Semester
                FROM users 
                JOIN semesters ON users.semester_id = semesters.id 
                WHERE users.role='student' AND semesters.name = ?
                ORDER BY users.full_name ASC
            """, conn, params=(list_filter_st,))

        if not students_df_view.empty:
            st.dataframe(
                students_df_view[['Name', 'Username', 'Semester']], 
                use_container_width=True, 
                hide_index=True
            )
            st.info(f"📊 Total Students: **{len(students_df_view)}**")
            csv_students_dl = students_df_view[['Name', 'Username', 'Semester']].to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download {list_filter_st} Student List (CSV)",
                data=csv_students_dl,
                file_name=f"Students_{list_filter_st}.csv",
                mime='text/csv',
                use_container_width=True
            )
        else:
            st.info("No students found.")

        st.divider()
        st.subheader("🗑️ Delete Student")

        if not students_df_view.empty:
            student_options_del_st = {
                "{} | {} | {}".format(
                    row_v['Semester'] if row_cell_v['Semester'] else 'No Semester', 
                    row_v['Username'], 
                    row_v['Name']
                ): row_v['ID']
                for _, row_v in students_df_view.iterrows()
            }

            selected_student_del_st = st.selectbox(
                "Select Student to Remove",
                list(student_options_del_st.keys()),
                key="delete_student_select"
            )

            col_del1_st, col_del2_st = st.columns([1, 3])
            
            with col_del1_st:
                if st.button("🗑️ Confirm Delete", type="primary", use_container_width=True):
                    student_id_del_f = student_options_del_st[selected_student_del_st]
                    try:
                        sub_files_st = pd.read_sql_query(
                            "SELECT submission_file FROM submissions WHERE student_id=?",
                            conn,
                            params=(int(student_id_del_f),)
                        )
                        deleted_files_st = 0
                        for _, row_f in sub_files_st.iterrows():
                            if row_f['submission_file'] and os.path.exists(row_f['submission_file']):
                                try:
                                    os.remove(row_f['submission_file'])
                                    deleted_files_st += 1
                                except:
                                    pass
                        c.execute("DELETE FROM submissions WHERE student_id=?", (int(student_id_del_f),))
                        c.execute("DELETE FROM users WHERE id=?", (int(student_id_del_f),))
                        conn.commit()
                        st.success("✅ Student removed! Deleted {} submission files.".format(deleted_files_st))
                        st.rerun()
                    except Exception as e:
                        st.error("Error deleting student: {}".format(str(e)))
            
            with col_del2_st:
                st.warning("⚠️ This action cannot be undone. All submissions will be deleted.")

        st.divider()
        st.subheader("🔧 Update Student Semester Assignment")

        all_students_st_up = pd.read_sql_query("""
        SELECT id, username, full_name, semester_id 
        FROM users 
        WHERE role='student'
        ORDER BY username ASC
        """, conn)

        if not all_students_st_up.empty:
            student_update_options_st = {
                "{} ({})".format(row_up['username'], row_up['full_name']): row_up['id']
                for _, row_up in all_students_st_up.iterrows()
            }
            
            col_up1_st, col_up2_st = st.columns(2)
            
            with col_up1_st:
                sel_st_up = st.selectbox(
                    "Select Student",
                    list(student_update_options_st.keys()),
                    key="update_student_select"
                )
            
            with col_up2_st:
                sems_list_up = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
                if not sems_list_up.empty:
                    new_sem_sel_up = st.selectbox(
                        "Assign to Semester",
                        sems_list_up["name"].tolist(),
                        key="update_semester_select"
                    )
                    if st.button("💾 Update Semester Assignment", use_container_width=True):
                        st_id_up = student_update_options_st[sel_st_up]
                        new_sem_id_up = int(sems_list_up[sems_list_up["name"] == new_sem_sel_up]["id"].values[0])
                        try:
                            c.execute(
                                "UPDATE users SET semester_id=? WHERE id=?",
                                (int(new_sem_id_up), int(st_id_up))
                            )
                            conn.commit()
                            st.success("✅ Student assigned to {} successfully!".format(new_sem_sel_up))
                            st.rerun()
                        except Exception as e:
                            st.error("Error updating: {}".format(str(e)))
                else:
                    st.warning("No semesters available.")

    # STUDY MATERIALS
    with tabs[7]:
        st.title("📚 Study Materials Management")
        st.subheader("📤 Upload New Study Material")
        
        col1_mat, col2_mat = st.columns(2)
        
        with col1_mat:
            sems_list_mat = pd.read_sql_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            if sems_list_mat.empty:
                st.warning("Please create semesters first.")
            else:
                mat_sem_name = st.selectbox("Select Semester", sems_list_mat["name"], key="material_semester")
                mat_sem_id = int(sems_list_mat[sems_list_mat["name"] == mat_sem_name]["id"].values[0])
                subjects_mat_list = pd.read_sql_query(
                    "SELECT * FROM subjects WHERE semester_id=?",
                    conn,
                    params=(mat_sem_id,)
                )
                if subjects_mat_list.empty:
                    st.warning("No subjects found.")
                    mat_sub_id = None
                else:
                    mat_sub_name = st.selectbox("Select Subject", subjects_mat_list["name"], key="material_subject")
                    mat_sub_id = int(subjects_mat_list[subjects_mat_list["name"] == mat_sub_name]["id"].values[0])
        
        with col2_mat:
            mat_title_input = st.text_input("Material Title", placeholder="e.g., Chapter 3")
            mat_desc_input = st.text_area("Description (Optional)")
        
        uploaded_file_mat = st.file_uploader("Upload File", type=["pdf", "docx", "pptx", "zip", "jpg", "png"])
        
        if st.button("📤 Upload Material", type="primary", use_container_width=True):
            if not mat_title_input.strip() or not uploaded_file_mat or mat_sub_id is None:
                st.error("⚠️ Fill required fields.")
            else:
                try:
                    ts_mat = datetime.now().strftime("%Y%m%d_%H%M%S")
                    ext_mat = uploaded_file_mat.name.split(".")[-1]
                    f_path_mat = f"study_materials/{ts_mat}_{mat_title_input.replace(' ', '_')}.{ext_mat}"
                    with open(f_path_mat, "wb") as f_m:
                        f_m.write(uploaded_file_mat.getbuffer())
                    if ext_mat.lower() == "pdf":
                        apply_watermark(f_path_mat)
                    c.execute("""
                    INSERT INTO study_materials(title, subject_id, semester_id, file_path, description, upload_date, uploaded_by)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """, (mat_title_input.strip(), int(mat_sub_id), int(mat_sem_id), f_path_mat, mat_desc_input.strip(), str(datetime.now()), int(st.session_state.user_id)))
                    conn.commit()
                    st.success("✅ Uploaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        st.divider()
        st.subheader("📋 Uploaded Study Materials")
        
        view_filter_mat = st.selectbox("Filter", ["All"] + sems_list_mat["name"].tolist(), key="filter_materials_sem")
        if view_filter_mat == "All":
            mats_df_view = pd.read_sql_query("""
            SELECT study_materials.id, study_materials.title, subjects.name as subject, semesters.name as semester, study_materials.description, study_materials.file_path, study_materials.upload_date
            FROM study_materials
            JOIN subjects ON study_materials.subject_id = subjects.id
            JOIN semesters ON study_materials.semester_id = semesters.id
            ORDER BY study_materials.upload_date DESC
            """, conn)
        else:
            v_sem_id_mat = int(sems_list_mat[sems_list_mat["name"] == view_filter_mat]["id"].values[0])
            mats_df_view = pd.read_sql_query("""
            SELECT study_materials.id, study_materials.title, subjects.name as subject, semesters.name as semester, study_materials.description, study_materials.file_path, study_materials.upload_date
            FROM study_materials
            JOIN subjects ON study_materials.subject_id = subjects.id
            JOIN semesters ON study_materials.semester_id = semesters.id
            WHERE study_materials.semester_id = ?
            ORDER BY study_materials.upload_date DESC
            """, conn, params=(v_sem_id_mat,))
        
        for _, mat_r in mats_df_view.iterrows():
            with st.expander(f"{mat_r['subject']} - {mat_r['title']}"):
                col_ma, col_mb = st.columns([3, 1])
                with col_ma:
                    st.write(f"**Semester:** {mat_r['semester']} | **Uploaded:** {mat_r['upload_date']}")
                    if mat_r['description']: st.write(mat_r['description'])
                with col_mb:
                    if os.path.exists(mat_r['file_path']):
                        with open(mat_r['file_path'], "rb") as f_dl:
                            st.download_button("📥 Download", f_dl, file_name=os.path.basename(mat_r['file_path']), key=f"dl_m_{mat_r['id']}")
                    if st.button("🗑️ Delete", key=f"del_m_{mat_r['id']}"):
                        if os.path.exists(mat_r['file_path']): os.remove(mat_r['file_path'])
                        c.execute("DELETE FROM study_materials WHERE id=?", (mat_r['id'],))
                        conn.commit()
                        st.rerun()

    # STORAGE MANAGEMENT
    with tabs[8]:
        st.title("💾 Storage & File Management")
        st.divider()
        stats_s = get_storage_stats()
        if stats_s:
            cols_s = st.columns(len(stats_s))
            ts_s = 0
            for idx_s, (lbl_s, d_s) in enumerate(stats_s.items()):
                cols_s[idx_s].metric(lbl_s, f"{d_s['size_mb']} MB", f"{d_s['file_count']} files")
                ts_s += d_s['size_mb']
            st.metric("📦 Total Storage", f"{round(ts_s, 2)} MB")
        
        if st.button("🧹 Scan & Clean Orphaned Files"):
            d_s, f_s = cleanup_orphaned_files()
            st.success(f"Cleaned {d_s} files ({f_s} MB).")
            st.rerun()
        
        st.divider()
        st.subheader("💾 Database Backup & Restore")
        if st.button("📦 Create Backup Now"):
            s_b, m_b = create_database_backup()
            if s_b: st.success(m_b)
            else: st.error(m_b)
        
        b_list = get_backup_list()
        if b_list:
            b_opts = {f"{b['date']} ({b['size_kb']} KB)": b['path'] for b in b_list}
            sel_b = st.selectbox("Select backup to restore", list(b_opts.keys()))
            if st.button("⚠️ Restore Database"):
                s_r, m_r = restore_database_from_backup(b_opts[sel_b])
                if s_r: st.success(m_r)
                else: st.error(m_r)

    # STUDENT PROFILES
    with tabs[9]:
        st.title("👤 Student Profile Viewer")
        all_st_p = pd.read_sql_query("SELECT users.id, users.username, users.full_name, semesters.name as semester FROM users LEFT JOIN semesters ON users.semester_id = semesters.id WHERE users.role='student' ORDER BY users.username ASC", conn)
        if not all_st_p.empty:
            sel_p = st.selectbox("Select Student", [f"{r_p['username']} ({r_p['full_name']})" for _, r_p in all_st_p.iterrows()])
            st_id_p = all_st_p.iloc[0]['id'] # Basic placeholder logic
            prof = get_student_profile(st_id_p)
            if prof:
                st.write(f"### {prof['info']['full_name']}")
                st.write(prof['stats'])
                st.dataframe(prof['submissions'], use_container_width=True)

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs_st = st.tabs(["Assignments","Study Materials", "My Results"])

    # ================= ASSIGNMENTS =================
    with tabs_st[0]:
        st.title("📝 My Assignments")

        student_info_st = pd.read_sql_query(
            "SELECT semester_id, username FROM users WHERE id=?",
            conn,
            params=(int(st.session_state.user_id),)
        )

        if student_info_st.empty:
            st.error("Student record not found.")
            st.stop()

        sem_id_st_raw = student_info_st.iloc[0]["semester_id"]

        if sem_id_st_raw is None or str(sem_id_st_raw).strip() == "":
            st.warning("You are not assigned to a semester. Please Contact your Lecturer")
            st.stop()

        sem_id_st = int(sem_id_st_raw)
        ann_st = get_announcements_for_semester(sem_id_st)
        
        if not ann_st.empty:
            st.subheader("📢 Announcements")
            for _, a_r in ann_st.iterrows():
                st.info(f"**{a_r['title']}**: {a_r['message']}")
            st.divider()

        all_assign_st = pd.read_sql_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=?
        ORDER BY assignments.deadline ASC
        """, conn, params=(sem_id_st,))

        if all_assign_st.empty:
            st.info("📭 No assignments available.")
        else:
            for _, row_a_s in all_assign_st.iterrows():
                deadline_d_s = format_deadline_display(row_a_s['deadline'])
                with st.expander(f"{row_a_s['subject']} - {row_a_s['title']} | {deadline_d_s}"):
                    if row_a_s["question_file"] and os.path.exists(row_a_s["question_file"]):
                        with open(row_a_s["question_file"], "rb") as f_q:
                            st.download_button("📥 Download Question", f_q, file_name=os.path.basename(row_a_s["question_file"]), key=f"dl_q_{row_a_s['id']}")
                    
                    exist_sub = pd.read_sql_query("SELECT * FROM submissions WHERE assignment_id=? AND student_id=?", conn, params=(int(row_a_s["id"]), int(st.session_state.user_id)))
                    
                    if not exist_sub.empty:
                        st.success(f"✅ Submitted on {exist_sub.iloc[0]['submission_time']}")
                        if exist_sub.iloc[0]['marks']: st.metric("Marks", f"{exist_sub.iloc[0]['marks']}/10")
                    else:
                        is_late_s, _ = check_deadline_passed(row_a_s['deadline'])
                        if is_late_s:
                            st.error("🔒 Deadline passed.")
                        else:
                            up_s = st.file_uploader("Upload Answer PDF", type=["pdf"], key=f"up_{row_a_s['id']}")
                            if st.button("Submit Assignment", key=f"btn_{row_a_s['id']}"):
                                if up_s:
                                    ts_s = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    f_p_s = f"submission_files/{st.session_state.username}_{row_a_s['id']}_{ts_s}.pdf"
                                    with open(f_p_s, "wb") as f_out: f_out.write(up_s.getbuffer())
                                    c.execute("INSERT INTO submissions(assignment_id, student_id, submission_time, submission_file, marks, ai_summary) VALUES(?,?,?,?,?,?)",
                                              (int(row_a_s["id"]), int(st.session_state.user_id), str(datetime.now()), f_p_s, "", ""))
                                    conn.commit()
                                    st.success("Submitted!")
                                    st.rerun()

    # ================= STUDY MATERIALS =================
    with tabs_st[1]:
        st.title("📚 Study Materials")
        mat_st = pd.read_sql_query("SELECT study_materials.*, subjects.name as subject FROM study_materials JOIN subjects ON study_materials.subject_id = subjects.id WHERE study_materials.semester_id = ? ORDER BY subjects.name ASC", conn, params=(sem_id_st,))
        if mat_st.empty:
            st.info("No materials.")
        else:
            for _, m_r in mat_st.iterrows():
                with st.expander(f"{m_r['subject']} - {m_r['title']}"):
                    if os.path.exists(m_r['file_path']):
                        with open(m_r['file_path'], "rb") as f_m_st:
                            st.download_button("📥 Download", f_m_st, file_name=os.path.basename(m_r['file_path']), key=f"st_dl_{m_r['id']}")

    # ================= RESULTS =================
    with tabs_st[2]:
        st.subheader("📝 My Academic Performance Record")
        q_res = """
        SELECT subjects.name as Subject, assignments.title as Assignment, assignments.deadline as Deadline, submissions.marks as Marks, submissions.submission_time as Submitted_On
        FROM assignments
        INNER JOIN subjects ON assignments.subject_id = subjects.id
        LEFT JOIN submissions ON assignments.id = submissions.assignment_id AND submissions.student_id = ?
        WHERE subjects.semester_id = ?
        ORDER BY assignments.deadline DESC
        """
        try:
            res_df_st = pd.read_sql_query(q_res, conn, params=(int(st.session_state.user_id), sem_id_st))
            if res_df_st.empty:
                st.info("No results.")
            else:
                st.dataframe(res_df_st, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error: {e}")
