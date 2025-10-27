# ASAP CAPEX Planning System

A comprehensive Capital Expenditure (CAPEX) planning and management dashboard built with Streamlit.

## Features

### 📊 **Dashboard & Analytics**
- Real-time project overview with KPIs
- Budget allocation tracking by financial year
- Project distribution by asset class
- Visual charts and graphs

### 📋 **Project Management**
- Add, edit, and delete projects
- Import projects from Excel/CSV spreadsheets
- Project filtering and search capabilities
- Multi-year cost planning (1, 3, and 10-year plans)

### 🎯 **Priority Scoring System**
- Weighted criteria scoring (WHS, Water Savings, Customer Impact, etc.)
- Automatic priority ranking
- Configurable scoring weights
- Real-time score recalculation

### ⚠️ **Risk Assessment**
- Interactive risk matrix (Consequence vs Likelihood)
- Color-coded risk levels (Low, Moderate, High, Extreme)
- Risk mitigation tracking

### 📅 **Multi-Year Planning**
- Financial year budget forecasting
- Cost distribution visualization
- Timeline planning and tracking

### 📊 **Status Tracking**
- Project lifecycle monitoring
- Status change history
- Progress reporting

### ⚙️ **Administration**
- Reference data management (Asset Classes, Types, Statuses)
- Configurable criteria weights
- Data backup and export
- Software registration configuration

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/[your-username]/ASAP-Capex-Planning.git
   cd ASAP-Capex-Planning
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the application:
   - Edit `config.ini` to set your organization details
   - The database will be created automatically on first run

## Usage

### Running the Application
```bash
streamlit run capex_app.py
```

The application will be available at `http://localhost:8501`

### Configuration
Edit `config.ini` to customize:
- Organization registration details
- Software branding information
- Display preferences

### Data Import
- Use the built-in import feature to load projects from Excel/CSV
- Download the provided template for correct column formatting
- Supports bulk project creation and updates

## Project Structure

```
ASAP-Capex-Planning/
├── capex_app.py              # Main application file
├── config.ini                # Configuration settings
├── requirements.txt          # Python dependencies
├── project_import_template.xlsx  # Excel template for imports
├── sample_correct_columns.csv    # Sample data format
├── README.md                 # This file
└── capex_planning.db         # SQLite database (created automatically)
```

## Database Schema

The application uses SQLite with the following main tables:
- **Projects**: Core project information
- **Assets**: Asset management and classification
- **Priority Scores**: Weighted scoring system
- **Risk Assessments**: Risk evaluation data
- **Project Costs**: Multi-year financial planning
- **Reference Data**: Configurable lookup tables

## Key Features

### Priority Scoring
Projects are evaluated using weighted criteria:
- **WHS (30%)**: Work Health & Safety considerations
- **Water Savings (20%)**: Environmental impact
- **Customer (30%)**: Customer service impact
- **Maintenance/Ops (10%)**: Operational considerations
- **Financial (10%)**: Financial implications

### Risk Matrix
5x6 risk matrix combining:
- **Consequence levels**: Low to Catastrophic
- **Likelihood levels**: Rare to Almost Certain
- **Risk ratings**: Low, Moderate, High, Extreme

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This software is produced by **Odysseus-imc Pty Ltd**.

## Support

For technical support or questions:
- Check the in-app FAQ section
- Review the user documentation
- Contact your system administrator

## Version History

- **v1.0 (Beta)**: Initial release with core CAPEX planning features
- Comprehensive project management
- Priority scoring and risk assessment
- Multi-year financial planning
- Configuration management

---

**Registered to**: [Your Organization Name]  
**Produced by**: Odysseus-imc Pty Ltd  
**Version**: 1.0 (Beta)