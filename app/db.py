import sqlite3
from contextlib import contextmanager
from pathlib import Path
from flask import current_app, g
from .domain import RuleError, stamp


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=5, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=5000')
    return g.db


def close_db(_=None):
    db = g.pop('db', None)
    if db:
        db.close()


@contextmanager
def transaction():
    db = get_db()
    try:
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise RuleError('The record conflicts with an existing record or stock hold.', 409) from None
    except sqlite3.OperationalError as error:
        db.rollback()
        if 'locked' in str(error).lower() or 'busy' in str(error).lower():
            raise RuleError('The database is busy. Please try the action again.', 409) from None
        raise
    except BaseException:
        db.rollback()
        raise


class Repository:
    def one(self, sql, params=()):
        row = get_db().execute(sql, params).fetchone()
        if row is None:
            raise RuleError('Record not found.', 404)
        return row

    def all(self, sql, params=()):
        return get_db().execute(sql, params).fetchall()

    def write(self, sql, params=()):
        return get_db().execute(sql, params)

    def event(self, actor, kind, target, action, detail, recipients=()):
        cur = self.write('INSERT INTO audit(actor_id,target_type,target_id,action,detail,created_at) VALUES(?,?,?,?,?,?)',
                         (actor['id'] if actor else None, kind, target, action, detail, stamp()))
        for recipient in set(recipients):
            self.write('INSERT INTO notifications(recipient_id,audit_id,message) VALUES(?,?,?)',
                       (recipient, cur.lastrowid, f'{action}: {detail}'))

    def life(self, actor, unit_id, action, detail, cost=None):
        self.write('INSERT INTO events(unit_id,actor_id,action,detail,cost_cents,created_at) VALUES(?,?,?,?,?,?)',
                   (unit_id, actor['id'], action, detail, cost, stamp()))

    def role_users(self, role):
        return [u['id'] for u in self.all('SELECT id FROM users WHERE role=? AND active=1', (role,))]


def init_schema():
    get_db().executescript(Path(__file__).with_name('schema.sql').read_text())
