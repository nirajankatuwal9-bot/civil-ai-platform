import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
import os
import re
import bcrypt
import time
import io

# ==========================================================
# ================== PAGE CONFIG ===========================
# ==========================================================

st.set_page_config(
    page_title="The N-Streamlines",
    page_icon="🌊",
    layout="wide"
)

# ==========================================================
# ================== DATABASE CONNECTION ===================
# ==========================================================

try:
    DATABASE_URL = st.secrets.get("DATABASE_URL", os.getenv("DATABASE_URL"))

    if not DATABASE_URL:
        st.error("🚨 DATABASE_URL not found in Streamlit Secrets!")
        st.stop()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False

except Exception as e:
    st.error(f"🚨 Database Connection Failed: {e}")
    st.stop()

# ==========================================================
# ================== DATABASE HELPERS ======================
# ==========================================================

def db_query(query, params=None):
    try:
        if params:
            return pd.read_sql_query(query, conn, params=params)
        else:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Database Query Error: {e}")
        return pd.DataFrame()

def db_execute(query, params=None):
    try:
        with conn.cursor() as cursor:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)

# ==========================================================
# ================== CREATE TABLES =========================
# ==========================================================

db_execute("""
CREATE TABLE IF NOT EXISTS semesters(
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    full_name TEXT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT,
    semester_id INTEGER,
    email TEXT
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS subjects(
    id SERIAL PRIMARY KEY,
    name TEXT,
    semester_id INTEGER
)
""")

db_execute("""
CREATE TABLE IF NOT EXISTS assignments(
    id SERIAL PRIMARY KEY,
    title TEXT,
    subject_id INTEGER,
    deadline TEXT,
    question_file TEXT,
    rubric TEXT
)
""")

db_execute("""
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

db_execute("""
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

db_execute("""
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

# ==========================================================
# ================== PASSWORD HELPERS ======================
# ==========================================================

def hash_password(p):
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def check_password(p, hashed):
    try:
        return bcrypt.checkpw(p.encode(), hashed.encode())
    except:
        return False

# ==========================================================
# ================== DEFAULT ADMIN =========================
# ==========================================================

admin_check = db_query(
    "SELECT * FROM users WHERE username=%s",
    params=("admin",)
)

if admin_check.empty:
    db_execute("""
        INSERT INTO users(full_name, username, password, role)
        VALUES(%s,%s,%s,%s)
    """, (
        "Administrator",
        "admin",
        hash_password("admin123"),
        "lecturer"
    ))

# ==========================================================
# ================== SESSION CONTROL =======================
# ==========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.username = None

SESSION_TIMEOUT = 1800

def check_session_timeout():
    if "last_activity" not in st.session_state:
        st.session_state.last_activity = time.time()
        return True

    if time.time() - st.session_state.last_activity > SESSION_TIMEOUT:
        return False

    st.session_state.last_activity = time.time()
    return True

def require_login():
    if not st.session_state.get("logged_in"):
        st.error("🔒 Please login")
        st.stop()

    if not check_session_timeout():
        st.warning("⏰ Session expired")
        st.session_state.clear()
        st.stop()

# ==========================================================
# ================== LOGIN SYSTEM ==========================
# ==========================================================

if not st.session_state.logged_in:

    st.title("🌊 THE N-STREAMLINES")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        user_data = db_query(
            "SELECT * FROM users WHERE username=%s",
            params=(username,)
        )

        if not user_data.empty:
            stored_pw = user_data.iloc[0]["password"]

            if check_password(password, stored_pw):
                st.session_state.logged_in = True
                st.session_state.user_id = int(user_data.iloc[0]["id"])
                st.session_state.role = user_data.iloc[0]["role"]
                st.session_state.username = user_data.iloc[0]["username"]
                st.session_state.semester_id = user_data.iloc[0]["semester_id"]
                st.session_state.last_activity = time.time()
                st.success("✅ Login Successful")
                st.rerun()
            else:
                st.error("Invalid credentials")
        else:
            st.error("User not found")

    st.stop()

# ==========================================================
# ================== BACKUP SYSTEM (OPTION 1) ==============
# ==========================================================

def create_database_backup():

    backup_dir = "data/backups"
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.sql"
    path = os.path.join(backup_dir, filename)

    try:
        with open(path, "w", encoding="utf-8") as f:
            tables = ["users", "semesters", "subjects", "assignments",
                      "submissions", "announcements", "study_materials"]

            for table in tables:
                df = db_query(f"SELECT * FROM {table}")
                if not df.empty:
                    f.write(f"-- Data for table {table}\n")
                    for _, row in df.iterrows():
                        values = []
                        for val in row:
                            if val is None:
                                values.append("NULL")
                            else:
                                escaped = str(val).replace("'", "''")
                                values.append(f"'{escaped}'")
                        insert = f"INSERT INTO {table} VALUES ({', '.join(values)});\n"
                        f.write(insert)
                    f.write("\n")

        return True, f"Backup created: {filename}"

    except Exception as e:
        return False, str(e)
