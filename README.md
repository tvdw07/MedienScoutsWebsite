# Ticket System

A comprehensive ticketing system with multiple ticket types and user management. This software enables users to create, manage, and track tickets efficiently while providing an administrative interface for user and system configuration.

## Features
- Multiple ticket types for different use cases
- User-friendly interface for ticket creation, management, and tracking
- Role-based user management system
- Administrative panel for configuration and user management
- Logging and history tracking for tickets

## Installation

The project install instructions are based on ubuntu 22.04.

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
#For the db and security settings
nano config.py
#For the email settings
nano config.ini
```

#### Step 7.1: Create the database

```bash
sudo apt-get install mariadb-server
```

```bash
sudo mysql_secure_installation
```

```bash
sudo mysql -u root -p
```

#### Step 7.2: Create the database

Activate the virtual environment if it isn't anymore:

```bash
source venv/bin/activate
```

Please use the following command to create the database tables:

```bash
flask db init
flask db migrate -m "Initial migration."
flask db upgrade
```

After creating the database, you can insert the ticket status values:

```bash
INSERT INTO ticket_status (id, status) 
VALUES 
(1, 'open'),
(2, 'seen'),
(3, 'in progress'),
(4, 'closed'),
(5, 'help required');
```

### Step 8: (Optional) Test the application

```bash
python wsgi.py
```

If it doesn't work please check your firewall settings.

After that test it with the following command:
```bash
sudo ufw allow 8000
gunicorn --workers 4 --worker-class gevent --timeout 120 --bind 0.0.0.0:8000 wsgi:app 
```

Then you can access the application via the server ip and port 8000.

### Step 9: Complete Setup Individually

-Create a systemd service with gunicorn

-Enable the service

-Install nginx

-Create a new site configuration

-Enable the site

-Restart systemd service

-Restart nginx

-Test the application

A good tutorial can be found here:
https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-22-04

## Usage
Detailed usage instructions will be announced in future updates. The system will provide an intuitive interface for users to interact with the ticketing system seamlessly.

## Contributing
We welcome contributions! If you're interested in contributing, you can:
- Fork the repository and submit pull requests
- Open issues to report bugs or suggest new features

### License Compliance
- Ensure proper credit is given both visually within the software and in the Impressum.
- For commercial use, please contact Tim von der Weppen via email.

## License
This project is licensed under the applicable terms. See the `LICENSE` file for more details.

## Contact
For support or inquiries, please reach out to:

**Tim von der Weppen**  
Email: [tim.vonderweppen@web.de](mailto:tim.vonderweppen@web.de)

