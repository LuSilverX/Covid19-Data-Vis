# COVID-19 Data Visualization Dashboard

![Python](https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python)
![Django](https://img.shields.io/badge/Django-5.1-blue?style=for-the-badge&logo=django)
![Celery](https://img.shields.io/badge/Celery-5.x-blue?style=for-the-badge&logo=celery)

A Django-based web application for visualizing COVID-19 data. It includes a historical dashboard (from static CSVs) and a live dashboard that loads CDC/NCHS weekly death counts via the Socrata CSV API (with cumulative totals computed in-app) and WHO global data via CSV download. Updates run via Celery with on-demand refreshes and scheduled jobs — CDC daily, WHO weekly. 

Note: Some older Selenium-based scraping features are now deprecated, so you may see certain steps or tools crossed out — they’re kept only for reference. Selenium scraper (fetch_cdc_data, _scrape_and_save_state_data) and AWS deployment files—kept for reference only and not used by the app.

## Key Features

- **Historical Dashboard**: Paginated tables and interactive line charts for US national, state, and county-level data. Filter charts by state or county using AJAX APIs.
- **Live Dashboard**: CDC/NCHS weekly death counts via the Socrata CSV API (with cumulative totals computed in-app) and WHO global data (cases/deaths by country/region). Supports filtering and pagination.
- **On-Demand Data Refresh**: Trigger background tasks to fetch CDC/NCHS weekly deaths (API) and WHO data; the frontend polls for completion and updates dynamically. ~~Scrape CDC data with Selenium (deprecated)~~.
- **Scheduled Updates**: Celery Beat runs daily tasks to refresh CDC (all states) and weekly tasks to refresh WHO data automatically.
- **Asynchronous Processing**: Uses Celery with Redis for task queuing, ensuring the UI remains responsive during long-running jobs.
- **APIs**: Endpoints for chart data, state/county lists, paginated data, task status, and refresh triggers.

## Technical Stack

- **Backend**: Django 5.1, Celery 5.x (with Redis broker), Requests for CDC/NCHS Socrata CSV + WHO CSV, ~~Selenium for CDC scraping (deprecated/dormant)~~.
- **Database**: MySQL.
- **Frontend**: Django templates, JavaScript/jQuery for AJAX polling and dynamic updates, Chart.js for visualizations.
- **Other**: Celery Beat (scheduling), Channels/ASGI + WSGI, python-dotenv for env vars, structured logging, pagination via Django Paginator, AWS deployment files included.

## Project Structure
- `covid19_project`
  - `covid19_project/` — project config, settings, URLs (includes Celery Beat schedules)
  - `data_handler/` — core app: models, views, tasks, templates
    - `tasks.py` — Socrata API task (current); ~~Selenium scraper (deprecated/dormant): `fetch_cdc_data`, `_scrape_and_save_state_data`~~
    - `management/commands/import_historical_data.py` — loads static CSVs
  - `Data/` — Contains the initial CSV files needed to populate the historical database tables.
  - `static/` — CSS/JS assets
  - `cdc_downloads/` — legacy folder used by the old scraper (optional to keep)
  - `.env.example`
  - `manage.py`
- `requirements.txt` — Python dependencies (repo root; alongside `covid19_project/`)
- `aws/` (or `deploy/`) — AWS deployment files included for reference — project runs locally by default.
  
## Setup and Installation

### Prerequisites

- Python 3.9+
- MySQL Server
- Redis Server (make sure it’s running)
- ~~Google Chrome browser~~
- ~~ChromeDriver (for Selenium -deprecated)~~
- Build/CLI tools: pkg-config, MySQL client libs, Redis CLI
```bash
# macOS (Homebrew)
brew install mysql redis pkg-config
```
### 1. Clone the Repository
```bash
git clone https://github.com/LuSilverX/Covid19-Data-Vis.git
cd Covid19-Data-Vis #repo root
```
From here on, run commands in a terminal at the repo root (e.g., your system terminal or VS Code: View → Terminal).
### 2. Create Your Environment File
Copy the template (the .env must live in covid19_project/):
```bash
# macOS/Linux (bash/zsh)
python3 -c 'import secrets, string; alphabet=string.ascii_letters+string.digits+"!@#$%^&*(-_=+)"; print("".join(secrets.choice(alphabet) for _ in range(50)))'

# Windows (PowerShell)
$key = python -c 'import secrets, string; alphabet=string.ascii_letters+string.digits+"!@#$%^&*(-_=+)"; print("".join(secrets.choice(alphabet) for _ in range(50)))'; $key

# Windows (CMD)
python -c "import secrets, string; alphabet=string.ascii_letters+string.digits+'!@#$%^&*(-_=+)'; print(''.join(secrets.choice(alphabet) for _ in range(50)))"
```
Open covid19_project/.env and replace placeholders:
- DJANGO_SECRET_KEY → generate one (see below)
- DB_USER, DB_PASSWORD → your local MySQL creds
- (optional) SOCRATA_APP_TOKEN → add to avoid rate limits

To generate a key:
```bash
# macOS/Linux
python3 -c 'import secrets, string; alphabet=string.ascii_letters+string.digits+"!@#$%^&*(-_=+)"; print("".join(secrets.choice(alphabet) for _ in range(50)))'
# Windows (PowerShell or CMD)
$key = python -c 'import secrets, string; alphabet=string.ascii_letters+string.digits+"!@#$%^&*(-_=+)"; print("".join(secrets.choice(alphabet) for _ in range(50)))'
```
### 3. Set Up Python Virtual Environment In Project Root
```bash
Run from the repo root covid19-data-vis/ if not there already

# macOS / Linux (run from the repo root Covid19-Data-Vis/ if not there already)
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
py -3 -m venv .venv
.venv\Scripts\Activate.ps1

# Windows (CMD)
py -3 -m venv .venv
.venv\Scripts\activate.bat
```
### 4. Install Dependencies
```bash
pip install -r requirements.txt
```
### 5. Configure Database
From a system terminal, open the MySQL client, then run the SQL:
```bash
mysql -u youruser
```
At the mysql> prompt:
```bash
CREATE DATABASE covid19_data_vis;
```
### 6. Run Migrations
Back at the repo root in the .venv run:
```bash
python3 covid19_project/manage.py migrate
```
### 7. Import Historical Data
```bash
python3 covid19_project/manage.py import_historical_data
```
### 8. Running the Application
Make sure MySQL and Redis are running (macOS example using Homebrew):
```bash
brew services start mysql
brew services start redis    # required before starting Celery
```
Go into the Django project folder (where manage.py lives)
```bash
cd covid19_project
```
Run in separate terminals:
1. Celery worker
```bash
celery -A covid19_project worker --loglevel=info -c 2
```
2. Celery Beat
```bash
celery -A covid19_project beat --loglevel=info
```
3.	Django server
```bash
python3 covid19_project/manage.py runserver
```
Visit http://127.0.0.1:8000/

Notes:
1. Environment Variables: Secrets live in .env, which is ignored by Git. See .env.example.
2. Local Ignored Files: .venv/, .idea/, .DS_Store, and .env are in .gitignore.
