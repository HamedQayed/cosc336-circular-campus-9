import shutil
import pytest
from app import create_app
from app.seed import seed_demo
from app.db import Repository


@pytest.fixture(scope='session')
def baseline(tmp_path_factory):
    root=tmp_path_factory.mktemp('baseline')
    app=create_app({'TESTING':True,'DATABASE':str(root/'baseline.sqlite'),'EVIDENCE_DIR':str(root/'evidence')})
    with app.app_context():seed_demo('Test fixture password only 123')
    return root/'baseline.sqlite'


@pytest.fixture
def app(tmp_path,baseline):
    (tmp_path/'active').mkdir()
    shutil.copy2(baseline,tmp_path/'active'/'test.sqlite')
    return create_app({'TESTING':True,'DATABASE':str(tmp_path/'active'/'test.sqlite'),'EVIDENCE_DIR':str(tmp_path/'active'/'evidence'),
                       'SECRET_KEY':'test-session-fixture-only','OPENAI_API_KEY':'','OPENROUTER_API_KEY':'','AI_MODEL':''})


@pytest.fixture
def client(app):return app.test_client()


def user(uid):return Repository().one('SELECT * FROM users WHERE id=?',(uid,))


def login(client,uid):
    with client.session_transaction() as session:
        session['user_id']=uid;session['csrf']='test-csrf'


def post(client,path,**data):
    return client.post(path,data={'csrf_token':'test-csrf',**data})
