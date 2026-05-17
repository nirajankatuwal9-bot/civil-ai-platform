import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
import os
import re
import io
import base64
import bcrypt
from PIL import Image
import fitz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time 
from streamlit_autorefresh import st_autorefresh

# ========== TIMEZONE CONFIG ==========
NST = timezone(timedelta(hours=5, minutes=45))

# ================= RESILIENT NEON POSTGRESQL CONNECTION ENGINE =================
def get_db_connection():
    """Establishes a connection to the Neon PostgreSQL database using secrets."""
    try:
        conn_string = st.secrets["postgres"]["url"]
        conn = psycopg2.connect(conn_string)
        return conn
    except Exception as e:
        st.error(f"❌ Database Connection Failure: {str(e)}")
        st.stop()

# Helper connection wrappers to match your existing app's query workflow patterns
def run_postgres_migration():
    """Creates tables using standard PostgreSQL data structures and ensures multi-tenant mapping compatibility."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 1. Tenant/College Isolation Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS organizations (
        id SERIAL PRIMARY KEY,
        org_name VARCHAR(255) NOT NULL UNIQUE,
        domain_extension VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. Multi-Tenant Users Table (With email, section, and lab_group fields integrated natively)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        org_id INTEGER NOT NULL DEFAULT 1, 
        full_name VARCHAR(255) NOT NULL,
        username VARCHAR(100) NOT NULL,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL,
        semester_id INTEGER,
        email VARCHAR(255),
        section VARCHAR(10) DEFAULT 'A',
        lab_group VARCHAR(50) DEFAULT 'Group 1',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT unique_org_username UNIQUE (org_id, username)
    );
    """)
    
    # 3. Semesters Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS semesters (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL UNIQUE
    );
    """)
    
    # 4. Subjects Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        semester_id INTEGER REFERENCES semesters(id) ON DELETE CASCADE
    );
    """)
    
    # 5. Subject Weighting Schemes Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subject_schemes (
        subject_id INTEGER PRIMARY KEY REFERENCES subjects(id) ON DELETE CASCADE,
        theory_full_marks REAL DEFAULT 40,
        prac_full_marks REAL DEFAULT 25,
        t_weight_att REAL DEFAULT 0.10,
        t_weight_hw REAL DEFAULT 0.25,
        t_weight_other REAL DEFAULT 0.15,
        t_weight_mid REAL DEFAULT 0.25,
        t_weight_final REAL DEFAULT 0.25,
        p_weight_att REAL DEFAULT 0.20,
        p_weight_perf REAL DEFAULT 0.20,
        p_weight_report REAL DEFAULT 0.20,
        p_weight_test REAL DEFAULT 0.20,
        p_weight_viva REAL DEFAULT 0.20
    );
    """)
    
    # 6. Assignments Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        deadline VARCHAR(50),
        question_file VARCHAR(500),
        rubric TEXT
    );
    """)
    
    # 7. Submissions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id SERIAL PRIMARY KEY,
        assignment_id INTEGER REFERENCES assignments(id) ON DELETE CASCADE,
        student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        submission_time VARCHAR(100),
        submission_file VARCHAR(500),
        marks VARCHAR(50),
        ai_summary TEXT
    );
    """)
    
    # 8. Study Materials Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS study_materials (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        semester_id INTEGER REFERENCES semesters(id) ON DELETE CASCADE,
        file_path VARCHAR(500),
        description TEXT,
        upload_date VARCHAR(100),
        uploaded_by INTEGER
    );
    """)
    
    # 9. Cumulative Student Marks Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS student_marks (
        student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        t_att_present INTEGER DEFAULT 0,
        t_att_total INTEGER DEFAULT 0,
        t_hw_raw REAL DEFAULT 0,
        t_mid_raw REAL DEFAULT 0,
        t_final_raw REAL DEFAULT 0,
        t_other_raw REAL DEFAULT 0,
        t_grace REAL DEFAULT 0,
        p_att_present INTEGER DEFAULT 0,
        p_att_total INTEGER DEFAULT 0,
        p_perf_raw REAL DEFAULT 0,
        p_report_raw REAL DEFAULT 0,
        p_test_raw REAL DEFAULT 0,
        p_viva_raw REAL DEFAULT 0,
        PRIMARY KEY (student_id, subject_id)
    );
    """)
    
    # 10. System Announcements Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS announcements (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        message TEXT,
        semester_id INTEGER,
        created_by INTEGER,
        created_at VARCHAR(100),
        priority VARCHAR(50),
        expires_at VARCHAR(100)
    );
    """)
    
    # Seed default organization system for baseline structure compatibility
    cur.execute("""
    INSERT INTO organizations (id, org_name, domain_extension) 
    VALUES (1, 'Default Institution', 'edu.np') 
    ON CONFLICT (id) DO NOTHING;
    """)
    
    conn.commit()
    cur.close()
    conn.close()

# Execute infrastructure engine verification
run_postgres_migration()
# ================= FIXED MULTI-TENANT PROVISIONING LOGIC =================

def seed_default_lecturer():
    secure_username = st.secrets["admin_setup"]["username"]
    secure_password = st.secrets["admin_setup"]["password"]
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Query checking for existing usernames matching the secure admin parameters
    cur.execute("SELECT id FROM users WHERE username = %s AND org_id = 1", (secure_username,))
    admin_exists = cur.fetchone()
    
    if not admin_exists:
        cur.execute("""
        INSERT INTO users (full_name, username, password, role, semester_id, org_id)
        VALUES (%s, %s, %s, %s, NULL, 1)
        """, (
            "Administrator",
            secure_username,
            bcrypt.hashpw(secure_password.encode(), bcrypt.gensalt()).decode(),
            "lecturer"
        ))
        conn.commit()
        
    cur.close()
    conn.close()

# Execute default system seeding operation
seed_default_lecturer()
# ================= SESSION SECURITY GATES =================

# Session timeout window configuration tracking (30 minutes)
SESSION_TIMEOUT = 1800

def check_session_timeout():
    """
    Evaluates active user interaction telemetry timestamps.
    Returns: True if valid, False if session has expired.
    """
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()
        return True
    
    current_time = time.time()
    elapsed = current_time - st.session_state.last_activity
    
    if elapsed > SESSION_TIMEOUT:
        return False  
    
    st.session_state.last_activity = current_time
    return True


def require_login():
    """
    Enforces route-guard isolation blocks on structural components.
    """
    if not st.session_state.get("logged_in", False):
        st.error("🔒 Please login to access this page")
        st.stop()
    
    if not check_session_timeout():
        st.warning("⏰ Your session has expired due to inactivity. Please login again.")
        st.session_state.clear()
        st.rerun()


# ================= SPACE-PROOF LOGIN FLOW GATE =================

if not st.session_state.get("logged_in", False):

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
        # Clean stray whitespaces from user inputs instantly using .strip()
        user_input = st.text_input("Username").strip()
        pw_input = st.text_input("Password", type="password").strip()

        if st.button("Enter the Flow", use_container_width=True, type="primary"):
            if not user_input or not pw_input:
                st.warning("Please enter both your Username and Password.")
            else:
                # Open isolated connection context for processing login request arrays
                login_conn = get_db_connection()
                
                # Translated query matching PostgreSQL placeholder requirements (%s)
                res = pd.read_sql_query(
                    "SELECT * FROM users WHERE username = %s AND org_id = 1",
                    login_conn,
                    params=(user_input,)
                )
                login_conn.close()

                if not res.empty and check_password(pw_input, res.iloc[0]["password"]):
                    st.session_state.logged_in = True
                    st.session_state.user_id = int(res.iloc[0]["id"])
                    st.session_state.role = str(res.iloc[0]["role"])
                    st.session_state.username = str(res.iloc[0]["username"])
                    st.session_state.semester_id = res.iloc[0]["semester_id"] if pd.notna(res.iloc[0]["semester_id"]) else None
                    st.session_state.full_name = str(res.iloc[0]["full_name"])
                    st.session_state.show_splash = True
                    st.rerun()
                else:
                    st.error("❌ Invalid Username or Password. Please check for typos and try again.")
    
    # Secure structural exit barrier for unauthenticated runtime contexts
    st.stop()


# ================= SECURE AUTHENTICATED RUNTIME ENVIRONMENT =================
# Down-stream blocks are only parsed when a user successfully enters the flow matrix.

# ---------- TIME & GREETING SETUP ----------
now_nst = datetime.now(NST)
current_hour = now_nst.hour

if current_hour < 12:
    greeting = "🌅 Good Morning"
elif 12 <= current_hour < 18:
    greeting = "☀️ Good Afternoon"
else:
    greeting = "🌙 Good Evening"

user_name = st.session_state.full_name
current_date = now_nst.strftime("%A, %B %d, %Y")
current_time = now_nst.strftime("%I:%M %p")


# ---------- THE WELCOME SPLASH SCREEN LAYOUT ----------
if st.session_state.get("show_splash"):
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align: center; color: #004b87;'>{greeting}, {user_name}!</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align: center; color: #555555;'>{current_date} &nbsp;|&nbsp; {current_time} (NST)</h3>", unsafe_allow_html=True)
    
    with st.spinner("Loading your secure workspace..."):
        time.sleep(2.5) 
        
    st.session_state.show_splash = False
    st.rerun()
    
    
# ---------- THE MAIN CONTAINER TIMELINE HEADER ----------
else:
    header_col1, header_col2 = st.columns([2, 1])
    
    with header_col1:
        st.markdown(f"### {greeting}, {user_name}!")
        
    with header_col2:
        st.markdown(f"""
        <div style='text-align: right; color: #555555;'>
            <strong>{current_date}</strong><br>
            {current_time} (NST)
        </div>
        """, unsafe_allow_html=True)
        
    st.divider()

def get_greeting():
    """Returns a dynamic greeting string based on Nepal Standard Time clocks."""
    curr_hour = datetime.now(NST).hour
    if curr_hour < 12:
        return "Good morning ☀️"
    elif 12 <= curr_hour < 18:
        return "Good afternoon 🌤️"
    else:
        return "Good evening 🌙"
# ================= DEADLINE AND COUNTDOWN CALCULATION METRICS =================

def get_deadline_status(deadline_str):
    """
    Evaluates calendar dates to map out task countdown status matrices.
    Returns: (days_remaining, status_string, indicator_emoji)
    """
    try:
        deadline = datetime.strptime(str(deadline_str).strip(), "%Y-%m-%d")
        today = datetime.now(NST)
        
        # Strip out hour/minute data for an accurate day-by-day structural calculation gap
        deadline_date = deadline.date()
        today_date = today.date()
        
        days_remaining = (deadline_date - today_date).days
        
        if days_remaining < 0:
            return days_remaining, "Overdue", "🔴"
        elif days_remaining == 0:
            return days_remaining, "Due Today", "export_status_orange"  # Use visual strings for safe UI interpretation
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
    Constructs a highly visible text timeline indicator complete with relative countdowns.
    """
    days, status, color = get_deadline_status(deadline_str)
    
    # Clean up standard text output matching for display panels
    emoji_color = "🟠" if color == "export_status_orange" else color
    
    if days is None:
        return f"{emoji_color}  {deadline_str}"
    elif days < 0:
        return f"{emoji_color}  {deadline_str} ({abs(days)} days overdue)"
    elif days == 0:
        return f"{emoji_color}  {deadline_str} (Due Today!)"
    elif days == 1:
        return f"{emoji_color}  {deadline_str} (Tomorrow)"
    else:
        return f"{emoji_color}  {deadline_str} ({days} days left)"


# ================= SYSTEM STORAGE ANALYSIS UTILITIES =================

def cleanup_orphaned_files():
    """
    Scans physical storage directories and removes files no longer tracked in Neon.
    Returns: (deleted_count, space_freed_mb)
    """
    deleted_count = 0
    space_freed = 0
    db_files = set()
    
    # Establish connection mapping arrays
    cleanup_conn = get_db_connection()
    cur = cleanup_conn.cursor()
    
    # 1. Gather assignment paths
    cur.execute("SELECT question_file FROM assignments WHERE question_file IS NOT NULL AND question_file != '';")
    for row in cur.fetchall():
        if row[0]: db_files.add(row[0])
        
    # 2. Gather student submission paths
    cur.execute("SELECT submission_file FROM submissions WHERE submission_file IS NOT NULL AND submission_file != '';")
    for row in cur.fetchall():
        if row[0]: db_files.add(row[0])
        
    # 3. Gather uploaded study material paths
    cur.execute("SELECT file_path FROM study_materials WHERE file_path IS NOT NULL AND file_path != '';")
    for row in cur.fetchall():
        if row[0]: db_files.add(row[0])
        
    cur.close()
    cleanup_conn.close()
    
    target_folders = ['assignment_files', 'submission_files', 'study_materials']
    
    for folder in target_folders:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                
                if file_path not in db_files and os.path.isfile(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        space_freed += file_size
                    except:
                        continue
    
    space_freed_mb = space_freed / (1024 * 1024)
    return deleted_count, round(space_freed_mb, 2)


def get_storage_stats():
    """
    Compiles space utilization telemetry statistics across all container folders.
    """
    stats = {}
    target_folders = {
        'assignment_files': 'Assignment Questions',
        'submission_files': 'Student Submissions',
        'study_materials': 'Study Materials',
        'data': 'Temporary Enclave Cache'
    }
    
    for folder, label in target_folders.items():
        if os.path.exists(folder):
            total_size = 0
            file_count = 0
            
            for dirpath, _, filenames in os.walk(folder):
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


# ================= DATA CONSTRAINTS & VALIDATION BARRIERS =================

MAX_FILE_SIZE_MB = 25  
ALLOWED_ASSIGNMENT_TYPES = ['pdf']
ALLOWED_SUBMISSION_TYPES = ['pdf']
ALLOWED_MATERIAL_TYPES = ['pdf', 'docx', 'pptx', 'zip', 'jpg', 'png']

def validate_file_upload(uploaded_file, allowed_types, max_size_mb=MAX_FILE_SIZE_MB):
    """
    Enforces strict size limits and validates magic-number extensions.
    Returns: (is_valid, error_or_success_message)
    """
    if uploaded_file is None:
        return False, "No file object uploaded to data stream buffer channel."
    
    file_extension = uploaded_file.name.split('.')[-1].lower()
    if file_extension not in allowed_types:
        return False, f"Invalid file type extension detected. Permitted formats: {', '.join(allowed_types)}"
    
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"File size payload exceeds threshold. Peak maximum: {max_size_mb} MB (Uploaded size: {file_size_mb:.2f} MB)"
    
    if file_extension == 'pdf':
        uploaded_file.seek(0)
        header_bytes = uploaded_file.read(5)
        uploaded_file.seek(0)
        if header_bytes != b'%PDF-':
            return False, "File stream validation failed: Corrupted or masked structure layout encountered."
            
    return True, "File payload fully matches standard validation criteria."


def check_deadline_passed(deadline_str):
    """
    Evaluates locking parameters based on absolute dates.
    Returns: (is_late, evaluation_message)
    """
    try:
        deadline_date = datetime.strptime(str(deadline_str).strip(), '%Y-%m-%d').date()
        current_date = datetime.now(NST).date()
        
        if current_date > deadline_date:
            days_late = (current_date - deadline_date).days
            return True, f"Deadline passed {days_late} days ago"
        return False, "Timeline remains open for submission entries."
    except:
        return False, "Invalid tracking date configuration format handled."


# ================= MULTI-TENANT SEARCH ENGINES =================

def search_students(query, semester_id=None):
    """
    Queries active student profiles inside your multi-tenant workspace using PostgreSQL LIKE blocks.
    """
    clean_query = query.strip().lower()
    if not clean_query:
        return pd.DataFrame()
        
    search_conn = get_db_connection()
    search_str = f"%{clean_query}%"
    
    # PostgreSQL queries use positional %s placeholders and case-insensitive ILIKE patterns
    if semester_id:
        results_df = pd.read_sql_query("""
            SELECT u.id, u.full_name, u.username, s.name as semester, u.section, u.lab_group
            FROM users u
            LEFT JOIN semesters s ON u.semester_id = s.id
            WHERE u.role = 'student' AND u.org_id = 1 AND u.semester_id = %s
              AND (LOWER(u.full_name) LIKE %s OR LOWER(u.username) LIKE %s)
            ORDER BY u.full_name ASC;
        """, search_conn, params=(int(semester_id), search_str, search_str))
    else:
        results_df = pd.read_sql_query("""
            SELECT u.id, u.full_name, u.username, s.name as semester, u.section, u.lab_group
            FROM users u
            LEFT JOIN semesters s ON u.semester_id = s.id
            WHERE u.role = 'student' AND u.org_id = 1
              AND (LOWER(u.full_name) LIKE %s OR LOWER(u.username) LIKE %s)
            ORDER BY u.full_name ASC;
        """, search_conn, params=(search_str, search_str))
        
    search_conn.close()
    return results_df
# ================= INTERNAL THEORY MARK CALCULATION ENGINE =================

def calculate_internal_theory(row, subject_id, db_conn):
    """
    Dynamically fetches subject marking configurations from PostgreSQL 
    and calculates weighted theory marks with a strict 70% attendance gate.
    """
    with db_conn.cursor() as cur:
        # Fetch the active subject's custom rules using standard %s placeholder mapping
        cur.execute("SELECT * FROM subject_schemes WHERE subject_id = %s;", (int(subject_id),))
        columns = [desc[0] for desc in cur.description]
        scheme_row = cur.fetchone()
    
    # Fallback default fallback matrix if rules haven't been locked yet
    if not scheme_row:
        scheme = {
            'theory_full_marks': 40.0,
            't_weight_att': 0.10, 't_weight_hw': 0.25, 't_weight_other': 0.15,
            't_weight_mid': 0.25, 't_weight_final': 0.25
        }
    else:
        scheme = dict(zip(columns, scheme_row))

    # 1. Attendance Ratio & Score Allocation Math
    att_present = float(row.get('t_att_present', 0))
    att_total = float(row.get('t_att_total', 34))
    
    att_ratio = att_present / att_total if att_total > 0 else 0.0
    att_score = att_ratio * (float(scheme['theory_full_marks']) * float(scheme['t_weight_att']))
    
    # 2. Scale Continuous Assessment Percentages (0-100) to Weights
    hw_score = (float(row.get('t_hw_raw', 0)) / 100) * (float(scheme['theory_full_marks']) * float(scheme['t_weight_hw']))
    mid_score = (float(row.get('t_mid_raw', 0)) / 100) * (float(scheme['theory_full_marks']) * float(scheme['t_weight_mid']))
    final_score = (float(row.get('t_final_raw', 0)) / 100) * (float(scheme['theory_full_marks']) * float(scheme['t_weight_final']))
    other_score = (float(row.get('t_other_raw', 0)) / 100) * (float(scheme['theory_full_marks']) * float(scheme['t_weight_other']))
    
    raw_total = att_score + hw_score + mid_score + final_score + other_score
    
    # 3. Enforce the Strict 70% Attendance Gate Barrier
    is_eligible_grace = att_ratio >= 0.70
    final_total = raw_total
    
    if is_eligible_grace and float(row.get('t_grace', 0)) > 0:
        final_total += min(float(row.get('t_grace', 0)), 5.0) 
        
    return round(final_total, 2), is_eligible_grace


# ================= INTERNAL PRACTICAL MARK CALCULATION ENGINE =================

def calculate_internal_practical(row, subject_id, db_conn):
    """
    Dynamically fetches laboratory configurations and calculates 
    weighted practical internal marks out of fluid/hydraulic lab modules.
    """
    with db_conn.cursor() as cur:
        cur.execute("SELECT * FROM subject_schemes WHERE subject_id = %s;", (int(subject_id),))
        columns = [desc[0] for desc in cur.description]
        scheme_row = cur.fetchone()
        
    if not scheme_row:
        scheme = {
            'prac_full_marks': 25.0,
            'p_weight_att': 0.20, 'p_weight_perf': 0.20, 'p_weight_report': 0.20,
            'p_weight_test': 0.20, 'p_weight_viva': 0.20
        }
    else:
        scheme = dict(zip(columns, scheme_row))

    full_p = float(scheme['prac_full_marks'])
    
    # Laboratory Grid Evaluation Array
    p_att_present = float(row.get('p_att_present', 0))
    p_att_total = float(row.get('p_att_total', 12))
    
    att_ratio = p_att_present / p_att_total if p_att_total > 0 else 0.0
    att_score = att_ratio * (full_p * float(scheme['p_weight_att']))
    
    perf_score = (float(row.get('p_perf_raw', 0)) / 100) * (full_p * float(scheme['p_weight_perf']))
    report_score = (float(row.get('p_report_raw', 0)) / 100) * (full_p * float(scheme['p_weight_report']))
    test_score = (float(row.get('p_test_raw', 0)) / 100) * (full_p * float(scheme['p_weight_test']))
    viva_score = (float(row.get('p_viva_raw', 0)) / 100) * (full_p * float(scheme['p_weight_viva']))
    
    raw_total = att_score + perf_score + report_score + test_score + viva_score
    is_eligible = att_ratio >= 0.70
    
    return round(raw_total, 2), is_eligible
    
