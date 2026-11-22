import pytest

from app.db import Repository
from app.domain import RuleError
from app.exchange import ExchangeService
from app.workflow import WorkflowService
from conftest import user
from test_stage2 import request_data
from test_stage3 import approved, evidence


def expire_request(repo,rid):
    repo.write("UPDATE requests SET expires_at='2000-01-01T00:00:00+04:00' WHERE id=?",(rid,))


@pytest.mark.parametrize('operation',['decide','cancel','reserve'])
def test_rejected_action_still_commits_expiration(app,operation):
    with app.app_context():
        repo=Repository()
        exchange=ExchangeService()
        rid=exchange.reserve(user(11),request_data())
        expire_request(repo,rid)
        with pytest.raises(RuleError):
            if operation=='decide':
                WorkflowService().decide(user(4),rid,{'decision':'approve','reason':'Reviewed','version':'1'})
            elif operation=='cancel':
                exchange.cancel(user(11),rid)
            else:
                exchange.reserve(user(11),request_data('insufficient',quantity=6))
        assert repo.one('SELECT status FROM requests WHERE id=?',(rid,))['status']=='Expired'
        assert repo.one('SELECT active FROM holds WHERE request_id=?',(rid,))['active']==0
        assert repo.one("SELECT COUNT(*) n FROM audit WHERE target_type='request' AND target_id=? AND action='Request expired'",(rid,))['n']==1
        assert repo.one('SELECT COUNT(*) n FROM requests')['n']==1


def test_expiry_after_collection_is_durable_audited_and_notified_once(app):
    with app.app_context():
        repo=Repository()
        rid,uid=approved()
        eid=evidence(uid)
        WorkflowService().collect(user(2),rid,{f'evidence_{uid}':str(eid),'reason':'Collected'})
        expire_request(repo,rid)
        with pytest.raises(RuleError):
            WorkflowService().receive(user(3),rid,{'version':'3','outcome':'accept',f'evidence_{uid}':str(eid)})
        rec=repo.one('SELECT status,version FROM requests WHERE id=?',(rid,))
        assert (rec['status'],rec['version'])==('Approved',4)
        assert repo.one('SELECT status FROM transfers WHERE request_id=?',(rid,))['status']=='Receipt disputed'
        assert repo.one('SELECT active FROM holds WHERE request_id=?',(rid,))['active']==1
        audit=repo.one("SELECT id FROM audit WHERE target_type='request' AND target_id=? AND action='Transfer expired in transit'",(rid,))
        recipients={row['recipient_id'] for row in repo.all('SELECT recipient_id FROM notifications WHERE audit_id=?',(audit['id'],))}
        assert {3,4,11} <= recipients
        ExchangeService().expire()
        assert repo.one('SELECT version FROM requests WHERE id=?',(rid,))['version']==4
        assert repo.one("SELECT COUNT(*) n FROM audit WHERE target_type='request' AND target_id=? AND action='Transfer expired in transit'",(rid,))['n']==1


def test_expired_uncollected_transfer_stays_expired_when_collection_is_rejected(app):
    with app.app_context():
        repo=Repository()
        rid,uid=approved()
        expire_request(repo,rid)
        with pytest.raises(RuleError):
            WorkflowService().collect(user(2),rid,{'reason':'Too late'})
        assert repo.one('SELECT status FROM requests WHERE id=?',(rid,))['status']=='Expired'
        assert repo.one('SELECT status FROM transfers WHERE request_id=?',(rid,))['status']=='Cancelled'
        assert repo.one('SELECT active FROM holds WHERE request_id=?',(rid,))['active']==0
