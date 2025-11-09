import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

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

# Initialize database
init_database()

# Sidebar navigation
st.sidebar.title("🏗️ CAPEX Planning")
page = st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Projects", "Add/Edit Project", "Priority Scoring", 
     "Risk Assessment", "Multi-Year Planning", "Status Tracking", 
     "Project History", "Reference Data"]
)

# DASHBOARD
if page == "Dashboard":
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

# PROJECTS LIST
elif page == "Projects":
    st.title("📋 Projects")
    
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
        if selected_class != "All":
            df_projects = df_projects[df_projects['asset_class'] == selected_class]
        if selected_status != "All":
            df_projects = df_projects[df_projects['design_status'] == selected_status]
        if search:
            df_projects = df_projects[
                df_projects['asset_code'].str.contains(search, case=False, na=False) |
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

# ADD/Edit PROJECT
elif page == "Add/Edit Project":
    st.title("➕ Add/Edit Project")
    
    conn = get_db()
    
    tab1, tab2, tab3 = st.tabs(["Add New Project", "Edit Existing Project", "Import from Spreadsheet"])
    
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
                    except Exception as e:
                        st.error(f"Error creating project: {str(e)}")
    
    with tab2:
        st.subheader("Edit Existing Project")
        
        # Select project to edit
        projects = pd.read_sql_query("""
            SELECT p.project_id, a.asset_code, p.project_scope
            FROM project p
            JOIN asset a ON p.asset_id = a.asset_id
        """, conn)
        
        if not projects.empty:
            selected_project = st.selectbox(
                "Select Project",
                projects['project_id'].tolist(),
                format_func=lambda x: f"{projects[projects['project_id']==x]['asset_code'].iloc[0]} - {projects[projects['project_id']==x]['project_scope'].iloc[0][:50]}"
            )
            
            if selected_project:
                # Load project details
                project_data = pd.read_sql_query("""
                    SELECT p.*, a.asset_code, a.description as asset_desc,
                           ps.whs_score, ps.water_savings_score, ps.customer_score,
                           ps.maintenance_score, ps.financial_score, ps.total_priority_score
                    FROM project p
                    JOIN asset a ON p.asset_id = a.asset_id
                    LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
                    WHERE p.project_id = ?
                """, conn, params=(selected_project,)).iloc[0]
                
                with st.form("edit_project_form"):
                    new_scope = st.text_area("Project Scope", value=project_data['project_scope'])
                    
                    design_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
                    new_design_status = st.selectbox(
                        "Design Status",
                        design_statuses['design_status_id'].tolist(),
                        index=int(project_data['design_status_id'] - 1) if project_data['design_status_id'] else 0,
                        format_func=lambda x: design_statuses[design_statuses['design_status_id']==x]['status_name'].iloc[0]
                    )
                    
                    update_submitted = st.form_submit_button("Update Project")
                    
                    if update_submitted:
                        c = conn.cursor()
                        c.execute("""UPDATE project 
                                    SET project_scope=?, design_status_id=?, updated_at=CURRENT_TIMESTAMP
                                    WHERE project_id=?""",
                                 (new_scope, new_design_status, selected_project))
                        conn.commit()
                        st.success("✅ Project updated successfully!")
        else:
            st.info("No projects available to edit.")
    
    with tab3:
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
elif page == "Risk Assessment":
        
        with st.form("new_project_form"):
            col1, col2 = st.columns(2)
            
            # Asset details
            asset_code = col1.text_input("Asset Code*", help="e.g., CD-2-892")
            
            asset_classes = pd.read_sql_query("SELECT * FROM asset_class", conn)
            asset_class_id = col1.selectbox(
                "Asset Class*",
                asset_classes['asset_class_id'].tolist(),
                format_func=lambda x: asset_classes[asset_classes['asset_class_id']==x]['class_name'].iloc[0]
            )
            
            comments = col2.text_input("Asset Type", help="e.g., Bridges (Roads, Access, Railway)")
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
                    except Exception as e:
                        st.error(f"Error creating project: {str(e)}")
    
    with tab2:
        st.subheader("Edit Existing Project")
        
        # Select project to edit
        projects = pd.read_sql_query("""
            SELECT p.project_id, a.asset_code, p.project_scope
            FROM project p
            JOIN asset a ON p.asset_id = a.asset_id
        """, conn)
        
        if not projects.empty:
            selected_project = st.selectbox(
                "Select Project",
                projects['project_id'].tolist(),
                format_func=lambda x: f"{projects[projects['project_id']==x]['asset_code'].iloc[0]} - {projects[projects['project_id']==x]['project_scope'].iloc[0][:50]}"
            )
            
            if selected_project:
                # Load project details
                project_data = pd.read_sql_query("""
                    SELECT p.*, a.asset_code, a.description as asset_desc,
                           ps.whs_score, ps.water_savings_score, ps.customer_score,
                           ps.maintenance_score, ps.financial_score, ps.total_priority_score
                    FROM project p
                    JOIN asset a ON p.asset_id = a.asset_id
                    LEFT JOIN priority_score ps ON a.asset_id = ps.asset_id
                    WHERE p.project_id = ?
                """, conn, params=(selected_project,)).iloc[0]
                
                with st.form("edit_project_form"):
                    new_scope = st.text_area("Project Scope", value=project_data['project_scope'])
                    
                    design_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
                    new_design_status = st.selectbox(
                        "Design Status",
                        design_statuses['design_status_id'].tolist(),
                        index=int(project_data['design_status_id'] - 1) if project_data['design_status_id'] else 0,
                        format_func=lambda x: design_statuses[design_statuses['design_status_id']==x]['status_name'].iloc[0]
                    )
                    
                    update_submitted = st.form_submit_button("Update Project")
                    
                    if update_submitted:
                        c = conn.cursor()
                        c.execute("""UPDATE project 
                                    SET project_scope=?, design_status_id=?, updated_at=CURRENT_TIMESTAMP
                                    WHERE project_id=?""",
                                 (new_scope, new_design_status, selected_project))
                        conn.commit()
                        st.success("✅ Project updated successfully!")
        else:
            st.info("No projects available to edit.")
    
    with tab3:
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

# PRIORITY SCORING
elif page == "Priority Scoring":
    st.title("🎯 Priority Scoring")
    
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
                    x='asset_code', 
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
    st.dataframe(df_matrix, use_container_width=True, hide_index=True)
    
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
            
            if risk_score <= 3:
                risk_rating = "Low"
            elif risk_score <= 6:
                risk_rating = "Moderate"
            elif risk_score <= 9:
                risk_rating = "High"
            else:
                risk_rating = "Extreme"
            
            st.info(f"**Calculated Risk Rating: {risk_rating}**")
            
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
        st.dataframe(df_risk, use_container_width=True, hide_index=True)
    
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No 3-year program data available")
    
    with tab3:
        st.subheader("10 Year Program")
        
        query = """
            SELECT 
                pyc.financial_year,
                SUM(pyc.project_cost) as total_cost,
                COUNT(DISTINCT p.project_id) as project_count
            FROM project_year_cost pyc
            JOIN project p ON pyc.project_id = p.project_id
            GROUP BY pyc.financial_year
            ORDER BY pyc.financial_year
        """
        df_10yr = pd.read_sql_query(query, conn)
        
        if not df_10yr.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig1 = px.line(df_10yr, x='financial_year', y='total_cost',
                              title='10-Year Budget Forecast', markers=True)
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                fig2 = px.bar(df_10yr, x='financial_year', y='project_count',
                             title='Project Count by Year')
                st.plotly_chart(fig2, use_container_width=True)
            
            st.dataframe(df_10yr, use_container_width=True, hide_index=True)
        else:
            st.info("No 10-year program data available")
    
    # Add costs to projects
    st.subheader("Add Project Costs")
    
    projects = pd.read_sql_query("""
        SELECT p.project_id, a.asset_code, p.project_scope
        FROM project p
        JOIN asset a ON p.asset_id = a.asset_id
    """, conn)
    
    if not projects.empty:
        with st.form("add_costs_form"):
            col1, col2 = st.columns(2)
            
            selected_project = col1.selectbox(
                "Select Project",
                projects['project_id'].tolist(),
                format_func=lambda x: f"{projects[projects['project_id']==x]['asset_code'].iloc[0]}"
            )
            
            financial_year = col2.selectbox(
                "Financial Year",
                ['FY 24-25', 'FY 25-26', 'FY 26-27', 'FY 27-28', 'FY 28-29', 
                 'FY 29-30', 'FY 30-31', 'FY 31-32', 'FY 32-33', 'FY 33-34']
            )
            
            col3, col4 = st.columns(2)
            project_cost = col3.number_input("Project Cost ($)", min_value=0, value=0, step=1000)
            customer_contrib = col4.number_input("Customer Contribution ($)", min_value=0, value=0, step=1000)
            
            summary = st.text_area("Summary")
            
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
            
            status_date = st.date_input("Status Date", value=datetime.now())
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
        st.dataframe(df_recent, use_container_width=True, hide_index=True)
    
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
        st.dataframe(df_completed, use_container_width=True, hide_index=True)
        
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
            
            st.dataframe(df_timeline, use_container_width=True, hide_index=True)
    else:
        st.info("No completed projects yet.")
    
    conn.close()

# REFERENCE DATA
elif page == "Reference Data":
    st.title("⚙️ Reference Data Management")
    
    conn = get_db()
    
    st.markdown("Manage lookup tables and reference data used throughout the application.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Asset Classes", "Design Statuses", "Criteria Weights", "Risk Factors"])
    
    with tab1:
        st.subheader("Asset Classes")
        df_classes = pd.read_sql_query("SELECT * FROM asset_class", conn)
        st.dataframe(df_classes, use_container_width=True, hide_index=True)
        
        with st.form("add_asset_class"):
            new_class = st.text_input("New Asset Class")
            if st.form_submit_button("Add"):
                if new_class:
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO asset_class (class_name) VALUES (?)", (new_class,))
                        conn.commit()
                        st.success("Added successfully!")
                        st.rerun()
                    except:
                        st.error("Asset class already exists!")
    
    with tab2:
        st.subheader("Design Statuses")
        df_statuses = pd.read_sql_query("SELECT * FROM design_status", conn)
        st.dataframe(df_statuses, use_container_width=True, hide_index=True)
        
        with st.form("add_design_status"):
            new_status = st.text_input("New Design Status")
            if st.form_submit_button("Add"):
                if new_status:
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO design_status (status_name) VALUES (?)", (new_status,))
                        conn.commit()
                        st.success("Added successfully!")
                        st.rerun()
                    except:
                        st.error("Status already exists!")
    
    with tab3:
        st.subheader("Priority Criteria Weights")
        df_criteria = pd.read_sql_query("SELECT * FROM criterion", conn)
        st.dataframe(df_criteria, use_container_width=True, hide_index=True)
        
        st.info("Total weights should sum to 100%")
        total_weight = df_criteria['weight_pct'].sum()
        st.metric("Total Weight", f"{total_weight}%")
    
    with tab4:
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

st.sidebar.markdown("---")
st.sidebar.info("""
**ASAP CAPEX Planning System**

Version 1.0

Manage and prioritize capital expenditure projects 
with integrated risk assessment and multi-year planning.
""")