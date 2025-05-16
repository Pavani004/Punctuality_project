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



