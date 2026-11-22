"""Synthetic demonstration data only. Passwords are generated locally and never tracked."""
import secrets
from pathlib import Path
from werkzeug.security import generate_password_hash
from flask import current_app
from .db import Repository, transaction
from .domain import ROLES, stamp


def seed_demo(password=None):
    repo = Repository()
    if repo.all('SELECT id FROM users LIMIT 1'):
        return False
    password = password or secrets.token_urlsafe(16)
    with transaction():
        repo.write("INSERT INTO departments(id,name) VALUES(1,'Engineering'),(2,'Business')")
        accounts = [(1,'requester','Engineering requester','requester',1),
                    (2,'custodian','Engineering custodian','custodian',1),
                    (3,'receiver','Business custodian','custodian',2),
                    (4,'approver','Workflow administrator','workflow_admin',1),
                    (5,'sysadmin','System administrator','system_admin',1),
                    (6,'representative','Business representative','representative',2),
                    (7,'maintenance','Engineering maintenance','maintenance',1),
                    (8,'procurement','Procurement officer','procurement',1),
                    (9,'finance','Finance officer','finance',1),
                    (10,'sustainability','Sustainability officer','sustainability',1),
                    (11,'requester2','Business requester','requester',2)]
        for uid, username, name, role, dept in accounts:
            repo.write('INSERT INTO users VALUES(?,?,?,?,?,?,1)', (uid,username,name,generate_password_hash(password),role,dept))
        samples = [('Ergonomic office chair','Furniture','Adjustable chair with wheels',6,30000),
                   ('Dell 24 inch monitor','IT','HDMI full HD monitor',5,65000),
                   ('Software engineering textbook','Books','Software engineering reference book',5,15000),
                   ('Laboratory stool','Laboratory','Height adjustable lab stool',4,None)]
        for lid,(name,category,desc,qty,value) in enumerate(samples,1):
            repo.write('INSERT INTO listings VALUES(?,?,?,?,?,?)', (lid,name,desc,category,desc,2))
            for _ in range(qty):
                uid=repo.write('INSERT INTO units(listing_id,owner_dept_id,custodian_id,location,condition,publication,value_cents) VALUES(?,1,2,?,?,?,?)',
                               (lid,'Engineering store','Good','Published',value)).lastrowid
                repo.life({'id':2},uid,'Registered','Synthetic baseline unit; publication preapproved for demo')
                repo.life({'id':4},uid,'Published','Synthetic seeded release approval')
        repo.event({'id':5}, 'system', 0, 'Demo initialized', '20 synthetic units, two departments, nine permission profiles')
    if not current_app.testing:
        path = Path(current_app.instance_path)/'demo-credentials.txt'
        path.write_text('LOCAL SYNTHETIC DEMO ONLY\nAll seeded accounts initially use: '+password+'\nUsernames: '+', '.join(a[1] for a in accounts)+'\n')
        path.chmod(0o600)
    return True
