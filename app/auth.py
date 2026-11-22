from flask import Blueprint, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from .db import Repository, transaction
from .domain import ROLES, RuleError
from .forms import text, integer, choice
from .security import Policy, signed_in

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        rows = Repository().all('SELECT * FROM users WHERE username=? AND active=1', (request.form.get('username', ''),))
        if rows and check_password_hash(rows[0]['password_hash'], request.form.get('password', '')):
            session.clear()
            session['user_id'] = rows[0]['id']
            return redirect(url_for('home'))
        error = 'Incorrect username or password.'
    return render_template('login.html', error=error), (400 if error else 200)


@bp.post('/logout')
@signed_in
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


class AccountService:
    def save(self, actor, data):
        Policy().require(actor, 'system_admin')
        repo = Repository()
        with transaction():
            if data.get('operation') == 'department':
                cur = repo.write('INSERT INTO departments(name) VALUES(?)', (text(data, 'name', 100),))
                repo.event(actor, 'department', cur.lastrowid, 'Department created', text(data, 'name', 100))
                return
            if data.get('operation') == 'deactivate':
                target = repo.one('SELECT * FROM users WHERE id=?', (integer(data, 'user_id'),))
                if target['id'] == actor['id']:
                    raise RuleError('Use another system administrator to deactivate your own account.')
                if repo.all('SELECT id FROM units WHERE custodian_id=?', (target['id'],)):
                    raise RuleError('Reassign custody before deactivating this account.', 409)
                if repo.all("SELECT id FROM requests WHERE destination_custodian_id=? AND status IN ('Seeking','Pending','Approved')", (target['id'],)):
                    raise RuleError('Resolve incoming requests before deactivating the receiving custodian.', 409)
                repo.write('UPDATE users SET active=0 WHERE id=?', (target['id'],))
                repo.event(actor, 'user', target['id'], 'Account deactivated', target['username'])
                return
            password = text(data, 'password', 200)
            if len(password) < 12:
                raise RuleError('Use a password of at least 12 characters.')
            department = integer(data, 'department_id')
            repo.one('SELECT id FROM departments WHERE id=?', (department,))
            cur = repo.write('INSERT INTO users(username,name,password_hash,role,department_id) VALUES(?,?,?,?,?)',
                             (text(data, 'username', 80), text(data, 'name', 100), generate_password_hash(password),
                              choice(data, 'role', ROLES), department))
            repo.event(actor, 'user', cur.lastrowid, 'Account created', 'Role and department assigned')


@bp.route('/accounts', methods=['GET', 'POST'])
@signed_in
def accounts():
    Policy().require(g.user, 'system_admin')
    if request.method == 'POST':
        AccountService().save(g.user, request.form)
        flash('Account or department updated.')
        return redirect(url_for('auth.accounts'))
    return render_template('accounts.html', users=Repository().all('SELECT u.id,u.name,u.username,u.role,u.active,d.name department FROM users u JOIN departments d ON d.id=u.department_id'), roles=ROLES)
