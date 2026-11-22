import io
import pytest
from werkzeug.datastructures import FileStorage
from PIL import Image
from app.db import Repository
from app.domain import RuleError
from app.assets import AssetService,EvidenceService
from app.exchange import ExchangeService
from app.workflow import WorkflowService,LifecycleService
from conftest import user,login
from test_stage2 import request_data


def evidence(uid,actor=2):
    stream=io.BytesIO();Image.new('RGB',(8,8),'white').save(stream,'PNG');stream.seek(0)
    return EvidenceService().upload(user(actor),uid,FileStorage(stream=stream,filename='synthetic-evidence.png'))


def approved():
    rid=ExchangeService().reserve(user(11),request_data())
    WorkflowService().decide(user(4),rid,{'decision':'approve','reason':'Synthetic teaching need reviewed','version':'1'})
    uid=Repository().one('SELECT unit_id FROM holds WHERE request_id=?',(rid,))['unit_id']
    return rid,uid


def completed():
    rid,uid=approved();eid=evidence(uid)
    WorkflowService().collect(user(2),rid,{f'evidence_{uid}':str(eid),'reason':'Collection verified'})
    eid=evidence(uid,3)
    WorkflowService().receive(user(3),rid,{'version':'3','outcome':'accept',f'evidence_{uid}':str(eid)})
    return rid,uid


def test_approval_keeps_single_hold_and_owner(app):
    with app.app_context():
        rid,uid=approved();repo=Repository()
        assert repo.one('SELECT owner_dept_id FROM units WHERE id=?',(uid,))['owner_dept_id']==1
        assert repo.one('SELECT COUNT(*) n FROM holds WHERE request_id=? AND active=1',(rid,))['n']==1


def test_receipt_changes_owner_once(app):
    with app.app_context():
        rid,uid=completed();repo=Repository()
        WorkflowService().receive(user(3),rid,{})
        unit=repo.one('SELECT * FROM units WHERE id=?',(uid,))
        assert (unit['owner_dept_id'],unit['custodian_id'],unit['publication'])==(2,3,'Draft')
        assert repo.one("SELECT COUNT(*) n FROM events WHERE unit_id=? AND action='Received'",(uid,))['n']==1
        assert repo.one('SELECT COUNT(*) n FROM holds WHERE active=1')['n']==0


def test_receipt_before_collection_and_wrong_receiver_denied(app):
    with app.app_context():
        rid,uid=approved()
        with pytest.raises(RuleError):WorkflowService().receive(user(3),rid,{'version':'2','outcome':'accept'})
        with pytest.raises(RuleError):WorkflowService().receive(user(2),rid,{})


def test_no_self_approval_or_system_admin_business_power(app):
    with app.app_context():
        rid=ExchangeService().reserve(user(11),request_data())
        with pytest.raises(RuleError):WorkflowService().decide(user(5),rid,{'decision':'approve','reason':'No','version':'1'})
        Repository().write("UPDATE users SET role='workflow_admin' WHERE id=11")
        with pytest.raises(RuleError):WorkflowService().decide(user(11),rid,{'decision':'approve','reason':'No','version':'1'})


def test_rejection_frees_stock_and_stale_approval_denied(app):
    with app.app_context():
        rid=ExchangeService().reserve(user(11),request_data())
        with pytest.raises(RuleError):WorkflowService().decide(user(4),rid,{'decision':'approve','reason':'Stale','version':'9'})
        WorkflowService().decide(user(4),rid,{'decision':'reject','reason':'No operational need','version':'1'})
        assert Repository().one('SELECT COUNT(*) n FROM holds WHERE active=1')['n']==0


def test_expired_in_transit_stock_stays_blocked_until_evidenced_return(app):
    with app.app_context():
        rid,uid=approved();eid=evidence(uid)
        WorkflowService().collect(user(2),rid,{f'evidence_{uid}':str(eid),'reason':'Collected'})
        Repository().write("UPDATE requests SET expires_at='2000-01-01T00:00:00+04:00' WHERE id=?",(rid,))
        ExchangeService().expire()
        assert Repository().one('SELECT status FROM transfers WHERE request_id=?',(rid,))['status']=='Receipt disputed'
        assert Repository().one('SELECT active FROM holds WHERE request_id=?',(rid,))['active']==1
        with pytest.raises(RuleError):ExchangeService().cancel(user(4),rid)
        WorkflowService().resolve(user(4),rid,{f'evidence_{uid}':str(eid),'reason':'Physical return checked against evidence'})
        assert Repository().one('SELECT active FROM holds WHERE request_id=?',(rid,))['active']==0


def test_mult_unit_receipt_failure_rolls_back_everything(app):
    with app.app_context():
        rid=ExchangeService().reserve(user(11),request_data(quantity=2));service=WorkflowService()
        service.decide(user(4),rid,{'decision':'approve','reason':'Reviewed','version':'1'})
        units=Repository().all('SELECT unit_id FROM holds WHERE request_id=?',(rid,));collection={'reason':'Collected'}
        for u in units:collection['evidence_'+str(u['unit_id'])]=str(evidence(u['unit_id']))
        service.collect(user(2),rid,collection)
        data={'version':'3','outcome':'accept','evidence_'+str(units[0]['unit_id']):str(evidence(units[0]['unit_id'],3))}
        with pytest.raises(RuleError):service.receive(user(3),rid,data)
        assert Repository().one('SELECT COUNT(*) n FROM units WHERE owner_dept_id=2')['n']==0
        assert Repository().one("SELECT COUNT(*) n FROM transfers WHERE status='Completed'")['n']==0


def test_maintenance_requires_authorized_repair_and_clearance(app):
    with app.app_context():
        service=LifecycleService();service.maintain(user(2),1,{'operation':'new_job','assignee_id':'7','reason':'Loose chair leg'})
        common={'operation':'job','job_id':'1','reason':'Synthetic service record'}
        for state in ['Inspection requested','Inspected']:
            service.maintain(user(7),1,{**common,'target':state})
        with pytest.raises(RuleError):service.maintain(user(7),1,{**common,'target':'Repair approved'})
        service.maintain(user(2),1,{**common,'target':'Repair approved'})
        service.maintain(user(7),1,{**common,'target':'In progress'})
        eid=evidence(1,7)
        for state in ['Completed','Closed']:
            service.maintain(user(7),1,{**common,'target':state,'evidence_id':str(eid),'cost':'20.00','condition':'Good'})
        assert Repository().one('SELECT serviceability FROM units WHERE id=1')['serviceability']=='Quarantined'
        service.inspect(user(2),1,{'evidence_id':str(eid),'condition':'Good','reason':'Human inspection complete'})
        assert Repository().one('SELECT serviceability FROM units WHERE id=1')['serviceability']=='Serviceable'


def test_disposition_blocks_holds_and_requires_approval_evidence(app):
    with app.app_context():
        rid,uid=approved();service=LifecycleService()
        with pytest.raises(RuleError):service.disposition(user(2),uid,{'operation':'propose_disposition','action':'Recycled','reason':'No longer useful'})
        service.disposition(user(2),1,{'operation':'propose_disposition','action':'Recycled','reason':'Synthetic worn unit'})
        with pytest.raises(RuleError):service.disposition(user(2),1,{'operation':'execute_disposition','disposition_id':'1','reason':'Attempt'})
        service.disposition(user(4),1,{'operation':'decide_disposition','disposition_id':'1','decision':'approve','reason':'Evidence reviewed'})
        eid=evidence(1)
        service.disposition(user(2),1,{'operation':'execute_disposition','disposition_id':'1','reason':'Campus partner receipt','evidence_id':str(eid)})
        assert Repository().one('SELECT lifecycle FROM units WHERE id=1')['lifecycle']=='Recycled'


def test_disposition_rejects_open_maintenance(app):
    with app.app_context():
        service=LifecycleService()
        service.maintain(user(2),1,{'operation':'new_job','assignee_id':'7','reason':'Repair required'})
        with pytest.raises(RuleError,match='open service jobs'):
            service.disposition(user(2),1,{'operation':'propose_disposition','action':'Recycled','reason':'Worn'})
        assert Repository().one('SELECT lifecycle FROM units WHERE id=1')['lifecycle']=='Active'
        assert Repository().one('SELECT COUNT(*) n FROM dispositions')['n']==0


def test_inspection_cannot_invalidate_held_unit(app):
    with app.app_context():
        rid,uid=approved();repo=Repository();eid=evidence(uid)
        with pytest.raises(RuleError,match='active requests'):
            LifecycleService().inspect(user(2),uid,{'evidence_id':str(eid),'condition':'Good','reason':'Inspection'})
        assert repo.one('SELECT publication FROM units WHERE id=?',(uid,))['publication']=='Published'
        assert repo.one('SELECT active FROM holds WHERE request_id=?',(rid,))['active']==1


def test_dispute_invalidates_stale_receipt_form(app):
    with app.app_context():
        rid,uid=approved();service=WorkflowService()
        service.collect(user(2),rid,{'reason':'Collected',f'evidence_{uid}':str(evidence(uid))})
        service.receive(user(3),rid,{'version':'3','outcome':'dispute','reason':'Wrong item'})
        with pytest.raises(RuleError,match='changed'):
            service.receive(user(3),rid,{'version':'3','outcome':'accept',f'evidence_{uid}':str(evidence(uid,3))})
        assert Repository().one('SELECT status FROM transfers WHERE request_id=?',(rid,))['status']=='Receipt disputed'


def test_evidence_download_scope_includes_receiver_only_after_approval(app,client):
    with app.app_context():eid=evidence(7)
    login(client,3);assert client.get(f'/evidence/{eid}').status_code==403
    with app.app_context():approved()
    assert client.get(f'/evidence/{eid}').status_code==200
    login(client,11);assert client.get(f'/evidence/{eid}').status_code==403
