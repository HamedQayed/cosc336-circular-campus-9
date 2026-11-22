import hmac
import secrets
from functools import wraps
from flask import g, request, session, redirect, url_for
from .db import Repository
from .domain import RuleError


class Policy:
    """Default-deny roles, plus record scopes, shared by UI and AI retrieval."""
    def require(self, actor, *roles):
        if not actor or not actor['active'] or actor['role'] not in roles:
            raise RuleError('Your account does not have permission for this action.', 403)

    def unit(self, actor, unit, write=False):
        if not actor:
            raise RuleError('Sign in first.', 403)
        if actor['role'] == 'custodian' and unit['custodian_id'] == actor['id']:
            return
        if not write and actor['role'] in ('workflow_admin', 'system_admin'):
            return
        if not write and actor['role']=='custodian' and Repository().all('SELECT id FROM transfers WHERE unit_id=? AND source_custodian_id=?',(unit['id'],actor['id'])):
            return
        if not write and actor['role'] == 'maintenance':
            if Repository().all('SELECT id FROM maintenance WHERE unit_id=? AND assignee_id=?', (unit['id'], actor['id'])):
                return
        if not write and unit['publication'] == 'Published' and unit['lifecycle'] == 'Active':
            return
        if not write and Repository().all('SELECT r.id FROM requests r JOIN holds h ON h.request_id=r.id '
                                           'WHERE h.unit_id=? AND (r.creator_id=? OR '
                                           '(r.destination_dept_id=? AND ? IN (\'representative\',\'custodian\')))',
                                           (unit['id'], actor['id'], actor['department_id'], actor['role'])):
            return
        raise RuleError('This asset is outside your record scope.', 403)

    def request(self, actor, rec):
        if actor['role'] == 'workflow_admin' or rec['creator_id'] == actor['id']:
            return
        if actor['role'] == 'representative' and rec['destination_dept_id'] == actor['department_id']:
            return
        if actor['role'] == 'custodian':
            if rec['destination_custodian_id'] == actor['id']:
                return
            if Repository().all('SELECT t.id FROM transfers t WHERE t.request_id=? AND t.source_custodian_id=?',
                                (rec['id'], actor['id'])):
                return
        raise RuleError('This request is outside your record scope.', 403)

    def evidence(self, actor, unit):
        if actor['role'] in ('workflow_admin','system_admin'):
            return
        if actor['role']=='custodian' and unit['custodian_id']==actor['id']:
            return
        if actor['role']=='custodian' and Repository().all('SELECT id FROM transfers WHERE unit_id=? AND source_custodian_id=?',(unit['id'],actor['id'])):
            return
        repo=Repository()
        if actor['role']=='custodian' and repo.all('SELECT r.id FROM requests r JOIN holds h ON h.request_id=r.id WHERE h.unit_id=? AND r.destination_custodian_id=? AND r.status IN (\'Approved\',\'Completed\')',(unit['id'],actor['id'])):
            return
        if actor['role']=='maintenance' and repo.all('SELECT id FROM maintenance WHERE unit_id=? AND assignee_id=?',(unit['id'],actor['id'])):
            return
        raise RuleError('This evidence is outside your assigned record scope.',403)


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


def load_identity():
    g.user = None
    if session.get('user_id'):
        rows = Repository().all('SELECT * FROM users WHERE id=? AND active=1', (session['user_id'],))
        if rows:
            g.user = rows[0]
        else:
            session.clear()
    if request.method == 'POST':
        expected, actual = session.get('csrf', ''), request.form.get('csrf_token', '')
        if not expected or not hmac.compare_digest(expected, actual):
            raise RuleError('Your form expired. Reload the page and try again.', 400)


def signed_in(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for('auth.login'))
        return fn(*args, **kwargs)
    return wrapped
