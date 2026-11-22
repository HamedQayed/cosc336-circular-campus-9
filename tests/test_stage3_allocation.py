import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.assets import EvidenceService
from app.db import Repository
from app.domain import RuleError
from app.exchange import ExchangeService
from app.workflow import WorkflowService
from conftest import user
from test_stage2 import request_data


def add_second_source_custodian(repo):
    repo.write("INSERT INTO users(id,username,name,password_hash,role,department_id,active) "
               "SELECT 12,'custodian_alt','Second source custodian',password_hash,"
               "'custodian',department_id,1 FROM users WHERE id=2")


def test_allocation_rejects_split_stock_without_partial_holds(app):
    with app.app_context():
        repo=Repository()
        add_second_source_custodian(repo)
        repo.write("UPDATE units SET publication='Draft' WHERE listing_id=2 AND id NOT IN (7,8)")
        repo.write('UPDATE units SET custodian_id=12 WHERE id=8')
        with pytest.raises(RuleError,match='single source custodian'):
            ExchangeService().reserve(user(11),request_data(quantity=2))
        assert repo.one('SELECT COUNT(*) n FROM requests')['n']==0
        assert repo.one('SELECT COUNT(*) n FROM holds')['n']==0


def test_allocation_chooses_source_with_enough_stock_for_collectable_handover(app):
    with app.app_context():
        repo=Repository()
        add_second_source_custodian(repo)
        repo.write("UPDATE units SET publication='Draft' WHERE listing_id=2 AND id IN (10,11)")
        repo.write('UPDATE units SET custodian_id=12 WHERE id IN (8,9)')
        rid=ExchangeService().reserve(user(11),request_data(quantity=2))
        rows=repo.all('SELECT u.id,u.custodian_id FROM units u JOIN holds h ON h.unit_id=u.id WHERE h.request_id=? ORDER BY u.id',(rid,))
        assert [(row['id'],row['custodian_id']) for row in rows]==[(8,12),(9,12)]
        workflow=WorkflowService()
        workflow.decide(user(4),rid,{'decision':'approve','reason':'Reviewed','version':'1'})
        collection={'reason':'Collected'}
        for row in rows:
            stream=io.BytesIO()
            Image.new('RGB',(2,2),'white').save(stream,'PNG')
            stream.seek(0)
            evidence_id=EvidenceService().upload(user(12),row['id'],FileStorage(stream=stream,filename='collection.png'))
            collection['evidence_'+str(row['id'])]=str(evidence_id)
        workflow.collect(user(12),rid,collection)
        assert repo.one("SELECT COUNT(*) n FROM transfers WHERE request_id=? AND status='Awaiting receipt'",(rid,))['n']==2
