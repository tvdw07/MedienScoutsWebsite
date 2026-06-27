# Ticket System

A comprehensive ticketing system with multiple ticket types and user management. This software enables users to create, manage, and track tickets efficiently while providing an administrative interface for user and system configuration.

## Features
- Multiple ticket types for different use cases
- User-friendly interface for ticket creation, management, and tracking
- Permission-based access control with role grouping
- Administrative panel for configuration and user management
- Logging and history tracking for tickets

## Project Structure
The application is split into focused blueprints instead of a single route module:

- `app/blueprints/main/pages.py` for public pages and legal content
- `app/blueprints/main/tickets.py` for ticket submission and ticket handling
- `app/blueprints/main/account.py` for profile and session actions
- `app/blueprints/main/utils.py` for shared ticket helpers
- `app/blueprints/bp_auth.py` for authentication
- `app/blueprints/bp_admin.py` for administration

The legacy `app/routes.py` import path still exists as a thin compatibility wrapper.
Details are documented in [docs/project-structure.md](docs/project-structure.md).

## Permission System
The application now uses a permission-based model instead of direct role checks.
Full details are documented in [docs/permission-system.md](docs/permission-system.md).

In short:
- Permissions are defined centrally in `app/permission_seed.py`
- Roles only group permissions
- User overrides can allow or deny individual permissions
- Protected routes use `@permission_required("permission.name")`
- Standard roles are `Admin`, `Teacher`, `MediaScout`, and `User`

## Legal Configuration
The legal pages read their operator-specific data from `LEGAL_*` environment variables:

- `LEGAL_OPERATOR_NAME`
- `LEGAL_ORGANIZATION_NAME`
- `LEGAL_REPRESENTATIVE_NAME`
- `LEGAL_STREET`
- `LEGAL_HOUSE_NUMBER`
- `LEGAL_POSTAL_CODE`
- `LEGAL_CITY`
- `LEGAL_COUNTRY`
- `LEGAL_PHONE`
- `LEGAL_EMAIL`
- `LEGAL_WEBSITE`
- `LEGAL_VAT_ID`
- `LEGAL_EDITORIAL_RESPONSIBLE_NAME`
- `LEGAL_EDITORIAL_RESPONSIBLE_EMAIL`
- `LEGAL_PRIVACY_CONTACT_NAME`
- `LEGAL_PRIVACY_CONTACT_EMAIL`
- `LEGAL_SUPPORT_EMAIL`
- `LEGAL_GITHUB_REPOSITORY`
- `LEGAL_VERSION`
- `LEGAL_BUILD_NUMBER`
- `LEGAL_LAWFUL_BASIS_TEXT`
- `LEGAL_STORAGE_DURATION_TEXT`

If a value is omitted, the pages fall back to neutral placeholders or built-in defaults where appropriate.

## Installation

The project install instructions are based on Ubuntu 22.04, but PostgreSQL is now used as the default database.
Redis is used for rate limiting.

### Step 1: Update the system to the newest version

```bash 
sudo apt update && sudo apt upgrade -y
```

Also install the following packages:

```bash
sudo apt install python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools
sudo apt install python3-venv
```

### Step 2: Install gh and authenticate with your github account

```bash
sudo apt install gh
gh auth login
```

### Step 3: Clone the repository

```bash
gh repo clone tvdw07/MedienScoutsWebsite
```

### Step 4: Install the required packages

```bash
sudo apt install python3 python3-pip python3-venv
```

### Step 5: Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 6: Install the required packages

```bash
pip install -r requirements.txt
```

### Step 7: Update the configuration file

```bash
cp .env.example .env
nano .env
```

### Step 8: Datenbank initialisieren

Make sure PostgreSQL and Redis are running, then execute the following script to create the database tables and apply
migrations:

```bash
python setup_db.py
```

### Step 9: (Optional) Test the application

```bash
python wsgi.py
```

If it does not work, check your firewall settings.

Test the application with the following command:
```bash
sudo ufw allow 8000
gunicorn --workers 4 --worker-class gevent --timeout 120 --bind 0.0.0.0:8000 wsgi:app 
```

You can then call up the application via the server IP and port 8000.

### Docker

Create or update `.env` from `.env.example`, then start the app:

```bash
docker compose up --build
```

The container runs `python setup_db.py` before starting Gunicorn on port `8000`.
PostgreSQL data is stored in the `postgres_data` volume, uploads in the `app_uploads` volume.
For production behind HTTPS, set:

```env
APP_ENV=production
FORCE_HTTPS=true
SESSION_COOKIE_SECURE=true
```

PostgreSQL and Redis are started as part of the compose stack. For local development without Docker, point
`DATABASE_URL` and `RATELIMIT_STORAGE_URI` at running services.

### Step 10: Complete Setup Individually

- Create a systemd service with gunicorn
- Activate the service
- Install nginx
- Create a new site configuration
- Activate the site
- Restart the systemd service
- Restart nginx
- Test the application

Ein gutes Tutorial findest du hier:
https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-22-04

## Usage
Open the application after setup, sign in, and use the home page ticket form or the ticket administration views depending on your permissions.

## Contributing
We welcome contributions! If you're interested in contributing, you can:
- Fork the repository and submit pull requests
- Open issues to report bugs or suggest new features

### License Compliance
- Ensure proper credit is given both visually within the software and in the Impressum.
- Keep the responsible contact details in `.env` up to date when the legal owner changes.

## License
This project is licensed under the applicable terms. See the `LICENSE` file for more details.

## Contact
Responsible contact details are configured through the environment variables listed above.
