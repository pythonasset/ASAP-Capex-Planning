import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
import shutil
import zipfile
from pathlib import Path
import configparser

# Database error handling and connection management
def get_db_connection():
    """Get database connection with proper error handling"""
    try:
        conn = sqlite3.connect('capex_planning.db')
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    except sqlite3.Error as e:
        st.error(f"Database connection error: {e}")
        return None

def execute_db_query(query, params=None, fetch=None):
    """Execute database query with comprehensive error handling"""
    try:
        conn = get_db_connection()
        if conn is None:
            return None
            
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch == 'all':
            result = cursor.fetchall()
        elif fetch == 'one':
            result = cursor.fetchone()
        else:
            result = None
            
        # Only commit if it's a modification query
        if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            conn.commit()
            
        conn.close()
        return result
        
    except sqlite3.IntegrityError as e:
        st.error(f"Database integrity error: {str(e)}")
        st.info("This may be due to duplicate entries or invalid references. Please check your data and try again.")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except sqlite3.Error as e:
        st.error(f"Database error: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

# Configuration reader
def read_config():
    """Read configuration from config.ini file"""
    config = configparser.ConfigParser()
    config_path = Path(__file__).parent / 'config.ini'
    
    # Default values if config file doesn't exist
    default_config = {
        'registered_to': 'Your Organization Name',
        'produced_by': 'Odysseus-imc Pty Ltd',
        'software_name': 'ASAP CAPEX Planning System',
        'version': '1.0 (Beta)',
        'show_registration': True,
        'show_producer': True,
        'show_version': True
    }
    
    try:
        if config_path.exists():
            config.read(config_path)
            return {
                'registered_to': config.get('SOFTWARE', 'registered_to', fallback=default_config['registered_to']),
                'produced_by': config.get('SOFTWARE', 'produced_by', fallback=default_config['produced_by']),
                'software_name': config.get('SOFTWARE', 'software_name', fallback=default_config['software_name']),
                'version': config.get('SOFTWARE', 'version', fallback=default_config['version']),
                'show_registration': config.getboolean('DISPLAY', 'show_registration', fallback=default_config['show_registration']),
                'show_producer': config.getboolean('DISPLAY', 'show_producer', fallback=default_config['show_producer']),
                'show_version': config.getboolean('DISPLAY', 'show_version', fallback=default_config['show_version'])
            }
        else:
            return default_config
    except Exception:
        return default_config

# Date formatting function
def format_date(date_value):
    """Format date to dd/mm/yyyy format"""
    if pd.isna(date_value) or date_value is None:
        return ""
    try:
        if isinstance(date_value, str):
            # Try to parse string date
            date_obj = pd.to_datetime(date_value)
        else:
            date_obj = date_value
        return date_obj.strftime("%d/%m/%Y")
    except:
        return str(date_value)

def format_dataframe_dates(df, date_columns):
    """Format date columns in a DataFrame to dd/mm/yyyy"""
    df_formatted = df.copy()
    for col in date_columns:
        if col in df_formatted.columns:
            df_formatted[col] = df_formatted[col].apply(format_date)
    return df_formatted

# Database maintenance and integrity checks
def check_database_integrity():
    """Check and maintain database integrity"""
    try:
        conn = get_db_connection()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        
        # Check for foreign key violations
        cursor.execute("PRAGMA foreign_key_check")
        violations = cursor.fetchall()
        
        if violations:
            st.warning(f"Found {len(violations)} database integrity issues. Attempting to fix...")
            
            # Fix orphaned priority_score records
            cursor.execute("""
                DELETE FROM priority_score 
                WHERE asset_id NOT IN (SELECT asset_id FROM asset)
                AND asset_id IS NOT NULL
            """)
            
            # Fix other potential issues
            cursor.execute("""
                DELETE FROM project_year_cost 
                WHERE project_id NOT IN (SELECT project_id FROM project)
                AND project_id IS NOT NULL
            """)
            
            cursor.execute("""
                DELETE FROM risk_assessment 
                WHERE project_id NOT IN (SELECT project_id FROM project)
                AND project_id IS NOT NULL
            """)
            
            conn.commit()
            st.success("Database integrity issues fixed!")
        
        # Optimize database
        cursor.execute("ANALYZE")
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Database integrity check failed: {e}")
        if 'conn' in locals() and conn:
            conn.close()
        return False

# Database initialization
def init_database():
    conn = sqlite3.connect('capex_planning.db')
    c = conn.cursor()
    
    # Reference tables
    c.execute('''CREATE TABLE IF NOT EXISTS yes_no_flag (
        flag_id INTEGER PRIMARY KEY,
        flag_name TEXT NOT NULL
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS asset_class (
        asset_class_id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_name TEXT NOT NULL UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS asset_type_l4 (
        asset_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_class_id INTEGER,
        type_name TEXT NOT NULL,
        FOREIGN KEY (asset_class_id) REFERENCES asset_class(asset_class_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS location_dim (
        location_id INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude REAL,
        longitude REAL,
        elevation_m REAL,
        region TEXT,
        locality TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS design_status (
        design_status_id INTEGER PRIMARY KEY AUTOINCREMENT,
        status_name TEXT NOT NULL UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS env_status (
        env_status_id INTEGER PRIMARY KEY AUTOINCREMENT,
        status_name TEXT NOT NULL UNIQUE
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS project_status (
        project_status_id INTEGER PRIMARY KEY AUTOINCREMENT,
        status_code TEXT NOT NULL UNIQUE,
        description TEXT
    )''')
    
    # Main asset table
    c.execute('''CREATE TABLE IF NOT EXISTS asset (
        asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_code TEXT NOT NULL UNIQUE,
        asset_type_id INTEGER,
        location_id INTEGER,
        construct_year INTEGER,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (asset_type_id) REFERENCES asset_type_l4(asset_type_id),
        FOREIGN KEY (location_id) REFERENCES location_dim(location_id)
    )''')
    
    # Weighting constants
    c.execute('''CREATE TABLE IF NOT EXISTS weighting_constant (
        constant_id INTEGER PRIMARY KEY AUTOINCREMENT,
        criterion_name TEXT NOT NULL,
        weight_pct REAL NOT NULL
    )''')
    
    # Priority score criteria
    c.execute('''CREATE TABLE IF NOT EXISTS criterion (
        criterion_id INTEGER PRIMARY KEY AUTOINCREMENT,
        criterion_name TEXT NOT NULL UNIQUE,
        weight_pct REAL NOT NULL
    )''')
    
    # Priority scores
    c.execute('''CREATE TABLE IF NOT EXISTS priority_score (
        score_id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER,
        whs_score REAL DEFAULT 0,
        water_savings_score REAL DEFAULT 0,
        customer_score REAL DEFAULT 0,
        maintenance_score REAL DEFAULT 0,
        financial_score REAL DEFAULT 0,
        total_priority_score REAL DEFAULT 0,
        FOREIGN KEY (asset_id) REFERENCES asset(asset_id)
    )''')
    
    # Projects
    c.execute('''CREATE TABLE IF NOT EXISTS project (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER,
        project_scope TEXT,
        design_status_id INTEGER,
        env_status_id INTEGER,
        priority_rank INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (asset_id) REFERENCES asset(asset_id),
        FOREIGN KEY (design_status_id) REFERENCES design_status(design_status_id),
        FOREIGN KEY (env_status_id) REFERENCES env_status(env_status_id)
    )''')
    
    # Project year costs
    c.execute('''CREATE TABLE IF NOT EXISTS project_year_cost (
        cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        financial_year TEXT,
        project_cost REAL DEFAULT 0,
        customer_contribution REAL DEFAULT 0,
        summary_txt TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES project(project_id)
    )''')
    
    # Consequence and Likelihood
    c.execute('''CREATE TABLE IF NOT EXISTS consequence (
        consequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        description TEXT,
        score INTEGER
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS likelihood (
        likelihood_id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        description TEXT,
        score INTEGER
    )''')
    
    # Risk assessment
    c.execute('''CREATE TABLE IF NOT EXISTS risk_assessment (
        risk_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        consequence_id INTEGER,
        likelihood_id INTEGER,
        risk_rating TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES project(project_id),
        FOREIGN KEY (consequence_id) REFERENCES consequence(consequence_id),
        FOREIGN KEY (likelihood_id) REFERENCES likelihood(likelihood_id)
    )''')
    
    # Project status history
    c.execute('''CREATE TABLE IF NOT EXISTS project_status_history (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER,
        project_status_id INTEGER,
        status_date DATE,
        comments TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES project(project_id),
        FOREIGN KEY (project_status_id) REFERENCES project_status(project_status_id)
    )''')
    
    # Initialize reference data if empty
    c.execute("SELECT COUNT(*) FROM design_status")
    if c.fetchone()[0] == 0:
        statuses = [
            'To be assigned', 'Under Development', 'For Review', 
            'Approved', 'Pending WAE', 'Complete'
        ]
        for status in statuses:
            c.execute("INSERT INTO design_status (status_name) VALUES (?)", (status,))
    
    c.execute("SELECT COUNT(*) FROM env_status")
    if c.fetchone()[0] == 0:
        env_statuses = ['Pending', 'Complete']
        for status in env_statuses:
            c.execute("INSERT INTO env_status (status_name) VALUES (?)", (status,))
    
    c.execute("SELECT COUNT(*) FROM project_status")
    if c.fetchone()[0] == 0:
        proj_statuses = [
            ('PLANNED', 'Project is planned'),
            ('DESIGN', 'In design phase'),
            ('APPROVED', 'Approved by board'),
            ('IN_PROGRESS', 'Construction in progress'),
            ('COMPLETED', 'Project completed'),
            ('ON_HOLD', 'Project on hold')
        ]
        for code, desc in proj_statuses:
            c.execute("INSERT INTO project_status (status_code, description) VALUES (?, ?)", (code, desc))
    
    c.execute("SELECT COUNT(*) FROM criterion")
    if c.fetchone()[0] == 0:
        criteria = [
            ('WHS', 30),
            ('Water Savings', 20),
            ('Customer', 30),
            ('Maintenance/Ops', 10),
            ('Financial', 10)
        ]
        for name, weight in criteria:
            c.execute("INSERT INTO criterion (criterion_name, weight_pct) VALUES (?, ?)", (name, weight))
    
    c.execute("SELECT COUNT(*) FROM consequence")
    if c.fetchone()[0] == 0:
        consequences = [
            ('L', 'Low', 1), ('M', 'Medium', 2), ('H', 'High', 3),
            ('VH', 'Very High', 4), ('C', 'Catastrophic', 5)
        ]
        for code, desc, score in consequences:
            c.execute("INSERT INTO consequence (code, description, score) VALUES (?, ?, ?)", 
                     (code, desc, score))
    
    c.execute("SELECT COUNT(*) FROM likelihood")
    if c.fetchone()[0] == 0:
        likelihoods = [
            ('R', 'Rare', 1), ('U', 'Unlikely', 2), ('O', 'Occasional', 3),
            ('L', 'Likely', 4), ('HL', 'Highly Likely', 5), ('AC', 'Almost Certain', 6)
        ]
        for code, desc, score in likelihoods:
            c.execute("INSERT INTO likelihood (code, description, score) VALUES (?, ?, ?)", 
                     (code, desc, score))
    
    c.execute("SELECT COUNT(*) FROM asset_class")
    if c.fetchone()[0] == 0:
        asset_classes = [
            'Bridges & Culverts', 'Regulators', 'Outlets', 
            'Pump Stations & Facilities', 'Channels', 'Meters'
        ]
        for ac in asset_classes:
            c.execute("INSERT INTO asset_class (class_name) VALUES (?)", (ac,))
    
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect('capex_planning.db')

# (Duplicate streamlit app code removed)

# Streamlit App
    st.title("📊 CAPEX Planning Dashboard")
    
    conn = get_db()
    
    col1, col2, col3, col4 = st.columns(4)
    
    # KPIs
    total_projects = pd.read_sql_query("SELECT COUNT(*) as cnt FROM project", conn).iloc[0]['cnt']
    total_budget = pd.read_sql_query(
        "SELECT SUM(project_cost) as total FROM project_year_cost", conn
    ).iloc[0]['total'] or 0
    
    active_projects = pd.read_sql_query(
        """SELECT COUNT(DISTINCT p.project_id) as cnt 
           FROM project p 
           JOIN project_status_history psh ON p.project_id = psh.project_id
           JOIN project_status ps ON psh.project_status_id = ps.project_status_id
           WHERE ps.status_code IN ('IN_PROGRESS', 'DESIGN')""", conn
    ).iloc[0]['cnt']
    
    completed_projects = pd.read_sql_query(
        """SELECT COUNT(DISTINCT p.project_id) as cnt 
           FROM project p 
           JOIN project_status_history psh ON p.project_id = psh.project_id
           JOIN project_status ps ON psh.project_status_id = ps.project_status_id
           WHERE ps.status_code = 'COMPLETED'""", conn
    ).iloc[0]['cnt']
    
    col1.metric("Total Projects", total_projects)
    col2.metric("Total Budget", f"${total_budget:,.0f}")
    col3.metric("Active Projects", active_projects)
    col4.metric("Completed Projects", completed_projects)
    
    # Projects by asset class
    st.subheader("Projects by Asset Class")
    query = """
        SELECT ac.class_name, COUNT(p.project_id) as project_count
        FROM asset_class ac
        LEFT JOIN asset_type_l4 at ON ac.asset_class_id = at.asset_class_id
        LEFT JOIN asset a ON at.asset_type_id = a.asset_type_id
        LEFT JOIN project p ON a.asset_id = p.asset_id
        GROUP BY ac.class_name
    """
    df_class = pd.read_sql_query(query, conn)
    if not df_class.empty:
        fig = px.bar(df_class, x='class_name', y='project_count', 
                     title='Projects by Asset Class')
        st.plotly_chart(fig, use_container_width=True)
    
    # Budget allocation by year
    st.subheader("Budget Allocation by Financial Year")
    query = """
        SELECT financial_year, SUM(project_cost) as total_cost
        FROM project_year_cost
        GROUP BY financial_year
        ORDER BY financial_year
    """
    df_year = pd.read_sql_query(query, conn)
    if not df_year.empty:
        fig = px.line(df_year, x='financial_year', y='total_cost',
                      title='Budget by Year', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    
    conn.close()

# Function to import projects from spreadsheet
def import_projects_from_spreadsheet(uploaded_file, conn, overwrite_existing=False):
    """
    Import projects from uploaded spreadsheet file
    Expected columns: asset_code, asset_class, asset_type, description, project_scope,
                     design_status, env_status, whs_score, water_score, customer_score,
                     maintenance_score, financial_score
    """
    try:
        # Read the uploaded file
        if uploaded_file.name.endswith('.xlsx'):
            df = pd.read_excel(uploaded_file)
        elif uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            raise ValueError("Unsupported file format. Please upload CSV or Excel files.")
        
        # Validate required columns
        required_columns = ['asset_code', 'project_scope']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Optional columns with defaults
        optional_columns = {
            'asset_class': 'Bridges & Culverts',
            'asset_type': 'General',
            'description': '',
            'design_status': 'To be assigned',
            'env_status': 'Pending',
            'whs_score': 0,
            'water_score': 0,
            'customer_score': 0,
            'maintenance_score': 0,
            'financial_score': 0
        }
        
        # Add missing optional columns with defaults
        for col, default_val in optional_columns.items():
            if col not in df.columns:
                df[col] = default_val
        
        c = conn.cursor()
        
        # Get reference data mappings
        asset_classes = pd.read_sql_query("SELECT * FROM asset_class", conn)
        design_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
        env_statuses = pd.read_sql_query("SELECT * FROM env_status", conn)
        
        imported_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Check if asset already exists
                c.execute("SELECT asset_id FROM asset WHERE asset_code = ?", (row['asset_code'],))
                existing_asset = c.fetchone()
                
                if existing_asset and not overwrite_existing:
                    errors.append(f"Row {index + 1}: Asset {row['asset_code']} already exists. Use overwrite option to replace.")
                    continue
                
                # Get or create asset class
                asset_class_match = asset_classes[asset_classes['class_name'].str.lower() == str(row['asset_class']).lower()]
                if not asset_class_match.empty:
                    asset_class_id = asset_class_match.iloc[0]['asset_class_id']
                else:
                    # Create new asset class
                    c.execute("INSERT INTO asset_class (class_name) VALUES (?)", (row['asset_class'],))
                    asset_class_id = c.lastrowid
                
                # Get or create asset type
                c.execute("SELECT asset_type_id FROM asset_type_l4 WHERE type_name=? AND asset_class_id=?",
                         (row['asset_type'], asset_class_id))
                asset_type_result = c.fetchone()
                if asset_type_result:
                    asset_type_id = asset_type_result[0]
                else:
                    c.execute("INSERT INTO asset_type_l4 (asset_class_id, type_name) VALUES (?, ?)",
                             (asset_class_id, row['asset_type']))
                    asset_type_id = c.lastrowid
                
                # Get design status ID
                design_status_match = design_statuses[design_statuses['status_name'].str.lower() == str(row['design_status']).lower()]
                design_status_id = design_status_match.iloc[0]['design_status_id'] if not design_status_match.empty else 1
                
                # Get env status ID
                env_status_match = env_statuses[env_statuses['status_name'].str.lower() == str(row['env_status']).lower()]
                env_status_id = env_status_match.iloc[0]['env_status_id'] if not env_status_match.empty else 1
                
                if existing_asset and overwrite_existing:
                    # Update existing asset
                    asset_id = existing_asset[0]
                    c.execute("""UPDATE asset SET asset_type_id=?, description=?, updated_at=CURRENT_TIMESTAMP
                                WHERE asset_id=?""", (asset_type_id, row['description'], asset_id))
                    
                    # Update or create priority score
                    c.execute("SELECT score_id FROM priority_score WHERE asset_id=?", (asset_id,))
                    if c.fetchone():
                        total_score = float(row['whs_score']) + float(row['water_score']) + float(row['customer_score']) + float(row['maintenance_score']) + float(row['financial_score'])
                        c.execute("""UPDATE priority_score SET 
                                    whs_score=?, water_savings_score=?, customer_score=?, 
                                    maintenance_score=?, financial_score=?, total_priority_score=?
                                    WHERE asset_id=?""",
                                 (float(row['whs_score']), float(row['water_score']), float(row['customer_score']),
                                  float(row['maintenance_score']), float(row['financial_score']), total_score, asset_id))
                    else:
                        total_score = float(row['whs_score']) + float(row['water_score']) + float(row['customer_score']) + float(row['maintenance_score']) + float(row['financial_score'])
                        c.execute("""INSERT INTO priority_score 
                                    (asset_id, whs_score, water_savings_score, customer_score, 
                                     maintenance_score, financial_score, total_priority_score)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                 (asset_id, float(row['whs_score']), float(row['water_score']), float(row['customer_score']),
                                  float(row['maintenance_score']), float(row['financial_score']), total_score))
                    
                    # Update project
                    c.execute("""UPDATE project SET project_scope=?, design_status_id=?, env_status_id=?, 
                                updated_at=CURRENT_TIMESTAMP WHERE asset_id=?""",
                             (row['project_scope'], design_status_id, env_status_id, asset_id))
                else:
                    # Create new asset
                    c.execute("""INSERT INTO asset (asset_code, asset_type_id, description) 
                                VALUES (?, ?, ?)""",
                             (row['asset_code'], asset_type_id, row['description']))
                    asset_id = c.lastrowid
                    
                    # Create priority score
                    total_score = float(row['whs_score']) + float(row['water_score']) + float(row['customer_score']) + float(row['maintenance_score']) + float(row['financial_score'])
                    c.execute("""INSERT INTO priority_score 
                                (asset_id, whs_score, water_savings_score, customer_score, 
                                 maintenance_score, financial_score, total_priority_score)
                                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                             (asset_id, float(row['whs_score']), float(row['water_score']), float(row['customer_score']),
                              float(row['maintenance_score']), float(row['financial_score']), total_score))
                    
                    # Create project
                    c.execute("""INSERT INTO project 
                                (asset_id, project_scope, design_status_id, env_status_id)
                                VALUES (?, ?, ?, ?)""",
                             (asset_id, row['project_scope'], design_status_id, env_status_id))
                    project_id = c.lastrowid
                    
                    # Add initial status
                    c.execute("SELECT project_status_id FROM project_status WHERE status_code='PLANNED'")
                    status_id = c.fetchone()[0]
                    c.execute("""INSERT INTO project_status_history 
                                (project_id, project_status_id, status_date, comments)
                                VALUES (?, ?, date('now'), 'Project imported from spreadsheet')""",
                             (project_id, status_id))
                
                imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        conn.commit()
        return imported_count, errors
        
    except Exception as e:
        return 0, [f"File processing error: {str(e)}"]

# Streamlit App
st.set_page_config(page_title="ASAP CAPEX Planning", layout="wide", page_icon="📊")

# Initialize database and check integrity
if 'db_initialized' not in st.session_state:
    init_database()
    check_database_integrity()
    st.session_state.db_initialized = True

# Custom CSS to change tab focus color from red to yellow
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 16px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #cccc66;
        color: #000000;
    }
</style>
""", unsafe_allow_html=True)

# Read configuration
config = read_config()

# Display software registration information
def display_software_info():
    """Display software registration and producer information"""
    if config['show_registration'] or config['show_producer'] or config['show_version']:
        info_parts = []
        if config['show_registration']:
            info_parts.append(f"**Registered to:** {config['registered_to']}")
        if config['show_producer']:
            info_parts.append(f"**Produced by:** {config['produced_by']}")
        if config['show_version']:
            info_parts.append(f"**Version:** {config['version']}")
        
        st.markdown(
            f"<div style='text-align: center; color: white; font-size: 0.9em; margin-bottom: 20px;'>{' | '.join(info_parts)}</div>",
            unsafe_allow_html=True
        )

# Initialize database
init_database()

# Sidebar navigation
st.sidebar.title("🏗️ CAPEX Planning")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Projects", "Add/Edit/Delete Project", "Priority Scoring", 
     "Risk Assessment", "Multi-Year Planning", "Status Tracking", 
     "Project History", "FAQ", "Administration"]
)

# Administration sub-menu
admin_page = None
if page == "Administration":
    st.sidebar.markdown("---")
    admin_page = st.sidebar.radio(
        "Administration Options",
        ["Reference Data", "Backup Data"]
    )

# DASHBOARD
if page == "Dashboard":
    st.title("📊 CAPEX Planning Dashboard")
    display_software_info()
    
    conn = get_db()
    
    col1, col2, col3, col4 = st.columns(4)
    
    # KPIs
    total_projects = pd.read_sql_query("SELECT COUNT(*) as cnt FROM project", conn).iloc[0]['cnt']
    total_budget = pd.read_sql_query(
        "SELECT SUM(project_cost) as total FROM project_year_cost", conn
    ).iloc[0]['total'] or 0
    
    active_projects = pd.read_sql_query(
        """SELECT COUNT(DISTINCT p.project_id) as cnt 
           FROM project p 
           JOIN project_status_history psh ON p.project_id = psh.project_id
           JOIN project_status ps ON psh.project_status_id = ps.project_status_id
           WHERE ps.status_code IN ('IN_PROGRESS', 'DESIGN')""", conn
    ).iloc[0]['cnt']
    
    completed_projects = pd.read_sql_query(
        """SELECT COUNT(DISTINCT p.project_id) as cnt 
           FROM project p 
           JOIN project_status_history psh ON p.project_id = psh.project_id
           JOIN project_status ps ON psh.project_status_id = ps.project_status_id
           WHERE ps.status_code = 'COMPLETED'""", conn
    ).iloc[0]['cnt']
    
    col1.metric("Total Projects", total_projects)
    col2.metric("Total Budget", f"${total_budget:,.0f}")
    col3.metric("Active Projects", active_projects)
    col4.metric("Completed Projects", completed_projects)
    
    # Projects by asset class
    st.subheader("Projects by Asset Class")
    query = """
        SELECT ac.class_name, COUNT(p.project_id) as project_count
        FROM asset_class ac
        LEFT JOIN asset_type_l4 at ON ac.asset_class_id = at.asset_class_id
        LEFT JOIN asset a ON at.asset_type_id = a.asset_type_id
        LEFT JOIN project p ON a.asset_id = p.asset_id
        GROUP BY ac.class_name
    """
    df_class = pd.read_sql_query(query, conn)
    if not df_class.empty:
        fig = px.bar(df_class, x='class_name', y='project_count', 
                     title='Projects by Asset Class')
        st.plotly_chart(fig, use_container_width=True)
    
    # Budget allocation by year
    st.subheader("Budget Allocation by Financial Year")
    query = """
        SELECT financial_year, SUM(project_cost) as total_cost
        FROM project_year_cost
        GROUP BY financial_year
        ORDER BY financial_year
    """
    df_year = pd.read_sql_query(query, conn)
    if not df_year.empty:
        fig = px.line(df_year, x='financial_year', y='total_cost',
                      title='Budget by Year', markers=True)
        st.plotly_chart(fig, use_container_width=True)
    
    conn.close()

# PROJECTS LIST
elif page == "Projects":
    st.title("📋 Projects")
    display_software_info()
    
    # Import Section
    with st.expander("📥 Import Projects from Spreadsheet", expanded=False):
        st.markdown("""
        **Import projects from CSV or Excel files**
        
        **Required columns:**
        - `asset_code` - Unique asset identifier
        - `project_scope` - Description of the project
        
        **Optional columns with defaults:**
        - `asset_class` (default: 'Bridges & Culverts')
        - `asset_type` (default: 'General')
        - `description` (default: empty)
        - `design_status` (default: 'To be assigned')
        - `env_status` (default: 'Pending')
        - `whs_score`, `water_score`, `customer_score`, `maintenance_score`, `financial_score` (default: 0)
        """)
        
        # Create template
        template_data = {
            'asset_code': ['CD-2-001', 'CD-2-002', 'PS-1-001'],
            'asset_class': ['Bridges & Culverts', 'Bridges & Culverts', 'Pumping Stations'],
            'asset_type': ['Culvert', 'Bridge', 'Pump'],
            'description': ['Main road culvert', 'Pedestrian bridge', 'Primary pump station'],
            'project_scope': ['Replace damaged culvert', 'Bridge maintenance', 'Pump upgrade'],
            'design_status': ['To be assigned', 'In progress', 'Completed'],
            'env_status': ['Pending', 'Approved', 'Approved'],
            'whs_score': [8, 6, 9],
            'water_score': [5, 3, 10],
            'customer_score': [7, 8, 6],
            'maintenance_score': [9, 7, 8],
            'financial_score': [6, 5, 7]
        }
        template_df = pd.DataFrame(template_data)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Download template
            csv_template = template_df.to_csv(index=False)
            st.download_button(
                "📥 Download Template (CSV)",
                csv_template,
                "capex_template.csv",
                "text/csv",
                help="Download a template file with sample data and correct column structure"
            )
        
        with col2:
            # Upload file
            uploaded_file = st.file_uploader(
                "Upload CSV or Excel file",
                type=['csv', 'xlsx'],
                help="Select a CSV or Excel file containing project data"
            )
        
        if uploaded_file:
            try:
                # Preview file
                if uploaded_file.name.endswith('.xlsx'):
                    preview_df = pd.read_excel(uploaded_file)
                else:
                    preview_df = pd.read_csv(uploaded_file)
                
                st.subheader("📋 File Preview")
                st.dataframe(preview_df.head(), use_container_width=True)
                st.info(f"File contains {len(preview_df)} rows")
                
                # Validation
                required_cols = ['asset_code', 'project_scope']
                missing_cols = [col for col in required_cols if col not in preview_df.columns]
                
                if missing_cols:
                    st.error(f"❌ Missing required columns: {missing_cols}")
                    
                    # Show helpful guidance
                    st.markdown("### 🔧 How to Fix This:")
                    st.markdown("**Your spreadsheet must have these exact column names:**")
                    st.markdown("- `asset_code` - Unique identifier for each asset (e.g., CD-2-001, PS-1-002)")
                    st.markdown("- `project_scope` - Description of the project work")
                    
                    st.markdown("**📝 Steps to fix your file:**")
                    st.markdown("1. Open your spreadsheet file")
                    st.markdown("2. Check the column headers in the first row")
                    st.markdown("3. Rename or add columns to match the required names exactly")
                    st.markdown("4. Save the file and upload again")
                    
                    st.info("💡 **Tip:** Download the template below to see the correct format!")
                else:
                    st.success("✅ All required columns found")
                    
                    # Import options
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        overwrite = st.checkbox(
                            "⚠️ Overwrite existing projects",
                            help="If checked, existing projects with the same asset code will be updated. If unchecked, they will be skipped."
                        )
                    
                    if overwrite:
                        st.warning("⚠️ **WARNING:** This will overwrite existing projects with matching asset codes!")
                    
                    # Import button
                    if st.button("🚀 Import Projects", type="primary"):
                        with st.spinner("Importing projects..."):
                            conn_import = get_db()
                            imported_count, errors = import_projects_from_spreadsheet(
                                uploaded_file, conn_import, overwrite
                            )
                            conn_import.close()
                            
                            if imported_count > 0:
                                st.success(f"✅ Successfully imported {imported_count} projects!")
                                if errors:
                                    st.warning("⚠️ Some errors occurred:")
                                    for error in errors:
                                        st.write(f"- {error}")
                                st.rerun()  # Refresh the page to show new data
                            else:
                                st.error("❌ No projects were imported")
                                if errors:
                                    st.write("Errors:")
                                    for error in errors:
                                        st.write(f"- {error}")
                        
            except Exception as e:
                st.error(f"❌ Error reading file: {str(e)}")
        
        st.markdown("---")
    
    conn = get_db()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    asset_classes = pd.read_sql_query("SELECT * FROM asset_class", conn)
    selected_class = col1.selectbox(
        "Filter by Asset Class",
        ["All"] + asset_classes['class_name'].tolist()
    )
    
    design_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
    selected_status = col2.selectbox(
        "Filter by Design Status",
        ["All"] + design_statuses['status_name'].tolist()
    )
    
    search = col3.text_input("Search projects", "")
    
    # Load projects
    query = """
        SELECT 
            p.project_id,
            a.asset_code,
            ac.class_name as asset_class,
            p.project_scope,
            ds.status_name as design_status,
            es.status_name as env_status,
            ps.total_priority_score,
            p.priority_rank
        FROM project p
        LEFT JOIN asset a ON p.asset_id = a.asset_id
        LEFT JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
        LEFT JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
        LEFT JOIN design_status ds ON p.design_status_id = ds.design_status_id
        LEFT JOIN env_status es ON p.env_status_id = es.env_status_id
        LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
    """
    
    df_projects = pd.read_sql_query(query, conn)
    
    if not df_projects.empty:
        # Change column heading from asset_code to asset_id
        df_projects = df_projects.rename(columns={'asset_code': 'asset_id'})
        
        if selected_class != "All":
            df_projects = df_projects[df_projects['asset_class'] == selected_class]
        if selected_status != "All":
            df_projects = df_projects[df_projects['design_status'] == selected_status]
        if search:
            df_projects = df_projects[
                df_projects['asset_id'].str.contains(search, case=False, na=False) |
                df_projects['project_scope'].str.contains(search, case=False, na=False)
            ]
        
        st.dataframe(df_projects, use_container_width=True, hide_index=True)
        
        # Export
        csv = df_projects.to_csv(index=False)
        st.download_button(
            "📥 Export to CSV",
            csv,
            "projects.csv",
            "text/csv"
        )
    else:
        st.info("No projects found. Add your first project!")
    
    conn.close()

# ADD/Edit/Delete PROJECT
elif page == "Add/Edit/Delete Project":
    st.title("➕ Add/Edit/Delete Project")
    display_software_info()
    
    conn = get_db()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Add New Project", "Edit Existing Project", "Delete Projects", "Import from Spreadsheet"])
    
    with tab1:
        st.subheader("Create New Project")
        
        with st.form("new_project_form"):
            col1, col2 = st.columns(2)
            
            # Asset details
            asset_code = col1.text_input("Asset ID*", help="e.g., CD-2-892")
            
            asset_classes = pd.read_sql_query("SELECT * FROM asset_class", conn)
            asset_class_id = col1.selectbox(
                "Asset Class*",
                asset_classes['asset_class_id'].tolist(),
                format_func=lambda x: asset_classes[asset_classes['asset_class_id']==x]['class_name'].iloc[0]
            )
            
            comments = col2.text_input("Comments", help="Additional notes or comments")
            description = col2.text_area("Asset Description")
            
            # Project details
            st.subheader("Project Information")
            col3, col4 = st.columns(2)
            
            project_scope = col3.text_area("Project Scope*", help="Describe the project")
            
            design_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
            design_status_id = col3.selectbox(
                "Design Status",
                design_statuses['design_status_id'].tolist(),
                format_func=lambda x: design_statuses[design_statuses['design_status_id']==x]['status_name'].iloc[0]
            )
            
            env_statuses = pd.read_sql_query("SELECT * FROM env_status", conn)
            env_status_id = col4.selectbox(
                "Environmental Status",
                env_statuses['env_status_id'].tolist(),
                format_func=lambda x: env_statuses[env_statuses['env_status_id']==x]['status_name'].iloc[0]
            )
            
            # Priority scoring
            st.subheader("Priority Scoring")
            col5, col6, col7 = st.columns(3)
            
            whs_score = col5.slider("WHS Score", 0, 30, 0, help="Max 30 points")
            water_score = col6.slider("Water Savings Score", 0, 20, 0, help="Max 20 points")
            customer_score = col7.slider("Customer Score", 0, 30, 0, help="Max 30 points")
            
            col8, col9 = st.columns(2)
            maintenance_score = col8.slider("Maintenance Score", 0, 10, 0, help="Max 10 points")
            financial_score = col9.slider("Financial Score", 0, 10, 0, help="Max 10 points")
            
            total_score = whs_score + water_score + customer_score + maintenance_score + financial_score
            st.info(f"**Total Priority Score: {total_score}**")
            
            submitted = st.form_submit_button("Create Project")
            
            if submitted:
                if not asset_code or not project_scope:
                    st.error("Please fill in all required fields marked with *")
                else:
                    try:
                        c = conn.cursor()
                        
                        # Check if asset type exists, if not create it
                        c.execute("SELECT asset_type_id FROM asset_type_l4 WHERE type_name=? AND asset_class_id=?",
                                 (comments, asset_class_id))
                        result = c.fetchone()
                        if result:
                            asset_type_id = result[0]
                        else:
                            c.execute("INSERT INTO asset_type_l4 (asset_class_id, type_name) VALUES (?, ?)",
                                     (asset_class_id, comments))
                            asset_type_id = c.lastrowid
                        
                        # Create asset
                        c.execute("""INSERT INTO asset (asset_code, asset_type_id, description) 
                                    VALUES (?, ?, ?)""",
                                 (asset_code, asset_type_id, description))
                        asset_id = c.lastrowid
                        
                        # Create priority score
                        c.execute("""INSERT INTO priority_score 
                                    (asset_id, whs_score, water_savings_score, customer_score, 
                                     maintenance_score, financial_score, total_priority_score)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                 (asset_id, whs_score, water_score, customer_score, 
                                  maintenance_score, financial_score, total_score))
                        
                        # Create project
                        c.execute("""INSERT INTO project 
                                    (asset_id, project_scope, design_status_id, env_status_id)
                                    VALUES (?, ?, ?, ?)""",
                                 (asset_id, project_scope, design_status_id, env_status_id))
                        project_id = c.lastrowid
                        
                        # Add initial status
                        c.execute("SELECT project_status_id FROM project_status WHERE status_code='PLANNED'")
                        status_id = c.fetchone()[0]
                        c.execute("""INSERT INTO project_status_history 
                                    (project_id, project_status_id, status_date, comments)
                                    VALUES (?, ?, date('now'), 'Project created')""",
                                 (project_id, status_id))
                        
                        conn.commit()
                        st.success(f"✅ Project created successfully! Project ID: {project_id}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error creating project: {str(e)}")
    
    with tab2:
        st.subheader("Edit Existing Project")
        
        # Get all projects for editing with full details
        projects_query = """
            SELECT p.project_id, a.asset_id, a.asset_code, a.description as asset_description,
                   p.project_scope, p.design_status_id, p.env_status_id,
                   at.type_name as comments, ac.asset_class_id,
                   ps.whs_score, ps.water_savings_score, ps.customer_score, 
                   ps.maintenance_score, ps.financial_score, ps.total_priority_score
            FROM project p
            JOIN asset a ON p.asset_id = a.asset_id
            JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
            JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
            LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
            ORDER BY a.asset_code
        """
        projects_df = pd.read_sql_query(projects_query, conn)
        
        if not projects_df.empty:
            # Project selection
            project_options = [f"{row['asset_code']} - {row['project_scope'][:50]}..." 
                             for _, row in projects_df.iterrows()]
            selected_idx = st.selectbox("Select Project to Edit", range(len(project_options)),
                                      format_func=lambda x: project_options[x])
            
            selected_row = projects_df.iloc[selected_idx]
            selected_project = selected_row['project_id']
            selected_asset = selected_row['asset_id']
            
            # Edit form
            with st.form("edit_project_form"):
                col1, col2 = st.columns(2)
                
                # Asset details
                asset_code = col1.text_input("Asset ID*", value=selected_row['asset_code'], 
                                           help="e.g., CD-2-892")
                
                asset_classes = pd.read_sql_query("SELECT * FROM asset_class", conn)
                current_class_idx = asset_classes[asset_classes['asset_class_id']==selected_row['asset_class_id']].index[0]
                asset_class_id = col1.selectbox(
                    "Asset Class*",
                    asset_classes['asset_class_id'].tolist(),
                    index=int(current_class_idx),
                    format_func=lambda x: asset_classes[asset_classes['asset_class_id']==x]['class_name'].iloc[0]
                )
                
                comments = col2.text_input("Comments", value=selected_row['comments'] or "", 
                                         help="Additional notes or comments")
                description = col2.text_area("Asset Description", 
                                           value=selected_row['asset_description'] or "")
                
                # Project details
                st.subheader("Project Information")
                col3, col4 = st.columns(2)
                
                project_scope = col3.text_area("Project Scope*", value=selected_row['project_scope'],
                                              help="Describe the project")
                
                design_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
                current_design_idx = design_statuses[design_statuses['design_status_id']==selected_row['design_status_id']].index[0]
                design_status_id = col3.selectbox(
                    "Design Status",
                    design_statuses['design_status_id'].tolist(),
                    index=int(current_design_idx),
                    format_func=lambda x: design_statuses[design_statuses['design_status_id']==x]['status_name'].iloc[0]
                )
                
                env_statuses = pd.read_sql_query("SELECT * FROM env_status", conn)
                current_env_idx = env_statuses[env_statuses['env_status_id']==selected_row['env_status_id']].index[0]
                env_status_id = col4.selectbox(
                    "Environmental Status",
                    env_statuses['env_status_id'].tolist(),
                    index=int(current_env_idx),
                    format_func=lambda x: env_statuses[env_statuses['env_status_id']==x]['status_name'].iloc[0]
                )
                
                # Priority scoring
                st.subheader("Priority Scoring")
                col5, col6, col7 = st.columns(3)
                
                whs_score = col5.slider("WHS Score", 0, 30, int(selected_row['whs_score'] or 0), 
                                       help="Max 30 points")
                water_score = col6.slider("Water Savings Score", 0, 20, int(selected_row['water_savings_score'] or 0), 
                                         help="Max 20 points")
                customer_score = col7.slider("Customer Score", 0, 30, int(selected_row['customer_score'] or 0), 
                                           help="Max 30 points")
                
                col8, col9 = st.columns(2)
                maintenance_score = col8.slider("Maintenance Score", 0, 10, int(selected_row['maintenance_score'] or 0), 
                                               help="Max 10 points")
                financial_score = col9.slider("Financial Score", 0, 10, int(selected_row['financial_score'] or 0), 
                                             help="Max 10 points")
                
                total_score = whs_score + water_score + customer_score + maintenance_score + financial_score
                current_total = selected_row['total_priority_score'] or 0
                
                if total_score != current_total:
                    st.warning(f"**Priority Score Changed: {current_total} → {total_score}**")
                else:
                    st.info(f"**Current Priority Score: {total_score}**")
                
                submitted = st.form_submit_button("Update Project")
                
                if submitted:
                    if not asset_code or not project_scope:
                        st.error("Please fill in all required fields marked with *")
                    else:
                        try:
                            c = conn.cursor()
                            
                            # Update asset code
                            c.execute("UPDATE asset SET asset_code=?, description=? WHERE asset_id=?",
                                     (asset_code, description, selected_asset))
                            
                            # Check if asset type exists for the comments, if not create it
                            c.execute("SELECT asset_type_id FROM asset_type_l4 WHERE type_name=? AND asset_class_id=?",
                                     (comments, asset_class_id))
                            result = c.fetchone()
                            if result:
                                asset_type_id = result[0]
                            else:
                                c.execute("INSERT INTO asset_type_l4 (asset_class_id, type_name) VALUES (?, ?)",
                                         (asset_class_id, comments))
                                asset_type_id = c.lastrowid
                            
                            # Update asset type
                            c.execute("UPDATE asset SET asset_type_id=? WHERE asset_id=?",
                                     (asset_type_id, selected_asset))
                            
                            # Update or insert priority score
                            c.execute("SELECT COUNT(*) FROM priority_score WHERE asset_id=?", (selected_asset,))
                            if c.fetchone()[0] > 0:
                                c.execute("""UPDATE priority_score SET 
                                           whs_score=?, water_savings_score=?, customer_score=?, 
                                           maintenance_score=?, financial_score=?, total_priority_score=?
                                           WHERE asset_id=?""",
                                         (whs_score, water_score, customer_score, 
                                          maintenance_score, financial_score, total_score, selected_asset))
                            else:
                                c.execute("""INSERT INTO priority_score 
                                           (asset_id, whs_score, water_savings_score, customer_score, 
                                            maintenance_score, financial_score, total_priority_score)
                                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                         (selected_asset, whs_score, water_score, customer_score, 
                                          maintenance_score, financial_score, total_score))
                            
                            # Update project
                            c.execute("""UPDATE project SET 
                                       project_scope=?, design_status_id=?, env_status_id=?
                                       WHERE project_id=?""",
                                     (project_scope, design_status_id, env_status_id, selected_project))
                            
                            conn.commit()
                            st.success("✅ Project updated successfully!")
                            st.rerun()  # Refresh to show updated values
                        except Exception as e:
                            st.error(f"Error updating project: {str(e)}")
        else:
            st.info("No projects available to edit.")
    
    with tab3:
        st.subheader("Delete Projects")
        
        # Get all projects with details for deletion
        delete_query = """
        SELECT p.project_id, a.asset_code, ac.class_name, p.project_scope, 
               ps.total_priority_score,
               ds.status_name as design_status, es.status_name as env_status
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
        JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
        JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
        LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
        LEFT JOIN design_status ds ON p.design_status_id = ds.design_status_id
        LEFT JOIN env_status es ON p.env_status_id = es.env_status_id
        ORDER BY ps.total_priority_score DESC
        """
        
        projects_df = pd.read_sql_query(delete_query, conn)
        
        if not projects_df.empty:
            # Filter options
            st.subheader("Filter Projects")
            col1, col2 = st.columns(2)
            
            with col1:
                # Asset class filter
                all_classes = ["All"] + sorted(projects_df['class_name'].dropna().unique().tolist())
                selected_class = st.selectbox("Filter by Asset Class", all_classes)
            
            with col2:
                # Design status filter
                all_statuses = ["All"] + sorted(projects_df['design_status'].dropna().unique().tolist())
                selected_status = st.selectbox("Filter by Design Status", all_statuses)
            
            # Apply filters
            filtered_df = projects_df.copy()
            
            if selected_class != "All":
                filtered_df = filtered_df[filtered_df['class_name'] == selected_class]
            
            if selected_status != "All":
                filtered_df = filtered_df[filtered_df['design_status'] == selected_status]
                filtered_df = filtered_df[filtered_df['class_name'] == selected_class]
            
            if selected_status != "All":
                filtered_df = filtered_df[filtered_df['design_status'] == selected_status]
            
            # Display filterable table
            st.subheader("Projects Available for Deletion")
            
            if not filtered_df.empty:
                # Prepare display columns
                display_df = filtered_df[['asset_code', 'class_name', 'project_scope', 
                                        'total_priority_score', 'design_status', 'env_status']].copy()
                
                display_df.columns = ['Asset Id', 'Asset Class', 'Project Scope', 
                                    'Priority Score', 'Design Status', 'Env Status']
                
                # Show table with selection
                selected_indices = st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    selection_mode="single-row",
                    on_select="rerun",
                    key="delete_projects_table"
                )
                
                # Handle deletion
                if selected_indices.selection.rows:
                    selected_idx = selected_indices.selection.rows[0]
                    selected_project = filtered_df.iloc[selected_idx]
                    
                    st.warning(f"**Selected Project for Deletion:**")
                    st.write(f"- **Asset Id:** {selected_project['asset_code']}")
                    st.write(f"- **Project Scope:** {selected_project['project_scope']}")
                    st.write(f"- **Priority Score:** {selected_project['total_priority_score']}" if pd.notnull(selected_project['total_priority_score']) else "Priority Score: N/A")
                    
                    # Confirmation dialog
                    st.error("⚠️ **Warning: This action cannot be undone!**")
                    
                    col_yes, col_no = st.columns(2)
                    
                    with col_yes:
                        if st.button("🗑️ Yes, Delete Project", type="primary", use_container_width=True):
                            try:
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM project WHERE project_id = ?", (selected_project['project_id'],))
                                conn.commit()
                                st.success("✅ Project deleted successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting project: {str(e)}")
                    
                    with col_no:
                        if st.button("❌ No, Cancel Delete", use_container_width=True):
                            st.info("🚫 Delete Project Cancelled")
                            # Clear the selection and refresh the table
                            if 'delete_projects_table' in st.session_state:
                                del st.session_state['delete_projects_table']
                            st.rerun()
                            
            else:
                st.info("No projects match the selected filters.")
        else:
            st.info("No projects available to delete.")
    
    with tab4:
        st.subheader("Import Projects from Spreadsheet")
        
        st.markdown("""
        **⚠️ Import Warning**: This process will import projects from a spreadsheet file. 
        
        **Important Notes:**
        - If projects with the same asset codes already exist, you can choose to overwrite them
        - Overwriting will replace ALL data for existing projects including priority scores
        - New asset classes and types will be created automatically if they don't exist
        - Always backup your data before importing
        """)
        
        # File upload
        uploaded_file = st.file_uploader(
            "Choose spreadsheet file", 
            type=['csv', 'xlsx'],
            help="Upload CSV or Excel file with project data"
        )
        
        if uploaded_file is not None:
            # Show file preview
            try:
                if uploaded_file.name.endswith('.xlsx'):
                    preview_df = pd.read_excel(uploaded_file, nrows=5)
                else:
                    preview_df = pd.read_csv(uploaded_file, nrows=5)
                
                st.subheader("File Preview (First 5 rows)")
                st.dataframe(preview_df, use_container_width=True)
                
                # Show expected format
                st.subheader("Expected Column Format")
                st.markdown("""
                **Required columns:**
                - `asset_code`: Unique identifier for the asset (e.g., CD-2-892)
                - `project_scope`: Description of the project work
                
                **Optional columns (will use defaults if missing):**
                - `asset_class`: Asset class name (default: 'Bridges & Culverts')
                - `asset_type`: Asset type name (default: 'General')
                - `description`: Asset description (default: empty)
                - `design_status`: Design status (default: 'To be assigned')
                - `env_status`: Environmental status (default: 'Pending')
                - `whs_score`: WHS score 0-30 (default: 0)
                - `water_score`: Water savings score 0-20 (default: 0)
                - `customer_score`: Customer score 0-30 (default: 0)
                - `maintenance_score`: Maintenance score 0-10 (default: 0)
                - `financial_score`: Financial score 0-10 (default: 0)
                """)
                
                # Import options
                st.subheader("Import Options")
                
                # Check for existing projects
                existing_assets = []
                try:
                    full_df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('.xlsx') else pd.read_csv(uploaded_file)
                    if 'asset_code' in full_df.columns:
                        asset_codes = full_df['asset_code'].tolist()
                        existing_query = f"SELECT asset_code FROM asset WHERE asset_code IN ({','.join(['?' for _ in asset_codes])})"
                        existing_df = pd.read_sql_query(existing_query, conn, params=asset_codes)
                        existing_assets = existing_df['asset_code'].tolist()
                except Exception as e:
                    st.error(f"Error checking existing assets: {str(e)}")
                
                if existing_assets:
                    st.warning(f"⚠️ Found {len(existing_assets)} existing projects with matching asset codes:")
                    st.write(existing_assets)
                    
                    overwrite_option = st.checkbox(
                        "⚠️ OVERWRITE existing projects", 
                        value=False,
                        help="Check this box to replace existing projects. This action cannot be undone!"
                    )
                    
                    if overwrite_option:
                        st.error("⚠️ WARNING: You have selected to overwrite existing projects. This will replace all data for matching asset codes!")
                else:
                    overwrite_option = False
                    st.success("✅ No existing projects found with matching asset codes. Safe to import.")
                
                # Import button
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    if st.button("🚀 Import Projects", type="primary"):
                        if existing_assets and not overwrite_option:
                            st.error("Cannot import: Existing projects found. Please check the overwrite option or remove duplicate asset codes from your file.")
                        else:
                            with st.spinner("Importing projects..."):
                                imported_count, errors = import_projects_from_spreadsheet(uploaded_file, conn, overwrite_option)
                            
                            if imported_count > 0:
                                st.success(f"✅ Successfully imported {imported_count} projects!")
                            
                            if errors:
                                st.error("❌ Some rows had errors:")
                                for error in errors[:10]:  # Show first 10 errors
                                    st.write(f"- {error}")
                                if len(errors) > 10:
                                    st.write(f"... and {len(errors) - 10} more errors")
                
                with col2:
                    st.info("💡 Tip: Start with a small test file to verify the format before importing large datasets.")
                
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
        else:
            # Show template download
            st.subheader("Download Template")
            st.markdown("Don't have a spreadsheet ready? Download this template to get started:")
            
            template_data = {
                'asset_code': ['CD-2-001', 'CD-2-002', 'PS-1-001'],
                'asset_class': ['Bridges & Culverts', 'Bridges & Culverts', 'Pump Stations & Facilities'],
                'asset_type': ['Road Bridge', 'Railway Bridge', 'Water Pump Station'],
                'description': ['Main road bridge over river', 'Railway crossing bridge', 'Primary water pumping facility'],
                'project_scope': ['Bridge deck replacement and structural repairs', 'Bridge inspection and maintenance', 'Pump upgrade and efficiency improvements'],
                'design_status': ['To be assigned', 'Under Development', 'For Review'],
                'env_status': ['Pending', 'Pending', 'Complete'],
                'whs_score': [25, 15, 20],
                'water_score': [5, 10, 18],
                'customer_score': [20, 15, 25],
                'maintenance_score': [8, 6, 9],
                'financial_score': [7, 5, 8]
            }
            
            template_df = pd.DataFrame(template_data)
            
            # Show template preview
            st.dataframe(template_df, use_container_width=True)
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                csv_template = template_df.to_csv(index=False)
                st.download_button(
                    "📥 Download CSV Template",
                    csv_template,
                    "project_import_template.csv",
                    "text/csv"
                )
            
            with col2:
                # For Excel download, we'll create a simple CSV version
                excel_buffer = template_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Excel Template",
                    excel_buffer,
                    "project_import_template.xlsx",
                    "application/vnd.ms-excel"
                )
    
    conn.close()

# RISK ASSESSMENT
elif page == "Priority Scoring":
    st.title("🎯 Priority Scoring")
    display_software_info()
    
    conn = get_db()
    
    st.markdown("""
    Projects are scored across 5 criteria with different weights:
    - **WHS (30%)**: Work Health & Safety considerations
    - **Water Savings (20%)**: Potential water conservation impact
    - **Customer (30%)**: Impact on customer service
    - **Maintenance/Ops (10%)**: Operational and maintenance implications
    - **Financial (10%)**: Financial considerations
    """)
    
    # Load all projects with scores
    query = """
        SELECT 
            p.project_id,
            a.asset_code,
            p.project_scope,
            ps.whs_score,
            ps.water_savings_score,
            ps.customer_score,
            ps.maintenance_score,
            ps.financial_score,
            ps.total_priority_score,
            p.priority_rank
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
        LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
        ORDER BY ps.total_priority_score DESC
    """
    
    df_scores = pd.read_sql_query(query, conn)
    
    if not df_scores.empty:
        # Change column heading from asset_code to asset_id for consistency
        df_scores = df_scores.rename(columns={'asset_code': 'asset_id'})
        
        # Update rankings based on scores
        c = conn.cursor()
        for rank, row in enumerate(df_scores.sort_values('total_priority_score', ascending=False).itertuples(), 1):
            c.execute("UPDATE project SET priority_rank=? WHERE project_id=?", 
                     (rank, row.project_id))
        conn.commit()
        
        # Display top projects
        st.subheader("Top Priority Projects")
        top_projects = df_scores.head(20)
        
        # Create visualization
        fig = px.bar(top_projects, 
                    x='asset_id', 
                    y=['whs_score', 'water_savings_score', 'customer_score', 
                       'maintenance_score', 'financial_score'],
                    title='Priority Score Breakdown - Top 20 Projects',
                    labels={'value': 'Score', 'variable': 'Criterion'},
                    barmode='stack')
        st.plotly_chart(fig, use_container_width=True)
        
        # Display table
        st.dataframe(df_scores, use_container_width=True, hide_index=True)
        
        # Recalculate scores option
        if st.button("🔄 Recalculate All Rankings"):
            st.success("Rankings recalculated successfully!")
            st.rerun()
    else:
        st.info("No projects with scores found. Add projects first.")
    
    conn.close()

# RISK ASSESSMENT
elif page == "Risk Assessment":
    st.title("⚠️ Risk Assessment")
    
    conn = get_db()
    
    st.markdown("""
    Risk assessment combines **Likelihood** and **Consequence** scores to determine overall risk rating.
    The risk matrix helps prioritize projects based on potential impacts.
    
    **How to use the Risk Matrix:**
    - The first column shows **Consequence** levels (from Catastrophic to Low)
    - The other columns show **Likelihood** levels (from Rare to Almost Certain)
    - Find the intersection of consequence and likelihood to determine the risk level
    """)
    
    # Display risk matrix
    st.subheader("Risk Matrix")
    
    risk_matrix_data = {
        'Consequence': ['Catastrophic', 'Very High', 'High', 'Medium', 'Low'],
        'Rare': ['High', 'Moderate', 'Moderate', 'Low', 'Low'],
        'Unlikely': ['High', 'High', 'Moderate', 'Moderate', 'Low'],
        'Occasional': ['High', 'High', 'High', 'Moderate', 'Moderate'],
        'Likely': ['Extreme', 'High', 'High', 'High', 'Moderate'],
        'Highly Likely': ['Extreme', 'Extreme', 'High', 'High', 'Moderate'],
        'Almost Certain': ['Extreme', 'Extreme', 'Extreme', 'High', 'High']
    }
    
    df_matrix = pd.DataFrame(risk_matrix_data)
    
    # Define color mapping for risk levels
    def get_risk_color(val):
        if val == 'Low':
            return 'background-color: #28a745; color: white; font-weight: bold'  # Green
        elif val == 'Moderate':
            return 'background-color: #ffc107; color: black; font-weight: bold'  # Yellow
        elif val == 'High':
            return 'background-color: #fd7e14; color: white; font-weight: bold'  # Orange
        elif val == 'Extreme':
            return 'background-color: #8b0000; color: white; font-weight: bold'  # Dark Red
        else:
            return ''  # No styling for other values
    
    # Define light grey styling for consequence column
    def get_consequence_color(val):
        return 'background-color: #f8f9fa; color: black; font-weight: bold'  # Light grey
    
    # Apply styling to risk matrix
    def style_risk_matrix(df):
        # Create a styler object
        styler = df.style
        
        # Apply light grey background to the first column (Consequence)
        styler = styler.map(get_consequence_color, subset=['Consequence'])
        
        # Apply color coding to all columns except the first one (Consequence)
        for col in df.columns[1:]:  # Skip 'Consequence' column
            styler = styler.map(get_risk_color, subset=[col])
        
        # Apply light grey background to headers
        styler = styler.set_table_styles([
            {'selector': 'thead th', 'props': [
                ('background-color', '#f8f9fa'),
                ('color', 'black'),
                ('font-weight', 'bold'),
                ('text-align', 'center')
            ]}
        ])
        
        return styler
    
    # Display the styled risk matrix
    styled_matrix = style_risk_matrix(df_matrix)
    st.dataframe(styled_matrix, use_container_width=True, hide_index=True)
    
    # Add color legend
    st.markdown("""
    **Risk Matrix Color Legend:**
    - ⬜ **Headers & Consequence Column**: Light Grey (reference information)
    - 🟢 **Low**: Green
    - 🟡 **Moderate**: Yellow  
    - 🟠 **High**: Orange
    - 🔴 **Extreme**: Dark Red
    """)
    
    # Add risk assessment
    st.subheader("Add Risk Assessment")
    
    projects = pd.read_sql_query("""
        SELECT p.project_id, a.asset_code, p.project_scope
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
    """, conn)
    
    if not projects.empty:
        with st.form("risk_assessment_form"):
            selected_project = st.selectbox(
                "Select Project",
                projects['project_id'].tolist(),
                format_func=lambda x: f"{projects[projects['project_id']==x]['asset_code'].iloc[0]} - {projects[projects['project_id']==x]['project_scope'].iloc[0][:50]}"
            )
            
            col1, col2 = st.columns(2)
            
            consequences = pd.read_sql_query("SELECT * FROM consequence", conn)
            consequence_id = col1.selectbox(
                "Consequence",
                consequences['consequence_id'].tolist(),
                format_func=lambda x: consequences[consequences['consequence_id']==x]['description'].iloc[0]
            )
            
            likelihoods = pd.read_sql_query("SELECT * FROM likelihood", conn)
            likelihood_id = col2.selectbox(
                "Likelihood",
                likelihoods['likelihood_id'].tolist(),
                format_func=lambda x: likelihoods[likelihoods['likelihood_id']==x]['description'].iloc[0]
            )
            
            # Calculate risk rating
            cons_score = consequences[consequences['consequence_id']==consequence_id]['score'].iloc[0]
            like_score = likelihoods[likelihoods['likelihood_id']==likelihood_id]['score'].iloc[0]
            risk_score = cons_score + like_score
            
            # Show the calculation to the user
            st.markdown(f"**Risk Calculation:** Consequence Score ({cons_score}) + Likelihood Score ({like_score}) = {risk_score}")
            
            if risk_score <= 3:
                risk_rating = "Low"
            elif risk_score <= 6:
                risk_rating = "Moderate"
            elif risk_score <= 9:
                risk_rating = "High"
            else:
                risk_rating = "Extreme"
            
            # Display calculated risk rating with color coding
            if risk_rating == "Low":
                st.markdown(f'<div style="background-color: #28a745; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">Calculated Risk Rating: {risk_rating}</div>', unsafe_allow_html=True)
            elif risk_rating == "Moderate":
                st.markdown(f'<div style="background-color: #ffc107; color: black; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">Calculated Risk Rating: {risk_rating}</div>', unsafe_allow_html=True)
            elif risk_rating == "High":
                st.markdown(f'<div style="background-color: #fd7e14; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">Calculated Risk Rating: {risk_rating}</div>', unsafe_allow_html=True)
            elif risk_rating == "Extreme":
                st.markdown(f'<div style="background-color: #8b0000; color: white; padding: 10px; border-radius: 5px; text-align: center; font-weight: bold;">Calculated Risk Rating: {risk_rating}</div>', unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Add Risk Assessment")
            
            if submitted:
                c = conn.cursor()
                c.execute("""INSERT INTO risk_assessment 
                            (project_id, consequence_id, likelihood_id, risk_rating)
                            VALUES (?, ?, ?, ?)""",
                         (selected_project, consequence_id, likelihood_id, risk_rating))
                conn.commit()
                st.success("✅ Risk assessment added successfully!")
    
    # Display existing assessments
    st.subheader("Risk Assessments")
    
    st.markdown("""
    **Note:** The Risk Rating column is color-coded to match the Risk Matrix above:
    - 🟢 Low | 🟡 Moderate | 🟠 High | 🔴 Extreme
    """)
    
    query = """
        SELECT 
            a.asset_code,
            p.project_scope,
            c.description as consequence,
            l.description as likelihood,
            ra.risk_rating
        FROM risk_assessment ra
        JOIN project p ON ra.project_id = p.project_id
        JOIN asset a ON p.asset_id = a.asset_id
        JOIN consequence c ON ra.consequence_id = c.consequence_id
        JOIN likelihood l ON ra.likelihood_id = l.likelihood_id
    """
    df_risk = pd.read_sql_query(query, conn)
    
    if not df_risk.empty:
        # Apply color styling to the risk_rating column
        def style_risk_assessments_table(df):
            # Create a styler object
            styler = df.style
            
            # Apply the same risk color function to the risk_rating column
            styler = styler.map(get_risk_color, subset=['risk_rating'])
            
            return styler
        
        # Display the styled risk assessments table
        styled_risk_table = style_risk_assessments_table(df_risk)
        st.dataframe(styled_risk_table, use_container_width=True, hide_index=True)
    else:
        st.info("No risk assessments have been added yet.")
    
    conn.close()

# MULTI-YEAR PLANNING
elif page == "Multi-Year Planning":
    st.title("📅 Multi-Year Planning")
    
    conn = get_db()
    
    st.markdown("Plan project costs across multiple financial years.")
    
    tab1, tab2, tab3 = st.tabs(["1 Year Plan", "3 Year Plan", "10 Year Plan"])
    
    with tab1:
        st.subheader("FY 2024-25 Projects")
        query = """
            SELECT 
                a.asset_code,
                ac.class_name,
                p.project_scope,
                pyc.project_cost,
                pyc.customer_contribution
            FROM project_year_cost pyc
            JOIN project p ON pyc.project_id = p.project_id
            JOIN asset a ON p.asset_id = a.asset_id
            JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
            JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
            WHERE pyc.financial_year = 'FY 24-25'
        """
        df_1yr = pd.read_sql_query(query, conn)
        
        if not df_1yr.empty:
            st.dataframe(df_1yr, use_container_width=True, hide_index=True)
            st.metric("Total Budget FY 24-25", f"${df_1yr['project_cost'].sum():,.0f}")
        else:
            st.info("No projects planned for FY 24-25")
    
    with tab2:
        st.subheader("3 Year Program (FY 24-25 to FY 26-27)")
        
        years = ['FY 24-25', 'FY 25-26', 'FY 26-27']
        query = """
            SELECT 
                ac.class_name,
                pyc.financial_year,
                SUM(pyc.project_cost) as total_cost
            FROM project_year_cost pyc
            JOIN project p ON pyc.project_id = p.project_id
            JOIN asset a ON p.asset_id = a.asset_id
            JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
            JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
            WHERE pyc.financial_year IN ('FY 24-25', 'FY 25-26', 'FY 26-27')
            GROUP BY ac.class_name, pyc.financial_year
        """
        df_3yr = pd.read_sql_query(query, conn)
        
        if not df_3yr.empty:
            # Pivot for better display
            df_pivot = df_3yr.pivot(index='class_name', columns='financial_year', values='total_cost').fillna(0)
            st.dataframe(df_pivot, use_container_width=True)
            
            # Visualization
            fig = px.bar(df_3yr, x='financial_year', y='total_cost', color='class_name',
                        title='3-Year Budget by Asset Class')
            
            # Improve x-axis spacing and formatting
            fig.update_layout(
                xaxis=dict(
                    title="Financial Year",
                    tickmode='array',
                    tickvals=['FY 24-25', 'FY 25-26', 'FY 26-27'],
                    ticktext=['FY 24-25', 'FY 25-26', 'FY 26-27'],
                    tickangle=0,
                    tickfont=dict(size=12),
                    categoryorder='array',
                    categoryarray=['FY 24-25', 'FY 25-26', 'FY 26-27']
                ),
                yaxis=dict(
                    title="Budget Amount ($)"
                ),
                bargap=0.3,  # Add space between year groups
                bargroupgap=0.1  # Add space between bars within groups
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No 3-year program data available")
    
    with tab3:
        st.subheader("10 Year Program")
        
        query = """
            SELECT 
                ac.class_name,
                pyc.financial_year,
                SUM(pyc.project_cost) as total_cost
            FROM project_year_cost pyc
            JOIN project p ON pyc.project_id = p.project_id
            JOIN asset a ON p.asset_id = a.asset_id
            JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
            JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
            GROUP BY ac.class_name, pyc.financial_year
            ORDER BY pyc.financial_year, ac.class_name
        """
        df_10yr = pd.read_sql_query(query, conn)
        
        if not df_10yr.empty:
            # Pivot for better display
            df_pivot = df_10yr.pivot(index='class_name', columns='financial_year', values='total_cost').fillna(0)
            st.dataframe(df_pivot, use_container_width=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Budget forecast line chart (total by year)
                df_total_by_year = df_10yr.groupby('financial_year')['total_cost'].sum().reset_index()
                fig1 = px.line(df_total_by_year, x='financial_year', y='total_cost',
                              title='10-Year Budget Forecast', markers=True)
                
                # Improve x-axis formatting for better readability
                fig1.update_layout(
                    xaxis=dict(
                        title="Financial Year",
                        tickangle=45,  # Angle the labels for better fit
                        tickfont=dict(size=10)
                    ),
                    yaxis=dict(
                        title="Budget Amount ($)"
                    )
                )
                
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                # Stacked bar chart by Asset Class
                fig2 = px.bar(df_10yr, x='financial_year', y='total_cost', color='class_name',
                             title='10 Year Budget by Asset Class')
                
                # Improve x-axis formatting for better readability
                fig2.update_layout(
                    xaxis=dict(
                        title="Financial Year",
                        tickangle=45,  # Angle the labels for better fit
                        tickfont=dict(size=10)
                    ),
                    yaxis=dict(
                        title="Budget Amount ($)"
                    ),
                    bargap=0.2,  # Add some space between bars
                    legend=dict(
                        title="Asset Class",
                        orientation="v",
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=1.02
                    )
                )
                
                st.plotly_chart(fig2, use_container_width=True)
            
            st.dataframe(df_10yr, use_container_width=True, hide_index=True)
        else:
            st.info("No 10-year program data available")
    
    # Add costs to projects
    st.subheader("Add/Edit Project Costs")
    
    # Show existing cost entries for reference
    existing_costs = pd.read_sql_query("""
        SELECT pyc.cost_id, a.asset_code, p.project_scope, pyc.financial_year, 
               pyc.project_cost, pyc.customer_contribution, pyc.summary_txt
        FROM project_year_cost pyc
        JOIN project p ON pyc.project_id = p.project_id
        JOIN asset a ON p.asset_id = a.asset_id
        ORDER BY a.asset_code, pyc.financial_year
    """, conn)
    
    if not existing_costs.empty:
        st.write("**Existing Cost Entries:**")
        display_costs = existing_costs[['asset_code', 'financial_year', 'project_cost', 'customer_contribution']].copy()
        display_costs.columns = ['Asset Id', 'Financial Year', 'Project Cost ($)', 'Customer Contribution ($)']
        st.dataframe(display_costs, use_container_width=True, hide_index=True)
    
    projects = pd.read_sql_query("""
        SELECT p.project_id, a.asset_code, p.project_scope
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
    """, conn)
    
    if not projects.empty:
        # Create two columns for Add and Edit buttons
        col_add, col_edit = st.columns(2)
        
        with col_add:
            st.write("**Add New Cost Entry**")
            with st.form("add_costs_form"):
                selected_project = st.selectbox(
                    "Select Project",
                    projects['project_id'].tolist(),
                    format_func=lambda x: f"{projects[projects['project_id']==x]['asset_code'].iloc[0]}",
                    key="add_project"
                )
                
                financial_year = st.selectbox(
                    "Financial Year",
                    ['FY 24-25', 'FY 25-26', 'FY 26-27', 'FY 27-28', 'FY 28-29', 
                     'FY 29-30', 'FY 30-31', 'FY 31-32', 'FY 32-33', 'FY 33-34'],
                    key="add_year"
                )
                
                project_cost = st.number_input("Project Cost ($)", min_value=0, value=0, step=1000, key="add_cost")
                customer_contrib = st.number_input("Customer Contribution ($)", min_value=0, value=0, step=1000, key="add_contrib")
                
                summary = st.text_area("Summary", key="add_summary")
                
                submitted = st.form_submit_button("Add Cost Entry")
                
                if submitted:
                    c = conn.cursor()
                    c.execute("""INSERT INTO project_year_cost 
                                (project_id, financial_year, project_cost, customer_contribution, summary_txt)
                                VALUES (?, ?, ?, ?, ?)""",
                             (selected_project, financial_year, project_cost, customer_contrib, summary))
                    conn.commit()
                    st.success("✅ Cost entry added successfully!")
                    st.rerun()
        
        with col_edit:
            st.write("**Edit Existing Cost Entry**")
            if not existing_costs.empty:
                with st.form("edit_costs_form"):
                    # Select existing cost entry to edit
                    selected_cost = st.selectbox(
                        "Select Cost Entry to Edit",
                        existing_costs['cost_id'].tolist(),
                        format_func=lambda x: f"{existing_costs[existing_costs['cost_id']==x]['asset_code'].iloc[0]} - {existing_costs[existing_costs['cost_id']==x]['financial_year'].iloc[0]}",
                        key="edit_cost_id"
                    )
                    
                    if selected_cost:
                        cost_data = existing_costs[existing_costs['cost_id'] == selected_cost].iloc[0]
                        
                        edit_financial_year = st.selectbox(
                            "Financial Year",
                            ['FY 24-25', 'FY 25-26', 'FY 26-27', 'FY 27-28', 'FY 28-29', 
                             'FY 29-30', 'FY 30-31', 'FY 31-32', 'FY 32-33', 'FY 33-34'],
                            index=['FY 24-25', 'FY 25-26', 'FY 26-27', 'FY 27-28', 'FY 28-29', 
                                   'FY 29-30', 'FY 30-31', 'FY 31-32', 'FY 32-33', 'FY 33-34'].index(cost_data['financial_year']) if cost_data['financial_year'] in ['FY 24-25', 'FY 25-26', 'FY 26-27', 'FY 27-28', 'FY 28-29', 'FY 29-30', 'FY 30-31', 'FY 31-32', 'FY 32-33', 'FY 33-34'] else 0,
                            key="edit_financial_year"
                        )
                        
                        edit_project_cost = st.number_input(
                            "Project Cost ($)", 
                            min_value=0, 
                            value=int(cost_data['project_cost']) if pd.notnull(cost_data['project_cost']) else 0, 
                            step=1000, 
                            key="edit_project_cost"
                        )
                        edit_customer_contrib = st.number_input(
                            "Customer Contribution ($)", 
                            min_value=0, 
                            value=int(cost_data['customer_contribution']) if pd.notnull(cost_data['customer_contribution']) else 0, 
                            step=1000, 
                            key="edit_customer_contrib"
                        )
                        
                        edit_summary = st.text_area(
                            "Summary", 
                            value=cost_data['summary_txt'] if pd.notnull(cost_data['summary_txt']) else "", 
                            key="edit_summary"
                        )
                        
                        submitted_edit = st.form_submit_button("Edit Cost Entry")
                        
                        if submitted_edit:
                            c = conn.cursor()
                            c.execute("""UPDATE project_year_cost 
                                        SET financial_year = ?, project_cost = ?, customer_contribution = ?, summary_txt = ?
                                        WHERE cost_id = ?""",
                                     (edit_financial_year, edit_project_cost, edit_customer_contrib, edit_summary, selected_cost))
                            conn.commit()
                            st.success("✅ Cost entry updated successfully!")
                            st.rerun()
            else:
                st.info("No existing cost entries to edit.")
    
    conn.close()

# STATUS TRACKING
elif page == "Status Tracking":
    st.title("📊 Status Tracking")
    
    conn = get_db()
    
    st.markdown("Track project lifecycle and monitor progress through different stages.")
    
    # Status distribution
    query = """
        SELECT 
            ps.status_code,
            ps.description,
            COUNT(DISTINCT psh.project_id) as project_count
        FROM project_status ps
        LEFT JOIN (
            SELECT project_id, project_status_id,
                   ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY status_date DESC) as rn
            FROM project_status_history
        ) psh ON ps.project_status_id = psh.project_status_id AND psh.rn = 1
        GROUP BY ps.status_code, ps.description
    """
    df_status = pd.read_sql_query(query, conn)
    
    if not df_status.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(df_status, values='project_count', names='status_code',
                        title='Projects by Status')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.dataframe(df_status, use_container_width=True, hide_index=True)
    
    # Update project status
    st.subheader("Update Project Status")
    
    projects = pd.read_sql_query("""
        SELECT p.project_id, a.asset_code, p.project_scope
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
    """, conn)
    
    if not projects.empty:
        with st.form("status_update_form"):
            selected_project = st.selectbox(
                "Select Project",
                projects['project_id'].tolist(),
                format_func=lambda x: f"{projects[projects['project_id']==x]['asset_code'].iloc[0]} - {projects[projects['project_id']==x]['project_scope'].iloc[0][:50]}"
            )
            
            statuses = pd.read_sql_query("SELECT * FROM project_status", conn)
            new_status = st.selectbox(
                "New Status",
                statuses['project_status_id'].tolist(),
                format_func=lambda x: f"{statuses[statuses['project_status_id']==x]['status_code'].iloc[0]} - {statuses[statuses['project_status_id']==x]['description'].iloc[0]}"
            )
            
            status_date = st.date_input("Status Date", value=datetime.now(), format="DD/MM/YYYY")
            comments = st.text_area("Comments")
            
            submitted = st.form_submit_button("Update Status")
            
            if submitted:
                c = conn.cursor()
                c.execute("""INSERT INTO project_status_history 
                            (project_id, project_status_id, status_date, comments)
                            VALUES (?, ?, ?, ?)""",
                         (selected_project, new_status, status_date, comments))
                conn.commit()
                st.success("✅ Status updated successfully!")
                st.rerun()
    
    # Recent status changes
    st.subheader("Recent Status Changes")
    query = """
        SELECT 
            a.asset_code,
            p.project_scope,
            ps.status_code,
            psh.status_date,
            psh.comments
        FROM project_status_history psh
        JOIN project p ON psh.project_id = p.project_id
        JOIN asset a ON p.asset_id = a.asset_id
        JOIN project_status ps ON psh.project_status_id = ps.project_status_id
        ORDER BY psh.status_date DESC
        LIMIT 20
    """
    df_recent = pd.read_sql_query(query, conn)
    
    if not df_recent.empty:
        # Format dates in the DataFrame
        df_recent_formatted = format_dataframe_dates(df_recent, ['status_date'])
        st.dataframe(df_recent_formatted, use_container_width=True, hide_index=True)
    
    conn.close()

# PROJECT HISTORY
elif page == "Project History":
    st.title("📜 Project History")
    
    conn = get_db()
    
    st.markdown("View completed projects and their full lifecycle history.")
    
    # Completed projects
    query = """
        SELECT 
            p.project_id,
            a.asset_code,
            ac.class_name,
            p.project_scope,
            SUM(pyc.project_cost) as total_cost,
            MAX(psh.status_date) as completion_date
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
        JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id
        JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id
        LEFT JOIN project_year_cost pyc ON p.project_id = pyc.project_id
        JOIN project_status_history psh ON p.project_id = psh.project_id
        JOIN project_status ps ON psh.project_status_id = ps.project_status_id
        WHERE ps.status_code = 'COMPLETED'
        GROUP BY p.project_id, a.asset_code, ac.class_name, p.project_scope
    """
    df_completed = pd.read_sql_query(query, conn)
    
    if not df_completed.empty:
        st.subheader("Completed Projects")
        # Format dates in the DataFrame
        df_completed_formatted = format_dataframe_dates(df_completed, ['completion_date'])
        st.dataframe(df_completed_formatted, use_container_width=True, hide_index=True)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Completed", len(df_completed))
        col2.metric("Total Value", f"${df_completed['total_cost'].sum():,.0f}")
        
        # Completion trend
        df_completed['completion_year'] = pd.to_datetime(df_completed['completion_date']).dt.year
        completion_trend = df_completed.groupby('completion_year').size().reset_index(name='count')
        
        fig = px.line(completion_trend, x='completion_year', y='count',
                     title='Project Completions by Year', markers=True)
        st.plotly_chart(fig, use_container_width=True)
        
        # Project timeline viewer
        st.subheader("View Project Timeline")
        selected_project = st.selectbox(
            "Select Completed Project",
            df_completed['project_id'].tolist(),
            format_func=lambda x: df_completed[df_completed['project_id']==x]['asset_code'].iloc[0]
        )
        
        if selected_project:
            timeline_query = """
                SELECT 
                    ps.status_code,
                    psh.status_date,
                    psh.comments
                FROM project_status_history psh
                JOIN project_status ps ON psh.project_status_id = ps.project_status_id
                WHERE psh.project_id = ?
                ORDER BY psh.status_date
            """
            df_timeline = pd.read_sql_query(timeline_query, conn, params=(selected_project,))
            
            # Format dates in the timeline DataFrame
            df_timeline_formatted = format_dataframe_dates(df_timeline, ['status_date'])
            st.dataframe(df_timeline_formatted, use_container_width=True, hide_index=True)
    else:
        st.info("No completed projects yet.")
    
    conn.close()

# FAQ
elif page == "FAQ":
    st.title("❓ Frequently Asked Questions")
    
    st.markdown("Find answers to common questions about the CAPEX Planning Dashboard.")
    
    # Create expandable FAQ sections
    with st.expander("🏗️ **General Questions**", expanded=True):
        st.markdown("""
        **Q: What is CAPEX Planning?**
        
        A: CAPEX (Capital Expenditure) Planning is the process of budgeting for major investments in fixed assets like buildings, equipment, and infrastructure. This dashboard helps organizations plan, track, and manage their capital expenditure projects.
        
        **Q: Who can use this system?**
        
        A: This system is designed for project managers, financial planners, asset managers, and executives involved in capital expenditure planning and approval processes.
        
        **Q: How do I get started?**
        
        A: Begin by navigating to the "Add/Edit/Delete Project" section to create your first project. Then use the Priority Scoring and Risk Assessment features to evaluate your projects.
        """)
    
    with st.expander("📊 **Project Management**"):
        st.markdown("""
        **Q: How do I add a new project?**
        
        A: Go to "Add/Edit/Delete Project" → "Add New Project" tab. Fill in all required fields including project details, costs, and timeline information.
        
        **Q: Can I edit existing projects?**
        
        A: Yes! Use the "Edit Existing Project" tab to modify any project details. You can update costs, timelines, priority scores, and other project information.
        
        **Q: How do I delete a project?**
        
        A: Navigate to the "Delete Projects" tab, select the project you want to remove, and confirm the deletion. This action cannot be undone.
        
        **Q: Can I import projects from a spreadsheet?**
        
        A: Yes! Use the "Import from Spreadsheet" tab to upload project data in bulk. The system accepts CSV and Excel files with the proper format.
        """)
    
    with st.expander("🎯 **Priority Scoring**"):
        st.markdown("""
        **Q: How does priority scoring work?**
        
        A: Priority scoring uses weighted criteria to rank projects. Each project is scored on multiple factors (Strategic Alignment, Financial ROI, Risk Level, etc.) and combined using configurable weights.
        
        **Q: Can I change the scoring criteria?**
        
        A: Yes! Administrators can modify scoring criteria and weights in Administration → Reference Data → Criteria Weights.
        
        **Q: What do the priority score ranges mean?**
        
        A: Scores typically range from 0-100:
        - 80-100: High Priority (Critical projects)
        - 60-79: Medium Priority (Important projects)
        - 0-59: Low Priority (Deferred projects)
        """)
    
    with st.expander("⚠️ **Risk Assessment**"):
        st.markdown("""
        **Q: How is project risk calculated?**
        
        A: Risk is assessed using a matrix of Impact vs Probability. Each project is evaluated on potential impact and likelihood of risk occurrence.
        
        **Q: What do the risk colors mean?**
        
        A: Risk levels are color-coded:
        - 🔴 Red: High Risk (requires immediate attention)
        - 🟡 Yellow: Medium Risk (monitor closely)
        - 🟢 Green: Low Risk (acceptable level)
        
        **Q: Can I add risk mitigation strategies?**
        
        A: Yes! When creating or editing risk assessments, you can document mitigation strategies and assign responsible parties.
        """)
    
    with st.expander("💰 **Financial Planning**"):
        st.markdown("""
        **Q: How do I plan for multiple years?**
        
        A: Use the "Multi-Year Planning" section to spread project costs across different years. You can create 1-year, 3-year, and 10-year budget plans.
        
        **Q: Can I see budget forecasts?**
        
        A: Yes! The Multi-Year Planning section shows cost distributions over time with visual charts and detailed breakdowns.
        
        **Q: How are costs calculated?**
        
        A: Total project costs include design costs, implementation costs, and any additional expenses. The system tracks both planned and actual expenditures.
        """)
    
    with st.expander("📈 **Reporting & Analytics**"):
        st.markdown("""
        **Q: What reports are available?**
        
        A: The dashboard provides:
        - Project status summaries
        - Budget vs actual spending analysis
        - Risk assessment matrices
        - Multi-year financial forecasts
        - Asset class distributions
        
        **Q: Can I export data?**
        
        A: Yes! Use Administration → Backup Data to export all data in CSV format or create complete database backups.
        
        **Q: How do I track project progress?**
        
        A: Use the "Status Tracking" section to monitor project phases and the "Project History" section to view completed projects.
        """)
    
    with st.expander("⚙️ **System Administration**"):
        st.markdown("""
        **Q: How do I backup my data?**
        
        A: Go to Administration → Backup Data. You can export individual tables as CSV files or create a complete backup including the database file.
        
        **Q: Can I customize reference data?**
        
        A: Yes! Administrators can modify asset classes, design statuses, criteria weights, and risk factors in the Reference Data section.
        
        **Q: Is my data secure?**
        
        A: The system uses a local SQLite database. For production use, ensure proper access controls and regular backups are implemented.
        
        **Q: What if I encounter errors?**
        
        A: Check that all required fields are completed and that data formats are correct. For persistent issues, contact your system administrator.
        """)
    
    with st.expander("🔧 **Technical Support**"):
        st.markdown("""
        **Q: What browsers are supported?**
        
        A: The dashboard works best with modern browsers including Chrome, Firefox, Safari, and Edge.
        
        **Q: Can I use this on mobile devices?**
        
        A: While accessible on mobile, the dashboard is optimized for desktop and tablet use due to its data-intensive nature.
        
        **Q: How do I report a bug?**
        
        A: Document the steps that led to the issue and contact your system administrator with details about the problem.
        
        **Q: Are there keyboard shortcuts?**
        
        A: Standard web shortcuts apply. Use Tab to navigate between fields and Enter to submit forms.
        """)
    
    st.markdown("---")
    st.info("💡 **Need additional help?** Contact your system administrator or refer to the user documentation for more detailed guidance.")

# ADMINISTRATION
elif page == "Administration":
    if admin_page == "Reference Data":
        st.title("⚙️ Reference Data Management")
        display_software_info()
        
        conn = get_db()
        
        st.markdown("Manage lookup tables and reference data used throughout the application.")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Asset Classes", "Asset Types", "Design Statuses", "Criteria Weights", "Risk Factors"])
        
        with tab1:
            st.subheader("Asset Classes")
            
            # Get current asset classes (this will be refreshed after any operation)
            df_classes_current = pd.read_sql_query("SELECT * FROM asset_class ORDER BY class_name", conn)
            
            # Create columns for different operations
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                st.write("**Add New Asset Class**")
                with st.form("add_asset_class"):
                    new_class = st.text_input("New Asset Class")
                    if st.form_submit_button("Add"):
                        if new_class.strip():
                            c = conn.cursor()
                            try:
                                c.execute("INSERT INTO asset_class (class_name) VALUES (?)", (new_class.strip(),))
                                conn.commit()
                                st.success("Added successfully!")
                                st.rerun()
                            except:
                                st.error("Asset class already exists!")
                        else:
                            st.error("Please enter a valid asset class name!")
            
            with col2:
                st.write("**Edit Asset Class**")
                if not df_classes_current.empty:
                    # Move the selectbox outside the form for better interaction
                    class_options = df_classes_current['class_name'].tolist()
                    selected_class = st.selectbox("Select Asset Class to Edit", 
                                                options=class_options,
                                                key="edit_class_select")
                    
                    if selected_class:
                        st.info(f"Current name: **{selected_class}**")
                        
                        with st.form("edit_asset_class"):
                            new_name = st.text_input("Enter New Name", placeholder="Type the new name here...",
                                                    key="edit_class_name")
                            update_clicked = st.form_submit_button("Update")
                            
                            if update_clicked:
                                if new_name.strip() and selected_class:
                                    if new_name.strip() != selected_class:  # Only update if name actually changed
                                        c = conn.cursor()
                                        try:
                                            # Check if the new name already exists (case-insensitive)
                                            c.execute("SELECT COUNT(*) FROM asset_class WHERE LOWER(class_name) = LOWER(?) AND LOWER(class_name) != LOWER(?)", 
                                                    (new_name.strip(), selected_class))
                                            exists = c.fetchone()[0]
                                            
                                            if exists > 0:
                                                st.error("Asset class name already exists!")
                                            else:
                                                c.execute("UPDATE asset_class SET class_name = ? WHERE class_name = ?", 
                                                        (new_name.strip(), selected_class))
                                                conn.commit()
                                                st.success("Updated successfully!")
                                                # Add a small delay before rerun to ensure message is visible
                                                import time
                                                time.sleep(0.5)
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Error updating asset class: {str(e)}")
                                    else:
                                        st.warning("⚠️ The new name is the same as the current name. No changes needed.")
                                else:
                                    st.error("Please enter a valid new name!")
                    else:
                        st.info("Please select an asset class to edit.")
                else:
                    st.info("No asset classes to edit")
            
            with col3:
                st.write("**Delete Asset Class**")
                if not df_classes_current.empty:
                    with st.form("delete_asset_class"):
                        # Use the current data for dropdown options
                        delete_options = df_classes_current['class_name'].tolist()
                        selected_class_delete = st.selectbox("Select Asset Class to Delete", 
                                                           options=delete_options,
                                                           key="delete_class_select")
                        st.warning("⚠️ This will permanently delete the asset class!")
                        if st.form_submit_button("Delete", type="primary"):
                            if selected_class_delete:
                                c = conn.cursor()
                                try:
                                    # Check if asset class is being used by checking asset_class_id
                                    c.execute("""
                                        SELECT COUNT(*) FROM asset a 
                                        JOIN asset_type_l4 at ON a.asset_type_id = at.asset_type_id 
                                        JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id 
                                        WHERE ac.class_name = ?
                                    """, (selected_class_delete,))
                                    count = c.fetchone()[0]
                                    if count > 0:
                                        st.error(f"Cannot delete! Asset class '{selected_class_delete}' is used by {count} asset(s).")
                                    else:
                                        c.execute("DELETE FROM asset_class WHERE class_name = ?", (selected_class_delete,))
                                        conn.commit()
                                        st.success("Deleted successfully!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting asset class: {str(e)}")
                else:
                    st.info("No asset classes to delete")
            
            st.markdown("---")
            st.write("**Current Asset Classes**")
            # Re-fetch and display the updated table after any operations
            df_classes_updated = pd.read_sql_query("SELECT asset_class_id as ID, class_name as 'Asset Class' FROM asset_class ORDER BY class_name", conn)
            if not df_classes_updated.empty:
                st.dataframe(df_classes_updated, use_container_width=True, hide_index=True)
            else:
                st.info("No asset classes defined yet.")
        
        with tab2:
            st.subheader("Asset Types")
            
            # Get current asset types (this will be refreshed after any operation)
            df_types_current = pd.read_sql_query("""
                SELECT at.asset_type_id, at.type_name, at.asset_class_id, ac.class_name 
                FROM asset_type_l4 at 
                JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id 
                ORDER BY ac.class_name, at.type_name
            """, conn)
            
            # Create columns for different operations
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                st.write("**Add New Asset Type**")
                with st.form("add_asset_type"):
                    # Get asset classes for dropdown
                    asset_classes = pd.read_sql_query("SELECT * FROM asset_class ORDER BY class_name", conn)
                    if not asset_classes.empty:
                        selected_class_id = st.selectbox("Asset Class", 
                                                       options=asset_classes['asset_class_id'].tolist(),
                                                       format_func=lambda x: asset_classes[asset_classes['asset_class_id']==x]['class_name'].iloc[0])
                        new_type = st.text_input("New Asset Type")
                        if st.form_submit_button("Add"):
                            if new_type.strip() and selected_class_id:
                                c = conn.cursor()
                                try:
                                    c.execute("INSERT INTO asset_type_l4 (type_name, asset_class_id) VALUES (?, ?)", 
                                            (new_type.strip(), selected_class_id))
                                    conn.commit()
                                    st.success("Added successfully!")
                                    st.rerun()
                                except:
                                    st.error("Asset type already exists in this class!")
                            else:
                                st.error("Please enter a valid asset type name!")
                    else:
                        st.error("No asset classes available. Please add asset classes first.")
            
            with col2:
                st.write("**Edit Asset Type**")
                if not df_types_current.empty:
                    # Move the selectbox outside the form for better interaction
                    type_options = [(row['asset_type_id'], f"{row['type_name']} ({row['class_name']})") 
                                  for _, row in df_types_current.iterrows()]
                    selected_type = st.selectbox("Select Asset Type to Edit", 
                                               options=[opt[0] for opt in type_options],
                                               format_func=lambda x: next(opt[1] for opt in type_options if opt[0] == x),
                                               key="edit_type_select")
                    
                    if selected_type:
                        current_type = df_types_current[df_types_current['asset_type_id']==selected_type].iloc[0]
                        st.info(f"Current name: **{current_type['type_name']}** (Class: {current_type['class_name']})")
                        
                        with st.form("edit_asset_type"):
                            # Get asset classes for dropdown
                            asset_classes = pd.read_sql_query("SELECT * FROM asset_class ORDER BY class_name", conn)
                            if not asset_classes.empty:
                                current_class_idx = int(asset_classes[asset_classes['asset_class_id']==current_type['asset_class_id']].index[0])
                                new_class_id = st.selectbox("Asset Class",
                                                          options=asset_classes['asset_class_id'].tolist(),
                                                          index=current_class_idx,
                                                          format_func=lambda x: asset_classes[asset_classes['asset_class_id']==x]['class_name'].iloc[0])
                                new_type_name = st.text_input("Enter New Name", placeholder="Type the new name here...",
                                                            key="edit_type_name")
                                update_clicked = st.form_submit_button("Update")
                                
                                if update_clicked:
                                    if new_type_name.strip() and selected_type:
                                        if new_type_name.strip() != current_type['type_name'] or new_class_id != current_type['asset_class_id']:
                                            c = conn.cursor()
                                            try:
                                                # Check if the new name already exists in the selected class
                                                c.execute("SELECT COUNT(*) FROM asset_type_l4 WHERE LOWER(type_name) = LOWER(?) AND asset_class_id = ? AND asset_type_id != ?", 
                                                        (new_type_name.strip(), new_class_id, selected_type))
                                                exists = c.fetchone()[0]
                                                
                                                if exists > 0:
                                                    st.error("Asset type name already exists in this asset class!")
                                                else:
                                                    c.execute("UPDATE asset_type_l4 SET type_name = ?, asset_class_id = ? WHERE asset_type_id = ?", 
                                                            (new_type_name.strip(), new_class_id, selected_type))
                                                    conn.commit()
                                                    st.success("Updated successfully!")
                                                    # Add a small delay before rerun to ensure message is visible
                                                    import time
                                                    time.sleep(0.5)
                                                    st.rerun()
                                            except Exception as e:
                                                st.error(f"Error updating asset type: {str(e)}")
                                        else:
                                            st.warning("⚠️ No changes made.")
                                    else:
                                        st.error("Please enter a valid new name!")
                            else:
                                st.error("No asset classes available. Please add asset classes first.")
                    else:
                        st.info("Please select an asset type to edit.")
                else:
                    st.info("No asset types to edit")
            
            with col3:
                st.write("**Delete Asset Type**")
                if not df_types_current.empty:
                    with st.form("delete_asset_type"):
                        # Use the current data for dropdown options
                        delete_options = [(row['asset_type_id'], f"{row['type_name']} ({row['class_name']})") 
                                        for _, row in df_types_current.iterrows()]
                        selected_type_delete = st.selectbox("Select Asset Type to Delete", 
                                                          options=[opt[0] for opt in delete_options],
                                                          format_func=lambda x: next(opt[1] for opt in delete_options if opt[0] == x),
                                                          key="delete_type_select")
                        st.warning("⚠️ This will permanently delete the asset type!")
                        if st.form_submit_button("Delete", type="primary"):
                            if selected_type_delete:
                                c = conn.cursor()
                                try:
                                    # Check if asset type is being used
                                    c.execute("SELECT COUNT(*) FROM asset WHERE asset_type_id = ?", (selected_type_delete,))
                                    count = c.fetchone()[0]
                                    if count > 0:
                                        type_name = df_types_current[df_types_current['asset_type_id']==selected_type_delete]['type_name'].iloc[0]
                                        st.error(f"Cannot delete! Asset type '{type_name}' is used by {count} asset(s).")
                                    else:
                                        c.execute("DELETE FROM asset_type_l4 WHERE asset_type_id = ?", (selected_type_delete,))
                                        conn.commit()
                                        st.success("Deleted successfully!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting asset type: {str(e)}")
                else:
                    st.info("No asset types to delete")
            
            st.markdown("---")
            st.write("**Current Asset Types**")
            # Re-fetch and display the updated table after any operations
            df_types_updated = pd.read_sql_query("""
                SELECT at.asset_type_id as ID, ac.class_name as 'Asset Class', at.type_name as 'Asset Type'
                FROM asset_type_l4 at 
                JOIN asset_class ac ON at.asset_class_id = ac.asset_class_id 
                ORDER BY ac.class_name, at.type_name
            """, conn)
            if not df_types_updated.empty:
                st.dataframe(df_types_updated, use_container_width=True, hide_index=True)
            else:
                st.info("No asset types defined yet.")
        
        with tab3:
            st.subheader("Design Statuses")
            
            # Get current design statuses (this will be refreshed after any operation)
            df_statuses_current = pd.read_sql_query("SELECT * FROM design_status ORDER BY status_name", conn)
            
            # Create columns for different operations
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                st.write("**Add New Design Status**")
                with st.form("add_design_status"):
                    new_status = st.text_input("New Design Status")
                    if st.form_submit_button("Add"):
                        if new_status.strip():
                            c = conn.cursor()
                            try:
                                c.execute("INSERT INTO design_status (status_name) VALUES (?)", (new_status.strip(),))
                                conn.commit()
                                st.success("Added successfully!")
                                st.rerun()
                            except:
                                st.error("Design status already exists!")
                        else:
                            st.error("Please enter a valid design status name!")
            
            with col2:
                st.write("**Edit Design Status**")
                if not df_statuses_current.empty:
                    # Move the selectbox outside the form for better interaction
                    status_options = df_statuses_current['status_name'].tolist()
                    selected_status = st.selectbox("Select Design Status to Edit", 
                                                 options=status_options,
                                                 key="edit_status_select")
                    
                    if selected_status:
                        st.info(f"Current name: **{selected_status}**")
                        
                        with st.form("edit_design_status"):
                            new_status_name = st.text_input("Enter New Name", placeholder="Type the new name here...",
                                                           key="edit_status_name")
                            update_clicked = st.form_submit_button("Update")
                            
                            if update_clicked:
                                if new_status_name.strip() and selected_status:
                                    if new_status_name.strip() != selected_status:  # Only update if name actually changed
                                        c = conn.cursor()
                                        try:
                                            # Check if the new name already exists (case-insensitive)
                                            c.execute("SELECT COUNT(*) FROM design_status WHERE LOWER(status_name) = LOWER(?) AND LOWER(status_name) != LOWER(?)", 
                                                    (new_status_name.strip(), selected_status))
                                            exists = c.fetchone()[0]
                                            
                                            if exists > 0:
                                                st.error("Design status name already exists!")
                                            else:
                                                c.execute("UPDATE design_status SET status_name = ? WHERE status_name = ?", 
                                                        (new_status_name.strip(), selected_status))
                                                conn.commit()
                                                st.success("Updated successfully!")
                                                # Add a small delay before rerun to ensure message is visible
                                                import time
                                                time.sleep(0.5)
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Error updating design status: {str(e)}")
                                    else:
                                        st.warning("⚠️ The new name is the same as the current name. No changes needed.")
                                else:
                                    st.error("Please enter a valid new name!")
                    else:
                        st.info("Please select a design status to edit.")
                else:
                    st.info("No design statuses to edit")
            
            with col3:
                st.write("**Delete Design Status**")
                if not df_statuses_current.empty:
                    with st.form("delete_design_status"):
                        # Use the current data for dropdown options
                        delete_options = df_statuses_current['status_name'].tolist()
                        selected_status_delete = st.selectbox("Select Design Status to Delete", 
                                                            options=delete_options,
                                                            key="delete_status_select")
                        st.warning("⚠️ This will permanently delete the design status!")
                        if st.form_submit_button("Delete", type="primary"):
                            if selected_status_delete:
                                c = conn.cursor()
                                try:
                                    # Check if design status is being used by projects
                                    c.execute("SELECT COUNT(*) FROM project WHERE design_status = ?", (selected_status_delete,))
                                    count = c.fetchone()[0]
                                    if count > 0:
                                        st.error(f"Cannot delete! Design status '{selected_status_delete}' is used by {count} project(s).")
                                    else:
                                        c.execute("DELETE FROM design_status WHERE status_name = ?", (selected_status_delete,))
                                        conn.commit()
                                        st.success("Deleted successfully!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting design status: {str(e)}")
                else:
                    st.info("No design statuses to delete")
            
            st.markdown("---")
            st.write("**Current Design Statuses**")
            # Re-fetch and display the updated table after any operations
            df_statuses_updated = pd.read_sql_query("SELECT design_status_id as ID, status_name as 'Design Status' FROM design_status ORDER BY status_name", conn)
            if not df_statuses_updated.empty:
                st.dataframe(df_statuses_updated, use_container_width=True, hide_index=True)
            else:
                st.info("No design statuses defined yet.")
        
        with tab4:
            # Helper function to check if definition column exists
            def has_definition_column(conn):
                c = conn.cursor()
                c.execute("PRAGMA table_info(criterion)")
                columns = [column[1] for column in c.fetchall()]
                return 'definition' in columns
            
            # Function to recalculate priority scores and rankings when criteria weights change
            def recalculate_priority_scores(conn):
                """
                Recalculate all project priority scores and rankings based on current criteria weights.
                Returns number of projects updated.
                """
                try:
                    c = conn.cursor()
                    
                    # Get all current criteria and their weights
                    c.execute("SELECT criterion_name, weight_pct FROM criterion")
                    criteria_weights = {row[0]: row[1]/100 for row in c.fetchall()}  # Convert to decimal
                    
                    if not criteria_weights:
                        return 0
                    
                    # Get all projects with their individual scores
                    c.execute("""
                        SELECT ps.asset_id, ps.whs_score, ps.water_savings_score, ps.customer_score, 
                               ps.maintenance_score, ps.financial_score, ps.score_id
                        FROM priority_score ps
                    """)
                    
                    projects_updated = 0
                    
                    for row in c.fetchall():
                        asset_id, whs_score, water_score, customer_score, maintenance_score, financial_score, score_id = row
                        
                        # Calculate weighted total based on criteria weights
                        # Map the score fields to criterion names (this is a simplified mapping)
                        score_mapping = {
                            'WHS': whs_score or 0,
                            'Water Savings': water_score or 0,
                            'Customer Impact': customer_score or 0,
                            'Maintenance': maintenance_score or 0,
                            'Financial': financial_score or 0
                        }
                        
                        # Calculate new weighted total
                        new_total = 0
                        for criterion_name, weight in criteria_weights.items():
                            # Try to match criterion names with score fields
                            if 'WHS' in criterion_name.upper() or 'SAFETY' in criterion_name.upper():
                                new_total += score_mapping['WHS'] * weight
                            elif 'WATER' in criterion_name.upper():
                                new_total += score_mapping['Water Savings'] * weight
                            elif 'CUSTOMER' in criterion_name.upper():
                                new_total += score_mapping['Customer Impact'] * weight
                            elif 'MAINTENANCE' in criterion_name.upper():
                                new_total += score_mapping['Maintenance'] * weight
                            elif 'FINANCIAL' in criterion_name.upper() or 'COST' in criterion_name.upper() or 'ROI' in criterion_name.upper():
                                new_total += score_mapping['Financial'] * weight
                            else:
                                # For new criteria, distribute evenly across all scores
                                avg_score = sum(score_mapping.values()) / len(score_mapping)
                                new_total += avg_score * weight
                        
                        # Update the total priority score
                        c.execute("UPDATE priority_score SET total_priority_score = ? WHERE score_id = ?", 
                                 (new_total, score_id))
                        projects_updated += 1
                    
                    # Recalculate rankings
                    c.execute("""
                        SELECT p.project_id, ps.total_priority_score
                        FROM project p
                        JOIN asset a ON p.asset_id = a.asset_id
                        LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
                        ORDER BY ps.total_priority_score DESC
                    """)
                    
                    projects_with_scores = c.fetchall()
                    for rank, (project_id, score) in enumerate(projects_with_scores, 1):
                        c.execute("UPDATE project SET priority_rank = ? WHERE project_id = ?", 
                                 (rank, project_id))
                    
                    conn.commit()
                    return projects_updated
                    
                except Exception as e:
                    st.error(f"Error recalculating scores: {str(e)}")
                    return 0
            
            # Get current criteria weights (this will be refreshed after any operation)
            try:
                if has_definition_column(conn):
                    df_criteria_current = pd.read_sql_query("SELECT * FROM criterion ORDER BY criterion_name", conn)
                else:
                    # If definition column doesn't exist, create it with empty strings for display
                    df_criteria_raw = pd.read_sql_query("SELECT * FROM criterion ORDER BY criterion_name", conn)
                    df_criteria_raw['definition'] = ''
                    df_criteria_current = df_criteria_raw
            except Exception as e:
                st.error(f"Error loading criteria data: {str(e)}")
                df_criteria_current = pd.DataFrame()
            
            # Display summary information first - only show suggestions if no data
            if df_criteria_current.empty:
                st.info("No criteria weights defined yet.")
                st.info("💡 **Suggested criteria to get started:**")
                st.write("• Cost Effectiveness (25%) - Evaluate financial return and cost-benefit ratio")
                st.write("• Strategic Alignment (20%) - Alignment with organizational goals and strategy")
                st.write("• Risk Assessment (15%) - Technical, operational, and financial risk evaluation")
                st.write("• Implementation Feasibility (15%) - Resource availability and execution capability")
                st.write("• Business Impact (25%) - Revenue potential and competitive advantage")
            
            # Add/Edit/Delete functions moved above the current criteria display
            st.write("### Manage Criteria")
            
            # Create columns for different operations
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                st.write("**Add New Criterion**")
                with st.form("add_criterion"):
                    new_criterion_name = st.text_input("Criterion Name")
                    new_criterion_definition = st.text_area("Definition/Description", height=100,
                                                           help="Provide a clear definition of what this criterion measures")
                    new_weight_pct = st.number_input("Weight Percentage", min_value=0.0, max_value=100.0, 
                                                    value=0.0, step=0.1, format="%.1f")
                    if st.form_submit_button("Add"):
                        if new_criterion_name.strip():
                            c = conn.cursor()
                            try:
                                # Check if definition column exists
                                c.execute("PRAGMA table_info(criterion)")
                                columns = [column[1] for column in c.fetchall()]
                                
                                if 'definition' in columns:
                                    c.execute("INSERT INTO criterion (criterion_name, definition, weight_pct) VALUES (?, ?, ?)", 
                                            (new_criterion_name.strip(), new_criterion_definition.strip(), new_weight_pct))
                                else:
                                    c.execute("INSERT INTO criterion (criterion_name, weight_pct) VALUES (?, ?)", 
                                            (new_criterion_name.strip(), new_weight_pct))
                                conn.commit()
                                st.success("Added successfully!")
                                
                                # Recalculate priority scores after adding criterion
                                updated_count = recalculate_priority_scores(conn)
                                if updated_count > 0:
                                    st.info(f"✅ Recalculated priority scores for {updated_count} projects.")
                                
                                st.rerun()
                            except:
                                st.error("Criterion already exists!")
                        else:
                            st.error("Please enter a criterion name!")
            
            with col2:
                st.write("**Edit Criterion**")
                if not df_criteria_current.empty:
                    # Move the selectbox outside the form for better interaction
                    criterion_options = df_criteria_current['criterion_name'].tolist()
                    selected_criterion = st.selectbox("Select Criterion to Edit", 
                                                     options=criterion_options,
                                                     key="edit_criterion_select")
                    
                    if selected_criterion:
                        current_criterion = df_criteria_current[df_criteria_current['criterion_name']==selected_criterion].iloc[0]
                        st.info(f"Current: **{current_criterion['criterion_name']}** ({current_criterion['weight_pct']}%)")
                        
                        with st.form("edit_criterion"):
                            new_criterion_name = st.text_input("Enter New Name (If not changing leave the input field as is)", placeholder="Type the new name here...",
                                                             key="edit_criterion_name")
                            
                            # Check if definition column exists
                            c = conn.cursor()
                            c.execute("PRAGMA table_info(criterion)")
                            columns = [column[1] for column in c.fetchall()]
                            
                            new_definition = ""
                            if 'definition' in columns:
                                new_definition = st.text_area("Definition/Description", 
                                                             value=current_criterion.get('definition', ''),
                                                             height=100,
                                                             key="edit_criterion_definition")
                            
                            new_weight = st.number_input("Weight Percentage", min_value=0.0, max_value=100.0,
                                                       value=float(current_criterion['weight_pct']),
                                                       step=0.1, format="%.1f",
                                                       key="edit_criterion_weight")
                            update_clicked = st.form_submit_button("Update")
                            
                            if update_clicked:
                                if selected_criterion:
                                    # Use current name if new name is empty
                                    final_criterion_name = new_criterion_name.strip() if new_criterion_name.strip() else current_criterion['criterion_name']
                                    
                                    changes_made = (final_criterion_name != current_criterion['criterion_name'] or
                                                  new_weight != current_criterion['weight_pct'])
                                    
                                    if 'definition' in columns:
                                        changes_made = changes_made or (new_definition.strip() != current_criterion.get('definition', ''))
                                    
                                    if changes_made:
                                        c = conn.cursor()
                                        try:
                                            # Check if the new name already exists (excluding current record)
                                            c.execute("SELECT COUNT(*) FROM criterion WHERE LOWER(criterion_name) = LOWER(?) AND LOWER(criterion_name) != LOWER(?)", 
                                                    (final_criterion_name, selected_criterion))
                                            exists = c.fetchone()[0]
                                            
                                            if exists > 0:
                                                st.error("Criterion name already exists!")
                                            else:
                                                if 'definition' in columns:
                                                    c.execute("UPDATE criterion SET criterion_name = ?, definition = ?, weight_pct = ? WHERE criterion_name = ?", 
                                                            (final_criterion_name, new_definition.strip(), new_weight, selected_criterion))
                                                else:
                                                    c.execute("UPDATE criterion SET criterion_name = ?, weight_pct = ? WHERE criterion_name = ?", 
                                                            (final_criterion_name, new_weight, selected_criterion))
                                                conn.commit()
                                                st.success("Updated successfully!")
                                                
                                                # Recalculate priority scores after updating criterion
                                                updated_count = recalculate_priority_scores(conn)
                                                if updated_count > 0:
                                                    st.info(f"✅ Recalculated priority scores for {updated_count} projects.")
                                                
                                                # Add a small delay before rerun to ensure message is visible
                                                import time
                                                time.sleep(0.5)
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Error updating criterion: {str(e)}")
                                    else:
                                        st.warning("⚠️ No changes made.")
                                else:
                                    st.error("Please select a criterion to edit!")
                    else:
                        st.info("Please select a criterion to edit.")
                else:
                    st.info("No criteria to edit")
            
            with col3:
                st.write("**Delete Criterion**")
                if not df_criteria_current.empty:
                    with st.form("delete_criterion"):
                        # Use the current data for dropdown options
                        delete_options = df_criteria_current['criterion_name'].tolist()
                        selected_criterion_delete = st.selectbox("Select Criterion to Delete", 
                                                                options=delete_options,
                                                                key="delete_criterion_select")
                        st.warning("⚠️ This will permanently delete the criterion!")
                        if st.form_submit_button("Delete", type="primary"):
                            if selected_criterion_delete:
                                c = conn.cursor()
                                try:
                                    # Check if criterion is being used in scoring (assuming there might be a scoring table)
                                    # For now, we'll allow deletion but add a check for future use
                                    c.execute("DELETE FROM criterion WHERE criterion_name = ?", (selected_criterion_delete,))
                                    conn.commit()
                                    st.success("Deleted successfully!")
                                    
                                    # Recalculate priority scores after deleting criterion
                                    updated_count = recalculate_priority_scores(conn)
                                    if updated_count > 0:
                                        st.info(f"✅ Recalculated priority scores for {updated_count} projects.")
                                    
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting criterion: {str(e)}")
                else:
                    st.info("No criteria to delete")
            
            st.divider()
            
            # Current Criteria Display Section
            st.write("### Current Priority Criteria")
            
            # Re-fetch and display the updated table after any operations
            try:
                # Check if definition column exists in criterion table
                c = conn.cursor()
                c.execute("PRAGMA table_info(criterion)")
                columns = [column[1] for column in c.fetchall()]
                has_definition = 'definition' in columns
                
                if has_definition:
                    df_criteria_updated = pd.read_sql_query("""
                        SELECT criterion_id as ID, criterion_name as 'Criterion Name', 
                               definition as 'Definition', weight_pct as 'Weight %'
                        FROM criterion ORDER BY criterion_name
                    """, conn)
                else:
                    df_criteria_updated = pd.read_sql_query("""
                        SELECT criterion_id as ID, criterion_name as 'Criterion Name', 
                               weight_pct as 'Weight %'
                        FROM criterion ORDER BY criterion_name
                    """, conn)
                    # Add empty definition column for consistent display and move it after criterion name
                    df_criteria_updated.insert(2, 'Definition', 'No definition available')
                
                if not df_criteria_updated.empty:
                    # Display the main criteria table with descriptions
                    st.dataframe(df_criteria_updated, width='stretch', hide_index=True)
                    
                    # Show weight validation
                    total_weight = df_criteria_updated['Weight %'].sum()
                    col_metric1, col_metric2, col_metric3, col_metric4 = st.columns([1, 3, 2, 2])
                    
                    with col_metric1:
                        st.metric("Total Weight", f"{total_weight:.1f}%")
                    
                    with col_metric4:
                        # Weight % column message
                        if total_weight == 100.0:
                            st.success("✅ Perfect! Weights sum to 100%")
                        elif total_weight < 100.0:
                            st.warning(f"⚠️ Need {100.0 - total_weight:.1f}% more")
                        else:
                            st.error(f"❌ Exceeds by {total_weight - 100.0:.1f}%")
                    
                    # Display detailed criteria with expandable descriptions
                    st.write("**Detailed Criteria Information:**")
                    for _, row in df_criteria_updated.iterrows():
                        with st.expander(f"{row['Criterion Name']} ({row['Weight %']}%)"):
                            if has_definition and row.get('Definition', '') and row['Definition'] != 'No definition available':
                                st.write(f"**Definition:** {row['Definition']}")
                            else:
                                st.write("*No definition provided for this criterion yet.*")
                                if has_definition:
                                    st.info("💡 Use the Edit function above to add a definition for this criterion.")
                else:
                    st.info("No criteria defined yet. Use the management tools above to add criteria.")
                
                # Priority Score Recalculation Status Area
                st.divider()
                st.write("### 🔄 Priority Score Recalculation Status")
                
                # Check if there are any priority scores that might need recalculation
                try:
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM priority_score WHERE total_priority_score IS NOT NULL")
                    score_count = c.fetchone()[0]
                    
                    c.execute("SELECT COUNT(*) FROM project")
                    project_count = c.fetchone()[0]
                    
                    if score_count > 0:
                        st.success(f"✅ Priority scores are up to date for {score_count} scored assets (from {project_count} total projects).")
                        st.info("💡 When you modify criteria weights above, project priorities will be automatically recalculated.")
                    else:
                        if project_count > 0:
                            st.info(f"ℹ️ Found {project_count} projects but no priority scores yet. Score projects to see recalculation status.")
                        else:
                            st.info("ℹ️ No projects found. Add projects and score them to see recalculation status.")
                except Exception as recalc_error:
                    st.warning(f"Could not check recalculation status: {str(recalc_error)}")
                    
            except Exception as e:
                st.error(f"Error displaying criteria: {str(e)}")
                st.info("Please check if the database is properly configured.")
                st.markdown("""
                **Suggested Criteria Examples:**
                - **Strategic Alignment** (25%): How well the project aligns with organizational strategy
                - **Financial ROI** (30%): Expected return on investment and financial benefits
                - **Risk Level** (20%): Overall project risk assessment (lower risk = higher score)
                - **Regulatory Compliance** (15%): Compliance requirements and regulatory impact
                - **Operational Impact** (10%): Effect on daily operations and business continuity
                """)
        
        with tab5:
            st.subheader("Risk Factors")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Consequences**")
                df_consequences = pd.read_sql_query("SELECT * FROM consequence", conn)
                st.dataframe(df_consequences, use_container_width=True, hide_index=True)
            
            with col2:
                st.write("**Likelihoods**")
                df_likelihoods = pd.read_sql_query("SELECT * FROM likelihood", conn)
                st.dataframe(df_likelihoods, use_container_width=True, hide_index=True)
        
        conn.close()
    
    elif admin_page == "Backup Data":
        st.title("💾 Data Backup")
        
        st.markdown("""
        Create a complete backup of all your CAPEX planning data including:
        - Projects and asset information
        - Priority scores and rankings
        - Risk assessments
        - Multi-year cost data
        - Status tracking history
        - Reference data (asset classes, statuses, etc.)
        """)
        
        # Backup form
        with st.form("backup_form"):
            st.subheader("Backup Configuration")
            
            # Default backup directory
            default_backup_dir = str(Path.home() / "Downloads" / "CAPEX_Backup")
            
            backup_dir = st.text_input(
                "Backup Directory Path", 
                value=default_backup_dir,
                help="Enter the full path where you want to save the backup files"
            )
            
            include_database = st.checkbox("Include Database File", value=True, help="Include the complete SQLite database file")
            include_csv_exports = st.checkbox("Include CSV Exports", value=True, help="Export all data as CSV files for easy viewing")
            create_zip = st.checkbox("Create ZIP Archive", value=True, help="Package all backup files into a single ZIP file")
            
            submitted = st.form_submit_button("🚀 Create Backup")
            
            if submitted:
                if not backup_dir.strip():
                    st.error("Please enter a backup directory path")
                else:
                    try:
                        # Create backup directory if it doesn't exist
                        backup_path = Path(backup_dir)
                        backup_path.mkdir(parents=True, exist_ok=True)
                        
                        # Create timestamped backup folder
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        backup_folder = backup_path / f"CAPEX_Backup_{timestamp}"
                        backup_folder.mkdir(exist_ok=True)
                        
                        conn = get_db()
                        backup_files = []
                        
                        # Export CSV files if requested
                        if include_csv_exports:
                            st.info("📊 Exporting data to CSV files...")
                            
                            # Export all tables
                            tables_to_export = [
                                ("projects", "SELECT p.project_id, a.asset_code, a.description as asset_description, p.project_scope, p.priority_rank FROM project p JOIN asset a ON p.asset_id = a.asset_id"),
                                ("assets", "SELECT * FROM asset"),
                                ("priority_scores", "SELECT ps.*, a.asset_code FROM priority_score ps JOIN asset a ON ps.asset_id = a.asset_id"),
                                ("project_costs", "SELECT pyc.*, a.asset_code FROM project_year_cost pyc JOIN project p ON pyc.project_id = p.project_id JOIN asset a ON p.asset_id = a.asset_id"),
                                ("status_history", "SELECT psh.*, a.asset_code, ps.status_code FROM project_status_history psh JOIN project p ON psh.project_id = p.project_id JOIN asset a ON p.asset_id = a.asset_id JOIN project_status ps ON psh.project_status_id = ps.project_status_id"),
                                ("risk_assessments", "SELECT ra.*, a.asset_code FROM risk_assessment ra JOIN project p ON ra.project_id = p.project_id JOIN asset a ON p.asset_id = a.asset_id"),
                                ("asset_classes", "SELECT * FROM asset_class"),
                                ("design_statuses", "SELECT * FROM design_status"),
                                ("project_statuses", "SELECT * FROM project_status"),
                                ("criteria", "SELECT * FROM criterion"),
                                ("consequences", "SELECT * FROM consequence"),
                                ("likelihoods", "SELECT * FROM likelihood")
                            ]
                            
                            for table_name, query in tables_to_export:
                                try:
                                    df = pd.read_sql_query(query, conn)
                                    if not df.empty:
                                        # Format dates in the dataframe
                                        date_columns = [col for col in df.columns if 'date' in col.lower()]
                                        if date_columns:
                                            df = format_dataframe_dates(df, date_columns)
                                        
                                        csv_file = backup_folder / f"{table_name}.csv"
                                        df.to_csv(csv_file, index=False)
                                        backup_files.append(csv_file)
                                        st.success(f"✅ Exported {table_name}: {len(df)} records")
                                    else:
                                        st.info(f"ℹ️ {table_name}: No data to export")
                                except Exception as e:
                                    st.warning(f"⚠️ Could not export {table_name}: {str(e)}")
                        
                        # Copy database file if requested
                        if include_database:
                            st.info("🗄️ Copying database file...")
                            try:
                                db_source = "capex_planning.db"
                                db_backup = backup_folder / f"capex_planning_backup_{timestamp}.db"
                                if os.path.exists(db_source):
                                    shutil.copy2(db_source, db_backup)
                                    backup_files.append(db_backup)
                                    st.success("✅ Database file copied successfully")
                                else:
                                    st.warning("⚠️ Database file not found at expected location")
                            except Exception as e:
                                st.error(f"❌ Error copying database: {str(e)}")
                        
                        # Create backup info file
                        info_file = backup_folder / "backup_info.txt"
                        with open(info_file, 'w') as f:
                            f.write(f"CAPEX Planning System Backup\n")
                            f.write(f"Created: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                            f.write(f"Backup Directory: {backup_folder}\n")
                            f.write(f"Database Included: {include_database}\n")
                            f.write(f"CSV Exports Included: {include_csv_exports}\n")
                            f.write(f"Total Files: {len(backup_files) + 1}\n\n")
                            f.write("Files in this backup:\n")
                            f.write("- backup_info.txt (this file)\n")
                            for file in backup_files:
                                f.write(f"- {file.name}\n")
                        
                        backup_files.append(info_file)
                        
                        # Create ZIP archive if requested
                        if create_zip:
                            st.info("📦 Creating ZIP archive...")
                            try:
                                zip_file = backup_path / f"CAPEX_Backup_{timestamp}.zip"
                                with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                                    for file in backup_files:
                                        zipf.write(file, file.name)
                                
                                # Remove individual files after zipping
                                for file in backup_files:
                                    file.unlink()
                                backup_folder.rmdir()
                                
                                st.success(f"🎉 Backup completed successfully!")
                                st.success(f"📁 ZIP file created: `{zip_file}`")
                                st.info(f"💾 Backup size: {zip_file.stat().st_size / 1024:.1f} KB")
                                
                            except Exception as e:
                                st.error(f"❌ Error creating ZIP file: {str(e)}")
                                st.info(f"📁 Individual files available at: `{backup_folder}`")
                        else:
                            st.success(f"🎉 Backup completed successfully!")
                            st.success(f"📁 Files saved to: `{backup_folder}`")
                            st.info(f"📊 Total files: {len(backup_files)}")
                        
                        conn.close()
                        
                    except Exception as e:
                        st.error(f"❌ Backup failed: {str(e)}")
                        st.info("Please check the directory path and permissions, then try again.")
        
        # Display current database statistics
        st.subheader("📈 Current Data Summary")
        try:
            conn = get_db()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                project_count = pd.read_sql_query("SELECT COUNT(*) as count FROM project", conn).iloc[0]['count']
                st.metric("Total Projects", project_count)
                
                asset_count = pd.read_sql_query("SELECT COUNT(*) as count FROM asset", conn).iloc[0]['count']
                st.metric("Total Assets", asset_count)
            
            with col2:
                cost_entries = pd.read_sql_query("SELECT COUNT(*) as count FROM project_year_cost", conn).iloc[0]['count']
                st.metric("Cost Entries", cost_entries)
                
                status_entries = pd.read_sql_query("SELECT COUNT(*) as count FROM project_status_history", conn).iloc[0]['count']
                st.metric("Status History Records", status_entries)
            
            with col3:
                risk_assessments = pd.read_sql_query("SELECT COUNT(*) as count FROM risk_assessment", conn).iloc[0]['count']
                st.metric("Risk Assessments", risk_assessments)
                
                priority_scores = pd.read_sql_query("SELECT COUNT(*) as count FROM priority_score", conn).iloc[0]['count']
                st.metric("Priority Scores", priority_scores)
            
            conn.close()
            
        except Exception as e:
            st.error(f"Error loading data summary: {str(e)}")
    
    else:
        st.title("🔧 Administration")
        st.markdown("""
        Welcome to the Administration section. Please select an option from the sidebar to manage system settings and reference data.
        
        **Available Options:**
        - **Reference Data**: Manage lookup tables, asset classes, design statuses, and risk factors
        - **Backup Data**: Create complete backups of all CAPEX planning data
        """)
        st.info("👈 Select an administration option from the sidebar to get started.")

st.sidebar.markdown("---")
st.sidebar.info("""
**ASAP CAPEX Planning System**

Version 1.0

Manage and prioritize capital expenditure projects 
with integrated risk assessment and multi-year planning.
""")