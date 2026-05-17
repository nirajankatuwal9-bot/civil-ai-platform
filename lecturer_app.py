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
