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

```mysql
CREATE DATABASE msdb /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci */;
USE msdn;
CREATE TABLE message (
  id int(11) NOT NULL AUTO_INCREMENT,
  author varchar(64) NOT NULL,
  role varchar(64) NOT NULL,
  content text NOT NULL,
  timestamp datetime DEFAULT current_timestamp(),
  deleted tinyint(1) DEFAULT 0,
  PRIMARY KEY (id)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE ticket_status (
  id int(11) NOT NULL AUTO_INCREMENT,
  status varchar(50) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE misc_ticket (
  id int(11) NOT NULL AUTO_INCREMENT,
  first_name varchar(50) NOT NULL,
  last_name varchar(50) NOT NULL,
  email varchar(100) NOT NULL,
  message text NOT NULL,
  created_at datetime DEFAULT current_timestamp(),
  status_id int(11) DEFAULT 1,
  PRIMARY KEY (id),
  KEY status_id (status_id),
  CONSTRAINT misc_ticket_ibfk_1 FOREIGN KEY (status_id) REFERENCES ticket_status (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE user (
  id int(11) NOT NULL AUTO_INCREMENT,
  username varchar(150) NOT NULL,
  password_hash varchar(512) DEFAULT NULL,
  email varchar(120) NOT NULL,
  first_name varchar(50) NOT NULL,
  last_name varchar(50) NOT NULL,
  role enum('ADMIN','TEACHER','MEMBER') NOT NULL DEFAULT 'MEMBER',
  user_rank enum('KEIN','BRONZE','SILBER','GOLD','PLATIN') DEFAULT 'KEIN',
  active tinyint(1) DEFAULT 1,
  active_from datetime DEFAULT NULL,
  active_until datetime DEFAULT NULL,
  last_login datetime DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY username (username),
  UNIQUE KEY email (email)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE misc_ticket_user (
  ticket_user_id int(11) NOT NULL AUTO_INCREMENT,
  misc_ticket_id int(11) NOT NULL,
  user_id int(11) NOT NULL,
  assigned_at datetime DEFAULT current_timestamp(),
  PRIMARY KEY (ticket_user_id),
  KEY misc_ticket_id (misc_ticket_id),
  KEY user_id (user_id),
  CONSTRAINT misc_ticket_user_ibfk_1 FOREIGN KEY (misc_ticket_id) REFERENCES misc_ticket (id),
  CONSTRAINT misc_ticket_user_ibfk_2 FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE problem_ticket (
  id int(11) NOT NULL AUTO_INCREMENT,
  first_name varchar(50) NOT NULL,
  last_name varchar(50) NOT NULL,
  email varchar(100) NOT NULL,
  class_name varchar(50) NOT NULL,
  serial_number varchar(50) DEFAULT NULL,
  problem_description text NOT NULL,
  steps_taken text DEFAULT NULL,
  photo varchar(200) DEFAULT NULL,
  created_at datetime DEFAULT current_timestamp(),
  status_id int(11) DEFAULT 1,
  PRIMARY KEY (id),
  KEY status_id (status_id),
  CONSTRAINT problem_ticket_ibfk_1 FOREIGN KEY (status_id) REFERENCES ticket_status (id)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE problem_ticket_user (
  ticket_user_id int(11) NOT NULL AUTO_INCREMENT,
  problem_ticket_id int(11) NOT NULL,
  user_id int(11) NOT NULL,
  assigned_at datetime DEFAULT current_timestamp(),
  PRIMARY KEY (ticket_user_id),
  KEY problem_ticket_id (problem_ticket_id),
  KEY user_id (user_id),
  CONSTRAINT problem_ticket_user_ibfk_1 FOREIGN KEY (problem_ticket_id) REFERENCES problem_ticket (id),
  CONSTRAINT problem_ticket_user_ibfk_2 FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE ticket_history (
  id int(11) NOT NULL AUTO_INCREMENT,
  ticket_type varchar(50) NOT NULL,
  ticket_id int(11) NOT NULL,
  message text NOT NULL,
  created_at datetime DEFAULT current_timestamp(),
  author_type varchar(50) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


INSERT INTO ticket_status (id, status) 
VALUES 
(1, 'open'),
(2, 'seen'),
(3, 'in progress'),
(4, 'closed'),
(5, 'help required');


CREATE TABLE training_ticket (
  id int(11) NOT NULL AUTO_INCREMENT,
  class_teacher varchar(50) NOT NULL,
  email varchar(100) NOT NULL,
  training_type varchar(100) NOT NULL,
  training_reason text DEFAULT NULL,
  proposed_date datetime DEFAULT NULL,
  created_at datetime DEFAULT current_timestamp(),
  status_id int(11) DEFAULT 1,
  PRIMARY KEY (id),
  KEY status_id (status_id),
  CONSTRAINT training_ticket_ibfk_1 FOREIGN KEY (status_id) REFERENCES ticket_status (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE training_ticket_user (
  ticket_user_id int(11) NOT NULL AUTO_INCREMENT,
  training_ticket_id int(11) NOT NULL,
  user_id int(11) NOT NULL,
  assigned_at datetime DEFAULT current_timestamp(),
  PRIMARY KEY (ticket_user_id),
  KEY training_ticket_id (training_ticket_id),
  KEY user_id (user_id),
  CONSTRAINT training_ticket_user_ibfk_1 FOREIGN KEY (training_ticket_id) REFERENCES training_ticket (id),
  CONSTRAINT training_ticket_user_ibfk_2 FOREIGN KEY (user_id) REFERENCES user (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
```

### Step 8: (Optional) Test the application

```bash
python wsgi.py
```

### Step 9: Create a systemd service with gunicorn

### Step 10: Enable the service

### Step 11: Install nginx

```bash
sudo apt install nginx
```

### Step 12: Create a new site configuration

### Step 13: Enable the site

### Step 14: Restart nginx

### Step 15: Test the application

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

