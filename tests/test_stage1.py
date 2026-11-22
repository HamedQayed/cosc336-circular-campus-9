import pytest
from werkzeug.security import check_password_hash
from app.db import Repository
from app.auth import AccountService
from app.domain import RuleError,ROLES
from conftest import login,post,user


def test_login_requires_authentication(client):
    assert client.get('/').status_code==302
    client.get('/login')
    with client.session_transaction() as session:csrf=session['csrf']
    response=client.post('/login',data={'csrf_token':csrf,'username':'requester2','password':'Test fixture password only 123'},follow_redirects=True)
    assert response.status_code==200 and b'Good resources' in response.data


def test_missing_csrf_cannot_login(client):
    assert client.post('/login',data={'username':'requester2','password':'x'}).status_code==400


def test_nine_profiles_and_hashed_credentials(app):
    with app.app_context():
        rows=Repository().all('SELECT * FROM users')
        assert {r['role'] for r in rows}==set(ROLES)
        assert all(r['password_hash']!='Test fixture password only 123' and check_password_hash(r['password_hash'],'Test fixture password only 123') for r in rows)


@pytest.mark.parametrize('uid',[1,2,3,4,6,7,8,9,10,11])
def test_business_roles_cannot_manage_accounts(client,uid):
    login(client,uid)
    assert client.get('/accounts').status_code==403


def test_system_admin_can_create_department_and_account(app):
    with app.app_context():
        service=AccountService();service.save(user(5),{'operation':'department','name':'Design'})
        service.save(user(5),{'name':'New tester','username':'new-tester','password':'Long initial test password','role':'requester','department_id':'3'})
        assert Repository().one("SELECT * FROM users WHERE username='new-tester'")['department_id']==3


def test_deactivated_account_loses_active_session(app,client):
    login(client,11)
    with app.app_context():AccountService().save(user(5),{'operation':'deactivate','user_id':'11'})
    assert client.get('/').status_code==302


def test_custody_blocks_deactivation(app):
    with app.app_context(),pytest.raises(RuleError):
        AccountService().save(user(5),{'operation':'deactivate','user_id':'2'})


def test_notifications_are_recipient_scoped(app,client):
    with app.app_context():Repository().event(user(5),'system',0,'Private event','Private request',[11])
    login(client,1);assert b'Private request' not in client.get('/notifications').data
    login(client,11);assert b'Private request' in client.get('/notifications').data
