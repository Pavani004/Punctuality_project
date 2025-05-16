#  Late Attendance Tracker – Punctuality Monitoring System

A real-world college project designed to automate the process of tracking late arrivals and improve student punctuality. The system logs late students using facial recognition and sends alerts to parents if the student is late more than three times in a week.

##  Features

- 🔐 **Face Recognition** using OpenCV
- 🧾 **Attendance Logging** with CSV + MySQL
- 📤 **Automated Notifications** to parents after 3 late entries/week
- 📊 Admin dashboard to view logs
- 🏫 Deployed successfully in a real college environment

## 🛠 Tech Stack

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS, Bootstrap
- **Computer Vision:** OpenCV
- **Database:** MySQL
- **File Handling:** CSV
  
Step 1 - 

Python -m venv venv


step 2-

venv/Scripts/activate

step3 -

pip install -r requirements.txt


step4 -

setup database in mysql

create database lateattendance;

--This will create a database

step4

on terminal run python app.py

flask db init

flask db migrate -m "Initial migration"

flask db upgrade

--these will create all the tables automatically after execution

after running this also run python app.py



