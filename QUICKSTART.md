# Quick Start Guide - ASAP CAPEX Planning

## 🚀 Getting Started in 5 Minutes

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/[your-username]/ASAP-Capex-Planning.git
cd ASAP-Capex-Planning

# Run setup (Windows)
setup.bat

# OR run setup (Linux/Mac)
./setup.sh

# OR manual setup
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Copy the template and edit with your details
cp config.ini.template config.ini
# Edit config.ini with your organization name
```

### 3. Run the Application
```bash
streamlit run capex_app.py
```

### 4. Access the Dashboard
Open your browser to: http://localhost:8501

## 📋 First Steps

### Adding Your First Project
1. Go to **Add/Edit/Delete Project** → **Add New Project**
2. Fill in the required fields:
   - Asset ID (e.g., CD-2-001)
   - Asset Class
   - Project Scope
3. Set priority scores for each criterion
4. Click **Add Project**

### Importing Multiple Projects
1. Go to **Add/Edit/Delete Project** → **Import from Spreadsheet**
2. Download the template file
3. Fill in your project data
4. Upload the completed file

### Setting Up Priority Criteria
1. Go to **Administration** → **Reference Data** → **Criteria Weights**
2. Add/Edit criteria and their weights
3. Ensure weights sum to 100%

### Managing Reference Data
1. **Asset Classes**: Add your organization's asset categories
2. **Asset Types**: Define specific asset types under each class
3. **Design Statuses**: Configure project lifecycle stages

## 🎯 Key Features Overview

### Dashboard
- View all project KPIs at a glance
- Budget allocation charts
- Project distribution by asset class

### Priority Scoring
- Weighted scoring across 5 criteria
- Automatic ranking calculation
- Configurable weights in Administration

### Risk Assessment
- 5x6 risk matrix
- Color-coded risk levels
- Risk mitigation tracking

### Multi-Year Planning
- 1, 3, and 10-year budget forecasts
- Cost distribution visualization
- Financial year planning

## 🔧 Common Tasks

### Backup Your Data
1. Go to **Administration** → **Backup Data**
2. Choose backup location
3. Select CSV exports and/or database backup
4. Click **Create Backup**

### Update Project Priorities
Projects are automatically re-ranked when you:
- Modify criteria weights
- Update project scores
- Add/remove criteria

### Export Data
- Most tables have **Export to CSV** buttons
- Use Administration → Backup for complete exports

## 📞 Support

- Check the **FAQ** section in the application
- Review project documentation
- Contact your system administrator

---
*Produced by Odysseus-imc Pty Ltd*