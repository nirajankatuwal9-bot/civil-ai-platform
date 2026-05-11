
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


try:
    # Fetch the connection string from Streamlit Secrets
    DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL"))
    
    if not DATABASE_URL:
        st.error("🚨 DATABASE_URL not found in Streamlit Secrets!")
        st.stop()

    # Connect using the URL
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    c = conn.cursor()
    
except Exception as e:
    conn.rollback()
    st.error(f"🚨 Database Connection Failed: {e}")
    st.stop()
# ================= SAFE DATABASE EXECUTION =================

def db_execute(query, params=None):
    try:
        c.execute(query, params)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)


def db_query(query, params=None):
    try:
        return pd. read_sQl_query(query, conn, params=params)
    except Exception as e:
        conn.rollback()
        st.error(f"Database Error: {e}")
        return pd.DataFrame()
# USERS
try:
    success,erro = db_execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        full_name TEXT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        semester_id INTEGER
    )
    """)
    
except:
    conn.rollback()

# Safe auto-migration for existing users table
try:
    success,erro = db_execute("ALTER TABLE users ADD COLUMN email TEXT")
    conn.commit()
except:
    conn.rollback()

# SEMESTERS
try:
    success,erro = db_execute("""
    CREATE TABLE IF NOT EXISTS semesters(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )
    """)
    
except:
    conn.rollback()

# SUBJECTS
try:
    success,erro = db_execute("""
    CREATE TABLE IF NOT EXISTS subjects(
        id SERIAL PRIMARY KEY,
        name TEXT,
        semester_id INTEGER
    )
    """)
    
except:
    conn.rollback()

# ASSIGNMENTS
try:
    success,erro = db_execute("""
    CREATE TABLE IF NOT EXISTS assignments(
        id SERIAL PRIMARY KEY,
        title TEXT,
        subject_id INTEGER,
        deadline TEXT,
        question_file TEXT,
        rubric TEXT
    )
    """)
    
except:
    conn.rollback()

# Safe auto-migration for rubric column
try:
    success,erro = db_execute("ALTER TABLE assignments ADD COLUMN rubric TEXT")
    conn.commit()
except:
    conn.rollback()

# SUBMISSIONS
try:
    success,erro = db_execute("""
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
    
except:
    conn.rollback()

# STUDY MATERIALS
try:
    success,erro = db_execute("""
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
    
except:
    conn.rollback()

# ANNOUNCEMENTS
try:
    success,erro = db_execute("""
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
    
except:
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

admin_exists = db_query(
    "SELECT * FROM users WHERE username='admin'",
    
)

if admin_exists.empty:
    success,erro = db_execute("""
    INSERT INTO users(full_name, username, password, role, semester_id)
    VALUES(%s,%s,%s,%s,%s)
    """, (
        "Administrator",
        "admin",
        hash_password("admin123"),
        "lecturer",
        None
    ))
    

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

    with st.container(border=True):
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")

        if st.button("Enter the Flow"):

            try:
                # 🔥 IMPORTANT FOR POSTGRESQL
                conn.rollback()   # Clears any failed transaction state
            except:
                pass

            try:
                res = db_query(
                    "SELECT * FROM users WHERE username=%s",
                    (user,)
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

            except Exception as e:
                conn.rollback()
                st.error(f"Login error: {e}")

        st.stop()

# ================= SAFE DATABASE EXECUTION =================

def db_execute(query, params=None):
    """
    Safe execution for INSERT, UPDATE, DELETE
    Automatically commits or rollbacks.
    """
    try:
        success,erro = c.execute(query, params)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)


def db_query(query, params=None):
    """
    Safe execution for SELECT queries.
    Returns pandas DataFrame.
    """
    try:
        return db_query(query, conn, params=params)
    except Exception as e:
        conn.rollback()
        st.error(f"Database Error: {e}")
        return pd.DataFrame()
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
                    success,erro = db_execute(f"DROP TABLE IF EXISTS {t} CASCADE")
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
        success,erro = db_execute("""
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
        df = db_query("""
        SELECT announcements.*, users.full_name as author, semesters.name as semester
        FROM announcements
        LEFT JOIN users ON announcements.created_by = users.id
        LEFT JOIN semesters ON announcements.semester_id = semesters.id
        WHERE announcements.semester_id=%s OR announcements.semester_id IS NULL
        ORDER BY announcements.created_at DESC
        """, conn, params=(int(semester_id),))
    else:
        df = db_query("""
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
        df = db_query("SELECT email FROM users WHERE role='student' AND semester_id=%s AND email IS NOT NULL AND email != ''", conn, params=(int(target_semester_id),))
    else:
        df = db_query("SELECT email FROM users WHERE role='student' AND email IS NOT NULL AND email != ''", conn)
    
    emails = df['email'].tolist()
    if not emails:
        return False, "No valid student emails found."

    SENDER_EMAIL = st.secrets["EMAIL_USER"]
    APP_PASSWORD = st.secrets["EMAIL_PASSWORD"]

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
    
    assignments = db_query("SELECT question_file FROM assignments WHERE question_file IS NOT NULL AND question_file != ''", conn)
    for _, row in assignments.iterrows():
        if row['question_file']:
            db_files.add(row['question_file'])
    
    submissions = db_query("SELECT submission_file FROM submissions WHERE submission_file IS NOT NULL AND submission_file != ''", conn)
    for _, row in submissions.iterrows():
        if row['submission_file']:
            db_files.add(row['submission_file'])
    
    materials = db_query("SELECT file_path FROM study_materials WHERE file_path IS NOT NULL AND file_path != ''", conn)
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
        results = db_query("""
        SELECT users.id, users.full_name, users.username, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student' 
        AND users.semester_id=%s
        AND (LOWER(users.full_name) LIKE %s OR LOWER(users.username) LIKE %s)
        ORDER BY users.full_name ASC
        """, conn, params=(semester_id, '%{}%'.format(query), '%{}%'.format(query)))
    else:
        results = db_query("""
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
    
    results = db_query("""
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
        success,erro = db_execute("""
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
        student_info = db_query("""
        SELECT users.*, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.id=%s
        """, conn, params=(int(student_id),))
        
        if student_info.empty:
            return None
        
        submissions = db_query("""
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
                if "name" in sems_ann.columns:
                    ann_sem_options = ["All Semesters"] + sems_ann["name"].tolist()
                else:
                    ann_sem_options = ["All Semesters"]
                    ann_sem = st.selectbox("Target Audience", ann_sem_options, key="ann_sem")
                
            
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
        
        all_assignments = db_query("""
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
                        submissions = db_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s", conn, params=(assign['id'],))
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
                total_submissions = db_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s", conn, params=(assignment['id'],)).iloc[0]['count']
                deadline_display = format_deadline_display(assignment['deadline'])
                with st.expander("{} - {} | {}".format(assignment['subject'], assignment['title'], deadline_display)):
                    col_a, col_b = st.columns(2)
                    with col_a: st.metric("Total Submissions", total_submissions)
                    with col_b:
                        graded = db_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s AND marks IS NOT NULL AND marks != ''", conn, params=(assignment['id'],)).iloc[0]['count']
                        st.metric("Graded", graded)

        # SEMESTERS
    with tabs[1]:
        st.title("🎓 Semesters")
        
        # 1. Use a Form to guarantee Streamlit captures the text input
        with st.form("add_semester_form"):
            name = st.text_input("New Semester Name")
            submitted = st.form_submit_button("➕ Add Semester", type="primary")
            
            if submitted:
                if not name.strip():
                    st.error("Semester name cannot be empty.")
                else:
                    try:
                        # Create a fresh cursor to avoid stale state
                        cur = conn.cursor()
                        cur.execute("INSERT INTO semesters(name) VALUES(%s)", (name.strip(),))
                        conn.commit()
                        cur.close()
                        st.success(f"✅ Semester '{name.strip()}' Added Successfully!")
                        st.rerun()
                    except psycopg2.IntegrityError:
                        conn.rollback()
                        st.warning("⚠️ Semester already exists.")
                    except Exception as e:
                        conn.rollback()
                        # This will show us EXACTLY why it's failing if it's a connection issue
                        st.error(f"🚨 Database Error: {e}")
        
        st.divider()
        st.subheader("📋 Existing Semesters")
        
        try:
            df_sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            st.dataframe(df_sems, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Error loading semesters: {e}")
            
        st.divider()
        st.subheader("🗑️ Delete Semester")
        # (Keep your existing delete semester logic here if you have it, or add it back)

    # SUBJECTS
    with tabs[2]:
        st.title("📚 Subject Management")
        sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
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
                        success,erro = db_execute("INSERT INTO subjects(name,semester_id) VALUES(%s,%s)", (sub.strip(), int(sem_id)))
                        conn.commit()
                        st.success("✅ Subject '{}' added to {}".format(sub.strip(), sem))
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("Error adding subject: {}".format(str(e)))
            
            st.divider()
            st.subheader("📋 Subjects for: {}".format(sem))
            subjects_for_sem = db_query("SELECT * FROM subjects WHERE semester_id=%s ORDER BY name ASC", conn, params=(int(sem_id),))
            
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
                            assignment_ids = db_query("SELECT id FROM assignments WHERE subject_id=%s", conn, params=(int(subject_id),))
                            for _, row in assignment_ids.iterrows():
                                success,erro = db_execute("DELETE FROM submissions WHERE assignment_id=%s", (row["id"],))
                            success,erro = db_execute("DELETE FROM assignments WHERE subject_id=%s", (int(subject_id),))
                            materials = db_query("SELECT file_path FROM study_materials WHERE subject_id=%s", conn, params=(int(subject_id),))
                            for _, mat in materials.iterrows():
                                if mat['file_path'] and os.path.exists(mat['file_path']): os.remove(mat['file_path'])
                            success,erro = db_execute("DELETE FROM study_materials WHERE subject_id=%s", (int(subject_id),))
                            success,erro = db_execute("DELETE FROM subjects WHERE id=%s", (int(subject_id),))
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
                all_subjects_debug = db_query("""
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
        sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if sems.empty:
            st.warning("Please create a semester first.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                sem_name = st.selectbox("Select Semester", sems["name"], key="assign_sem")
                sem_id = int(sems[sems["name"] == sem_name]["id"].values[0])
                subjects = db_query("SELECT * FROM subjects WHERE semester_id=%s", conn, params=(sem_id,))
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
                        success,erro = db_execute("""
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
        view_sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not view_sems.empty:
            view_filter = st.selectbox("Filter by Semester", ["All"] + view_sems["name"].tolist(), key="view_assign_filter")
            if view_filter == "All":
                all_assignments = db_query("""
                SELECT assignments.id as ID, assignments.title as Title, subjects.name as Subject, semesters.name as Semester, assignments.deadline as Deadline, assignments.question_file as File
                FROM assignments JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY assignments.deadline DESC
                """, conn)
            else:
                filter_sem_id = int(view_sems[view_sems["name"] == view_filter]["id"].values[0])
                all_assignments = db_query("""
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
                    submission_count = db_query("SELECT COUNT(*) as count FROM submissions WHERE assignment_id=%s", conn, params=(assignment['ID'],)).iloc[0]['count']
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
                                    submissions = db_query("SELECT submission_file FROM submissions WHERE assignment_id=%s", conn, params=(assignment['ID'],))
                                    for _, sub in submissions.iterrows():
                                        if sub['submission_file'] and os.path.exists(sub['submission_file']): os.remove(sub['submission_file'])
                                    success,erro = db_execute("DELETE FROM submissions WHERE assignment_id=%s", (assignment['ID'],))
                                    if assignment['File'] and os.path.exists(assignment['File']): os.remove(assignment['File'])
                                    success,erro = db_execute("DELETE FROM assignments WHERE id=%s", (assignment['ID'],))
                                    conn.commit()
                                    st.success("✅ Assignment '{}' deleted successfully!".format(assignment['Title']))
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error("Error deleting assignment: {}".format(str(e)))

    # SUBMISSIONS & AI
    with tabs[4]:
        st.subheader("Student Submissions & AI Grading")
        sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems.empty:
            selected_sem = st.selectbox("Filter by Semester", ["All"] + sems["name"].tolist(), key="filter_sem")
            if selected_sem == "All":
                df = db_query("""
                SELECT submissions.id, users.username, users.full_name, semesters.name as semester, subjects.name as subject, assignments.title as assignment, assignments.rubric, submissions.submission_time, submissions.submission_file, submissions.marks, submissions.ai_summary
                FROM submissions JOIN users ON submissions.student_id = users.id JOIN assignments ON submissions.assignment_id = assignments.id JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id
                ORDER BY submissions.submission_time DESC
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = db_query("""
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
                                                    success,erro = db_execute("UPDATE submissions SET marks=%s, ai_summary=%s WHERE id=%s", (marks, result, row["id"]))
                                                    conn.commit()
                                                    st.success("Updated marks: {}/10".format(marks))
                                                    st.rerun()
                                                else:
                                                    st.warning("Could not extract marks from AI response.Please enter manually below")
                                                    success,erro = db_execute("UPDATE submissions SET ai_summary=%s WHERE id=%s", (str(result), int(row["id"])))
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
                                success,erro = db_execute("UPDATE submissions SET marks=%s WHERE id=%s", (manual_marks, row["id"]))
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
        trend_data = db_query("""
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
        sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        if not sems.empty:
            selected_sem = st.selectbox("Select Semester", ["All"] + sems["name"].tolist(), key="analytics_sem")
            if selected_sem == "All":
                df = db_query("""
                SELECT semesters.name as Semester, subjects.name as Subject, assignments.title as Assignment, users.full_name as Student_Name, users.username as Username, submissions.submission_time as Submission_Date, assignments.deadline as Deadline, submissions.marks as Marks, submissions.ai_summary as AI_Feedback
                FROM submissions JOIN assignments ON submissions.assignment_id=assignments.id JOIN subjects ON assignments.subject_id = subjects.id JOIN semesters ON subjects.semester_id = semesters.id JOIN users ON submissions.student_id = users.id
                WHERE submissions.marks IS NOT NULL AND submissions.marks != ''
                ORDER BY semesters.name, subjects.name, assignments.title, users.full_name
                """, conn)
            else:
                sem_id = int(sems[sems["name"] == selected_sem]["id"].values[0])
                df = db_query("""
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
        
        # TEMPORARY FIX BUTTON - Remove after fixing all students
        st.subheader("⚠️ Emergency Fix for Existing Students")
        
        if st.button("🔧 Fix ALL Students with NULL semester"):
            # Get first semester as default
            default_sem = db_query("SELECT id FROM semesters ORDER BY id ASC LIMIT 1", conn)
            
            if not default_sem.empty:
                default_sem_id = int(default_sem.iloc[0]['id'])
                
                try:
                    # Update all students with NULL semester_id
                    c.execute("""
                    UPDATE users 
                    SET semester_id = %s 
                    WHERE role = 'student' AND semester_id IS NULL
                    """, (default_sem_id,))
                    
                    conn.commit()
                    affected = c.rowcount
                    st.success("✅ Fixed {} students - assigned to semester_id {}".format(affected, default_sem_id))
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error("Error fixing students: {}".format(str(e)))
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
            sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)

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
                            VALUES(%s, %s, %s, %s, %s)
                            """, (
                                student_name.strip(),
                                username.strip(),
                                hash_password(password.strip()),
                                "student",
                                semester_id_to_insert
                            ))
                            conn.commit()
                            
                            # Verify insertion
                            verify = db_query(
                                "SELECT * FROM users WHERE username=%s",
                                conn,
                                params=(username.strip(),)
                            )
                            
                            if not verify.empty:
                                st.success("✅ Student '{}' created!".format(username))
                                st.write("**Verification:** semester_id saved as: {}".format(verify.iloc[0]['semester_id']))
                                st.rerun()
                            else:
                                st.error("Student created but verification failed")
                                
                        except psycopg2.IntegrityError:
                            conn.rollback()
                            st.error("Username already exists.")
                        except Exception as e:
                            conn.rollback()
                            st.error("Error creating student: {}".format(str(e)))
                            import traceback
                            st.code(traceback.format_exc())

        st.divider()

        st.subheader("Bulk Upload Students via CSV")
        st.info("CSV format: name,username,password,semester")

        csv_file = st.file_uploader("Upload CSV", type=["csv"], key="student_csv")

        if csv_file:
            df_csv = pd.read_csv(csv_file)

            #1. clean the headers instantly 
            df_csv.columns=df_csv.columns.str.strip().str.lower()
            required_cols = {"name", "username", "password", "semester"}

            if not required_cols.issubset(df_csv.columns):
                st.error("CSV must contain columns: Name, Username, password, Semester")
                st.write("Your columns are currently reading as:", list(df_csv.columns))
            else:
                st.write("🔍 Data Preview:", df_csv.head())
                if st.button("🚀 Process & Register Students"):
                    sems = db_query("SELECT * FROM semesters", conn)
                    success_count = 0
                    error_count = 0

                    for _, row in df_csv.iterrows():
                        clean_name = str(row["name"]).strip()
                        clean_user = str(row["username"]).strip()
                        clean_sem = str(row["semester"]).strip()

                        raw_pw = str(row["password"]).replace('.0', '').strip()
                        
                        sem_match = sems[sems["name"] == clean_sem]

                        if sem_match.empty:
                            st.warning(f"⚠️ Semester '{clean_sem}' not found for user {clean_user}. Skipping.")
                            error_count += 1
                            continue

                        sem_id = int(sem_match["id"].values[0])

                        try:
                            c.execute("""
                            INSERT INTO users(full_name, username, password, role, semester_id)
                            VALUES(%s,%s,%s,%s,%s)
                            """, (
                                clean_name,
                                clean_user,
                                hash_password(raw_pw),
                                "student",
                                int(sem_id)
                            ))
                            conn.commit()
                            success_count += 1
                        except Exception as e:
                            conn.rollback()
                            error_count += 1
                            continue

                    st.success("{} students uploaded successfully. {} failed.".format(success_count, error_count))
                    st.rerun()

        st.divider()
        st.subheader("📋 Registered Student List")

        # 1. Filter Dropdown for Sorting/Viewing
        all_sems_list = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        filter_col1, filter_col2 = st.columns([1, 2])
        
        with filter_col1:
            list_filter = st.selectbox("View Students by Semester", ["All"] + all_sems_list["name"].tolist(), key="view_filter")

        # 2. Build Query: Sorted by Semester, then Alphabetically by Name
        if list_filter == "All":
            students_df = db_query("""
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
            students_df = db_query("""
                SELECT 
                    users.id as ID,
                    users.full_name as Name, 
                    users.username as Username, 
                    semesters.name as Semester
                FROM users 
                JOIN semesters ON users.semester_id = semesters.id 
                WHERE users.role='student' AND semesters.name = %s
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
                        c.execute("DELETE FROM submissions WHERE student_id=%s", (int(student_id),))
                        # Then delete user
                        c.execute("DELETE FROM users WHERE id=%s", (int(student_id),))
                        conn.commit()
                        
                        st.success("✅ Student removed successfully!")
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        st.error("Error deleting student: {}".format(str(e)))
            
            with col_del2:
                st.warning("⚠️ This action cannot be undone. All submissions will be deleted.")

        else:
            st.info("No students to delete.")

        st.divider()
        st.subheader("🔧 Update Student Semester Assignment")

        # Get all students for semester update
        all_students = db_query("""
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
                sems_update = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
                
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
                                "UPDATE users SET semester_id=%s WHERE id=%s",
                                (int(new_sem_id), int(student_id_update))
                            )
                            conn.commit()
                            
                            st.success("✅ Student assigned to {} successfully!".format(new_semester))
                            st.rerun()
                            
                        except Exception as e:
                            conn.rollback()
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
            sems_material = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
            
            if sems_material.empty:
                st.warning("Please create semesters first.")
            else:
                material_semester = st.selectbox("Select Semester", sems_material["name"], key="material_semester")
                material_sem_id = int(sems_material[sems_material["name"] == material_semester]["id"].values[0])
                
                # Get subjects for selected semester
                subjects_material = db_query(
                    "SELECT * FROM subjects WHERE semester_id=%s",
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
                    VALUES(%s, %s, %s, %s, %s, %s, %s)
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
                    conn.rollback()
                    st.error("Error uploading material: {}".format(str(e)))
        
        st.divider()
        
        # ========== VIEW/MANAGE MATERIALS ==========
        st.subheader("📋 Uploaded Study Materials")
        
        # Filter by semester
        filter_sems = db_query("SELECT * FROM semesters ORDER BY name ASC", conn)
        
        if not filter_sems.empty:
            filter_semester = st.selectbox(
                "Filter by Semester", 
                ["All"] + filter_sems["name"].tolist(), 
                key="filter_materials_sem"
            )
            
            # Query materials
            if filter_semester == "All":
                materials_df = db_query("""
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
                materials_df = db_query("""
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
                WHERE study_materials.semester_id = %s
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
                                    c.execute("DELETE FROM study_materials WHERE id=%s", (material['id'],))
                                    conn.commit()
                                    
                                    st.success("✅ Material deleted!")
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error("Error deleting: {}".format(str(e)))
                                    
        # STORAGE MANAGEMENT
    with tabs[8]:
        
        st.title("💾 Storage & File Management")
        st.markdown("---")
        st.markdown("""
        <div style='background-color: #f0f8ff; padding: 15px; border-radius: 10px; border-left: 4px solid #004b87;'>
            <h4 style='color: #004b87; margin-top: 0;'>🌊 The N-Streamlines Storage Monitor</h4>
            <p style='color: #555; margin-bottom: 0;'>Keep your platform clean and optimized</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Get storage stats
        stats = get_storage_stats()
        
        # ========== STORAGE USAGE OVERVIEW ==========
        st.subheader("📊 Current Storage Usage")
        
        if stats:
            cols = st.columns(len(stats))
            
            total_size = 0
            total_files = 0
            
            for idx, (label, data) in enumerate(stats.items()):
                with cols[idx]:
                    st.metric(
                        label,
                        "{} MB".format(data['size_mb']),
                        "{} files".format(data['file_count'])
                    )
                    total_size += data['size_mb']
                    total_files += data['file_count']
            
            st.divider()
            
            col_total1, col_total2, col_total3 = st.columns(3)
            
            with col_total1:
                st.metric("📦 Total Platform Storage", "{} MB".format(round(total_size, 2)))
            
            with col_total2:
                st.metric("📄 Total Files", total_files)
            
            with col_total3:
                # Estimate GitHub limit (1GB = 1024 MB)
                percent_used = (total_size / 1024) * 100
                st.metric("GitHub Repo Usage", "{}%".format(round(percent_used, 1)))
            
            # Warning if approaching limit
            if percent_used > 80:
                st.error("⚠️ **Critical:** Approaching GitHub 1GB storage limit! Run cleanup immediately.")
            elif percent_used > 50:
                st.warning("⚠️ **Warning:** Using over 50% of recommended storage. Consider cleanup.")
        
        else:
            st.info("No storage data available yet.")
        
        st.divider()
        
        # ========== ORPHANED FILE CLEANUP ==========
        st.subheader("🧹 Automatic File Cleanup")
        
        st.markdown("""
        <div style='background-color: #fff4e6; padding: 12px; border-radius: 8px; border-left: 3px solid #ff9800;'>
            <p style='margin: 0; color: #e65100;'>
                <strong>⚠️ What are orphaned files?</strong><br>
                Files that exist on disk but are no longer referenced in the database 
                (e.g., from deleted assignments, students, or semesters).
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        col_cleanup1, col_cleanup2 = st.columns([1, 2])
        
        with col_cleanup1:
            if st.button("🧹 Scan & Clean Orphaned Files", type="primary", use_container_width=True):
                
                with st.spinner("🔍 Scanning for orphaned files..."):
                    deleted, space_freed = cleanup_orphaned_files()
                
                if deleted > 0:
                    st.success("✅ **Cleanup Complete!**")
                    st.write("- **Files Deleted:** {}".format(deleted))
                    st.write("- **Space Freed:** {} MB".format(space_freed))
                    st.balloons()
                    st.rerun()
                else:
                    st.info("✨ **Platform is clean!** No orphaned files found.")
        
        with col_cleanup2:
            st.info("""
            **Safe Operation:**
            - Only removes files NOT in database
            - Does NOT delete active assignments/submissions
            - Recommended: Run monthly
            """)
        
        st.divider()
        
        # ========== FILE BROWSER ==========
        st.subheader("📁 File Browser & Inspector")
        
        folder = st.selectbox("Select Folder to Inspect", [
            "assignment_files",
            "submission_files", 
            "study_materials",
            "data"
        ])
        
        if os.path.exists(folder):
            files = []
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    try:
                        size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                        # Get file modification time
                        mod_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d %H:%M')
                        
                        files.append({
                            'Filename': filename,
                            'Size (MB)': size_mb,
                            'Modified': mod_time,
                            'Path': file_path
                        })
                    except:
                        continue
            
            if files:
                df_files = pd.DataFrame(files)
                # Sort by size (largest first)
                df_files = df_files.sort_values('Size (MB)', ascending=False)
                
                st.dataframe(
                    df_files[['Filename', 'Size (MB)', 'Modified']], 
                    use_container_width=True, 
                    hide_index=True
                )
                
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    st.info("📊 **Total Files:** {}".format(len(files)))
                
                with col_info2:
                    total_folder_size = sum([f['Size (MB)'] for f in files])
                    st.info("💾 **Folder Size:** {} MB".format(round(total_folder_size, 2)))
                
                # Show largest files
                if len(files) > 5:
                    st.write("**🔝 Top 5 Largest Files:**")
                    top_5 = df_files.head(5)[['Filename', 'Size (MB)']]
                    st.dataframe(top_5, use_container_width=True, hide_index=True)
            
            else:
                st.info("📭 No files in this folder")
        else:
            st.warning("⚠️ Folder does not exist yet")
        
        st.divider()
        
        # ========== QUICK STATS ==========
        st.subheader("📈 Platform Statistics")
        
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            semester_count = db_query("SELECT COUNT(*) as count FROM semesters", conn).iloc[0]['count']
            st.metric("🎓 Semesters", semester_count)
        
        with col_stat2:
            student_count = db_query("SELECT COUNT(*) as count FROM users WHERE role='student'", conn).iloc[0]['count']
            st.metric("👥 Students", student_count)
        
        with col_stat3:
            assignment_count = db_query("SELECT COUNT(*) as count FROM assignments", conn).iloc[0]['count']
            st.metric("📝 Assignments", assignment_count)
        
        with col_stat4:
            submission_count = db_query("SELECT COUNT(*) as count FROM submissions", conn).iloc[0]['count']
            st.metric("📤 Submissions", submission_count)
            st.divider()
        
        # ========== DATABASE BACKUP & RESTORE ==========
        st.subheader("💾 Database Backup & Restore")
        
        st.warning("⚠️ **Important:** After restoring a backup, you must refresh the page to reconnect to the database.")
        
        col_backup1, col_backup2 = st.columns(2)
        
        with col_backup1:
            st.markdown("**📦 Create New Backup**")
            st.info("Creates a timestamped backup of the current database. Last 10 backups are kept automatically.")
            
            if st.button("📦 Create Backup Now", use_container_width=True, type="primary"):
                with st.spinner("Creating backup..."):
                    success, message = create_database_backup()
                
                if success:
                    st.success("✅ {}".format(message))
                    st.balloons()
                else:
                    st.error("❌ {}".format(message))
        
        with col_backup2:
            st.markdown("**🔄 Restore from Backup**")
            
            backups = get_backup_list()
            
            if backups:
                # Display backups in a nice format
                backup_options = {
                    "{} ({} KB)".format(b['date'], b['size_kb']): b['path']
                    for b in backups
                }
                
                selected_backup_display = st.selectbox(
                    "Select backup to restore",
                    list(backup_options.keys()),
                    key="restore_backup_select"
                )
                
                if selected_backup_display:
                    selected_backup_path = backup_options[selected_backup_display]
                    
                    # Two-step confirmation
                    if st.button("⚠️ Restore Database", use_container_width=True):
                        st.error("🚨 **DANGER ZONE** 🚨")
                        st.write("This will replace the current database!")
                        
                        col_confirm1, col_confirm2 = st.columns(2)
                        
                        with col_confirm1:
                            if st.button("✅ YES, RESTORE", type="primary", use_container_width=True, key="confirm_restore_yes"):
                                with st.spinner("Restoring database..."):
                                    success, message = restore_database_from_backup(selected_backup_path)
                                
                                if success:
                                    st.success("✅ {}".format(message))
                                    st.info("🔄 Please REFRESH the page now (Ctrl+R or Cmd+R)")
                                else:
                                    st.error("❌ {}".format(message))
                        
                        with col_confirm2:
                            if st.button("❌ Cancel", use_container_width=True, key="confirm_restore_no"):
                                st.info("Restore cancelled")
            else:
                st.info("📭 No backups available yet. Create your first backup!")
        
        st.divider()
        
        # Show backup history
        if backups:
            with st.expander("📜 Backup History"):
                backup_df = pd.DataFrame(backups)
                st.dataframe(
                    backup_df[['filename', 'date', 'size_kb']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'filename': 'Backup File',
                        'date': 'Created On',
                        'size_kb': 'Size (KB)'
                    }
                )
                
    # STUDENT PROFILES
    with tabs[9]:
        
        st.title("👤 Student Profile Viewer")
        
        # Select student
        all_students = db_query("""
        SELECT users.id, users.username, users.full_name, semesters.name as semester
        FROM users
        LEFT JOIN semesters ON users.semester_id = semesters.id
        WHERE users.role='student'
        ORDER BY users.username ASC
        """, conn)
        
        if all_students.empty:
            st.info("No students registered yet.")
        else:
            # Search or select
            col_profile1, col_profile2 = st.columns([2, 1])
            
            with col_profile1:
                search_profile = st.text_input(
                    "🔍 Search student by name or username",
                    key="search_profile"
                )
            
            with col_profile2:
                if search_profile:
                    filtered = all_students[
                        all_students['username'].str.contains(search_profile, case=False) |
                        all_students['full_name'].str.contains(search_profile, case=False)
                    ]
                else:
                    filtered = all_students
            
            if filtered.empty:
                st.warning("No students found")
            else:
                student_options = {
                    "{} ({}) - {}".format(row['username'], row['full_name'], row['semester']): row['id']
                    for _, row in filtered.iterrows()
                }
                
                selected = st.selectbox("Select Student", list(student_options.keys()))
                
                if selected:
                    student_id = student_options[selected]
                    profile = get_student_profile(student_id)
                    
                    if profile:
                        st.divider()
                        
                        # Header
                        st.markdown("""
                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    padding: 20px; border-radius: 10px; color: white;'>
                            <h2 style='margin:0;'>{}</h2>
                            <p style='margin:5px 0 0 0;'>@{} | {}</p>
                        </div>
                        """.format(
                            profile['info']['full_name'],
                            profile['info']['username'],
                            profile['info']['semester']
                        ), unsafe_allow_html=True)
                        st.divider()
                        st.subheader("📊 Personal Growth & Performance")
                        
                        submissions_df = profile['submissions']

                        # Filter only the assignments that have actually been graded by the AI
                        graded_df = submissions_df[submissions_df['marks'].notna() & (submissions_df['marks'] != '')].copy()

                        if not graded_df.empty:
                            # Safely convert marks to numbers
                            graded_df['Marks'] = pd.to_numeric(graded_df['marks'], errors='coerce')
                            # Sort by deadline to show chronological growth over the semester
                            graded_df = graded_df.sort_values(by='deadline')
                            # Create a clean chart data table
                            chart_data = graded_df[['assignment', 'Marks']].set_index('assignment')
                            # Display a line chart showing their progress
                            st.line_chart(chart_data)
                        else:
                            st.info("Waiting for more graded assignments to generate a growth chart.")
                        
                        st.write("")
                        
                        # Statistics
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        
                        with col_stat1:
                            st.metric("📤 Total Submissions", profile['stats']['total_submissions'])
                        
                        with col_stat2:
                            st.metric("✅ Graded", profile['stats']['total_graded'])
                        
                        with col_stat3:
                            st.metric("📊 Average Score", "{}/10".format(profile['stats']['average']))
                        
                        with col_stat4:
                            st.metric("🏆 Best Score", "{}/10".format(profile['stats']['highest']))
                        
                        st.divider()
                        
                        # Submissions
                        st.subheader("📋 Submission History")
                        
                        if profile['submissions'].empty:
                            st.info("No submissions yet")
                        else:
                            # Add status column
                            def get_status(row):
                                if row['marks'] and str(row['marks']).strip():
                                    return "✅ Graded ({}/10)".format(row['marks'])
                                else:
                                    return "⏳ Pending"
                            
                            display_df = profile['submissions'].copy()
                            display_df['Status'] = display_df.apply(get_status, axis=1)
                            
                            st.dataframe(
                                display_df[['subject', 'assignment', 'deadline', 'submission_time', 'Status']],
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # Performance chart
                            graded = display_df[display_df['marks'].notna() & (display_df['marks'] != '')]
                            
                            if not graded.empty:
                                st.divider()
                                st.subheader("📈 Performance Over Time")
                                
                                graded['marks_numeric'] = pd.to_numeric(graded['marks'], errors='coerce')
                                graded_sorted = graded.sort_values('submission_time')
                                
                                st.line_chart(
                                    graded_sorted.set_index('assignment')['marks_numeric']
                                )

# ==========================================================
# ===================== STUDENT =============================
# ==========================================================

elif role == "student":

    tabs = st.tabs(["Assignments","Study Materials", "My Results"])

        # ================= ASSIGNMENTS =================
    # ================= ASSIGNMENTS =================
    with tabs[0]:
        st.title("📝 My Assignments")

        # 1. First, get student's semester info
        student_info = db_query(
            "SELECT semester_id, username FROM users WHERE id=%s",
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

        # 2. Define sem_id clearly as an integer
        sem_id = int(sem_id_raw)

        # 3. NOW load announcements using that sem_id
        announcements = get_announcements_for_semester(sem_id)
        
        if not announcements.empty:
            st.subheader("📢 Announcements")
            for _, ann in announcements.iterrows():
                # Color based on priority
                if ann['priority'] == 'Urgent':
                    color = '#ff4444'
                    icon = '🚨'
                elif ann['priority'] == 'Important':
                    color = '#ff9800'
                    icon = '⚠️'
                else:
                    color = '#4CAF50'
                    icon = '📢'
                
                st.markdown("""
                <div style='background-color: {}; padding: 15px; border-radius: 8px; 
                            border-left: 5px solid {}; margin-bottom: 10px;'>
                    <h4 style='margin:0; color: white;'>{} {}</h4>
                    <p style='color: white; margin: 10px 0;'>{}</p>
                    <small style='color: #f0f0f0;'>Posted by {} on {}</small>
                </div>
                """.format(
                    color + '22', 
                    color,
                    icon,
                    ann['title'],
                    ann['message'],
                    ann['author'],
                    ann['created_at'][:16]
                ), unsafe_allow_html=True)
            
            st.divider()

        # 4. Continue with the rest of your Assignment logic...
        # (Deadline reminders, assignment list, etc.)

        st.title("📝 My Assignments")

        # Get student's semester
        student_info = db_query(
            "SELECT semester_id, username FROM users WHERE id=%s",
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
        semester_info = db_query(
            "SELECT name FROM semesters WHERE id=%s",
            conn,
            params=(sem_id,)
        )
        
        if not semester_info.empty:
            st.info("📚 Semester: **{}**".format(semester_info.iloc[0]['name']))
        
        # ========== DEADLINE REMINDER DASHBOARD ==========
        st.subheader("⏰ Deadline Reminders")
        
        # Get all assignments for student's semester
        all_assignments = db_query("""
        SELECT 
            assignments.id,
            assignments.title,
            assignments.deadline,
            subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=%s
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
                submission = db_query("""
                SELECT id FROM submissions
                WHERE assignment_id=%s AND student_id=%s
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
                st.error("🔴 **OVERDUE ASSIGNMENTS - Cannot submit!!**")
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
        assignments = db_query("""
        SELECT assignments.*, subjects.name as subject
        FROM assignments
        JOIN subjects ON assignments.subject_id = subjects.id
        WHERE subjects.semester_id=%s
        ORDER BY assignments.deadline ASC
        """, conn, params=(sem_id,))

        if assignments.empty:
            st.info("📭 No assignments available for your semester.")
        else:
            for index, row in assignments.iterrows():
                
                # Check submission status
                existing_submission = db_query("""
                SELECT * FROM submissions
                WHERE assignment_id=%s AND student_id=%s
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

                    # 1. DOWNLOAD ASSIGNMENT FILE
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

                    # 2. DEADLINE CALCULATIONS (NEW)
                    try:
                        # Convert stored deadline string to date object
                        deadline_date = datetime.strptime(str(row['deadline']), '%Y-%m-%d').date()
                        current_date = datetime.now().date()
                        is_late = current_date > deadline_date
                    except:
                        is_late = False

                    # 3. SUBMISSION STATUS LOGIC
                    if not existing_submission.empty:
                        # Case A: Already submitted
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

                    elif is_late:
                        # Case B: Not submitted and deadline passed (LOCKDOWN)
                        st.error("🔒 **Deadline Locked:** This assignment closed on {}.".format(row['deadline']))
                        st.info("Late submissions are not accepted through the portal. Please contact Er. Nirajan Katuwal.")
                    
                    else:
                        # Case C: Not submitted and deadline is still open
                        days_left, _, _ = get_deadline_status(row['deadline'])
                        if days_left == 0:
                            st.warning("⚠️ **Final Call:** This assignment is due today!")
                        elif days_left is not None and days_left <= 2:
                            st.info("🟡 Only {} days left to submit!".format(days_left))

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

                                try:
                                    c.execute("""
                                    INSERT INTO submissions(
                                        assignment_id,
                                        student_id,
                                        submission_time,
                                        submission_file,
                                        marks,
                                        ai_summary
                                    )
                                    VALUES(%s,%s,%s,%s,%s,%s)
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
                                    if days_left >= 0:
                                        st.success("✅ Assignment submitted successfully on time!")
                                    else:
                                        st.warning("⚠️ Assignment submitted {} days late.".format(abs(days_left)))
                                    
                                    st.balloons()
                                    st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error("Error submitting: {}".format(str(e)))

        # ================= STUDY MATERIALS =================
    with tabs[1]:
        
        st.title("📚 Study Materials")
        
        # Get student's semester
        student_info = db_query(
            "SELECT semester_id FROM users WHERE id=%s",
            conn,
            params=(int(st.session_state.user_id),)
        )
        
        if student_info.empty or student_info.iloc[0]["semester_id"] is None:
            st.warning("⚠️ You are not assigned to a semester. Please contact your lecturer.")
        else:
            sem_id = int(student_info.iloc[0]["semester_id"])
            
            # Get semester name
            semester_info = db_query(
                "SELECT name FROM semesters WHERE id=%s",
                conn,
                params=(sem_id,)
            )
            
            if not semester_info.empty:
                st.info("📚 Study Materials for: **{}**".format(semester_info.iloc[0]['name']))
            
            # Get all materials for student's semester
            materials = db_query("""
            SELECT 
                study_materials.id,
                study_materials.title,
                subjects.name as subject,
                study_materials.description,
                study_materials.file_path,
                study_materials.upload_date
            FROM study_materials
            JOIN subjects ON study_materials.subject_id = subjects.id
            WHERE study_materials.semester_id = %s
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
    # ================= RESULTS (ACCOUNTABILITY MODE) =================
    with tabs[2]:
        st.subheader("📝 My Academic Performance Record")

        # JOIN assignments first to ensure we see EVERY task, even those NOT submitted
        query = """
        SELECT 
            subjects.name as Subject, 
            assignments.title as Assignment, 
            assignments.deadline as Deadline,
            submissions.marks as Marks,
            submissions.submission_time as Submitted_On
        FROM assignments
        INNER JOIN subjects ON assignments.subject_id = subjects.id
        LEFT JOIN submissions ON assignments.id = submissions.assignment_id AND submissions.student_id = %s
        WHERE subjects.semester_id = %s
        ORDER BY assignments.deadline DESC
        """

        try:
            student_id = int(st.session_state.user_id)
            # Use the sem_id we calculated at the start of the student section
            results_df = db_query(query, conn, params=(student_id, sem_id))

            if results_df.empty:
                st.info("📭 No assignments have been posted for your semester yet.")
            else:
                display_data = []
                current_date = datetime.now().date()

                for _, row in results_df.iterrows():
                        # Parse deadline
                        deadline_date = datetime.strptime(str(row['Deadline']), '%Y-%m-%d').date()
                        current_date = datetime.now().date()
                    
                        # Convert marks to a clean variable to check for empty/NaN
                        raw_marks = row['Marks']
                        has_marks = raw_marks is not None and str(raw_marks).lower() != 'nan' and str(raw_marks).strip() != ""
                    
                        status = ""
                        score = ""
                    
                        # --- REFINED PRIORITY LOGIC ---
                    
                        # 1. Check if actually submitted first
                        if row['Submitted_On'] is not None:
                            if has_marks:
                                status = "✅ Graded"
                                score = f"{raw_marks}/10"
                            else:
                                status = "Pending"
                                score = "N/A"
                    
                        # 2. If NOT submitted, check if the deadline has passed
                        elif current_date > deadline_date:
                            status = "❌ MISSED (Negligence)"
                            score = "0/10"
                    
                        # 3. If NOT submitted and deadline is still in the future
                        else:
                            status = "📖 Open for Submission"
                            score = "Pending"

                        display_data.append({
                            "Subject": row['Subject'],
                            "Assignment": row['Assignment'],
                            "Deadline": row['Deadline'],
                            "Status": status,
                            "Marks": score
                        })

                # Create final dataframe
                final_df = pd.DataFrame(display_data)
                
                # Display to student
                st.dataframe(
                    final_df, 
                    use_container_width=True, 
                    hide_index=True
                )
                
                # Accountability Summary
                missed = len(final_df[final_df['Status'] == "❌ MISSED (Negligence)"])
                if missed > 0:
                    st.error(f"⚠️ You have **{missed}** missed assignment(s). A score of **0/10** has been recorded.")
                
        except Exception as e:
            st.error("⚠️ System error loading results. Please contact Er. Nirajan Katuwal.")
