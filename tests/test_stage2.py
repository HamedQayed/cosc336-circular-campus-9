import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from app.db import Repository
from app.domain import RuleError,now
from app.assets import AssetService,EvidenceService
from app.exchange import ExchangeService
from conftest import login,post,user


def request_data(key='unique-key',quantity=1):
    return {'purpose':'Equip the Business teaching room','quantity':str(quantity),'needed_date':(now().date()+timedelta(days=2)).isoformat(),
            'destination_dept_id':'2','destination_custodian_id':'3','destination_location':'Business 101','category':'IT','urgency':'Normal','listing_id':'2','request_key':key}


def test_request_reserves_without_changing_owner(app):
    with app.app_context():
        rid=ExchangeService().reserve(user(11),request_data())
        repo=Repository();assert repo.one('SELECT COUNT(*) n FROM holds WHERE active=1')['n']==1
        uid=repo.one('SELECT unit_id FROM holds WHERE request_id=?',(rid,))['unit_id']
        assert repo.one('SELECT owner_dept_id FROM units WHERE id=?',(uid,))['owner_dept_id']==1


def test_duplicate_request_returns_same_result(app):
    with app.app_context():
        service=ExchangeService();assert service.reserve(user(11),request_data())==service.reserve(user(11),request_data())
        assert Repository().one('SELECT COUNT(*) n FROM requests')['n']==1


def test_atomic_insufficient_quantity_and_required_specs(app):
    with app.app_context():
        for data in [request_data(quantity=6),{**request_data(),'specifications':'4K'}]:
            with pytest.raises(RuleError):ExchangeService().reserve(user(11),data)
        assert Repository().one('SELECT COUNT(*) n FROM holds')['n']==0


def test_final_unit_race_has_one_winner(app):
    with app.app_context():Repository().write("UPDATE units SET publication='Draft' WHERE listing_id=2 AND id<>7")
    def reserve(key):
        with app.app_context():
            try:ExchangeService().reserve(user(11),request_data(key));return 'saved'
            except RuleError:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,['race-a','race-b']))
    assert sorted(results)==['conflict','saved']
    with app.app_context():assert Repository().one('SELECT COUNT(*) n FROM holds WHERE active=1')['n']==1


def test_creator_cancel_releases_hold_once(app):
    with app.app_context():
        service=ExchangeService();rid=service.reserve(user(11),request_data());service.cancel(user(11),rid)
        with pytest.raises(RuleError):service.cancel(user(11),rid)
        assert Repository().one('SELECT COUNT(*) n FROM holds WHERE active=1')['n']==0


def test_expiry_and_seeking_without_hold(app):
    with app.app_context():
        service=ExchangeService();rid=service.reserve(user(11),request_data())
        Repository().write("UPDATE requests SET expires_at='2000-01-01T00:00:00+04:00' WHERE id=?",(rid,));service.expire()
        assert Repository().one('SELECT status FROM requests WHERE id=?',(rid,))['status']=='Expired'
        seeking=service.reserve(user(11),{**request_data('seeking'),'listing_id':''})
        assert Repository().one('SELECT status,expires_at FROM requests WHERE id=?',(seeking,))['expires_at'] is None


def test_invalid_quantity_and_cross_department_denied(app):
    with app.app_context():
        for data in [{**request_data(),'quantity':'-1'},{**request_data(),'destination_dept_id':'1'}]:
            with pytest.raises(RuleError):ExchangeService().reserve(user(11),data)


def test_register_requires_custodian_and_starts_draft(app):
    data={'name':'Test chair','description':'Synthetic chair','category':'Furniture','condition':'Good','location':'Store','quantity':'2','value':''}
    with app.app_context():
        with pytest.raises(RuleError):AssetService().create(user(11),data)
        lid=AssetService().create(user(2),data)
        assert len(Repository().all("SELECT id FROM units WHERE listing_id=? AND publication='Draft'",(lid,)))==2


def test_reviewed_metadata_edit_preserves_safety_and_rejects_stale_version(app):
    with app.app_context():
        repo=Repository();repo.write("UPDATE units SET publication='Draft' WHERE listing_id=1")
        repo.write("UPDATE units SET serviceability='Quarantined' WHERE id=1")
        data={'version':'1','name':'Reviewed chair','description':'Corrected metadata','specifications':'Adjustable',
              'category':'Furniture','condition':'Good','location':'Checked store','value':'300','reason':'Custodian reviewed classification'}
        AssetService().edit(user(2),1,data)
        assert repo.one('SELECT serviceability FROM units WHERE id=1')['serviceability']=='Quarantined'
        with pytest.raises(RuleError):AssetService().edit(user(2),1,data)


def test_forged_evidence_file_is_rejected(app):
    from werkzeug.datastructures import FileStorage
    with app.app_context(),pytest.raises(RuleError):
        EvidenceService().upload(user(2),1,FileStorage(stream=io.BytesIO(b'not a png'),filename='test.png'))


def test_catalogue_filters_and_private_requests(app,client):
    login(client,11)
    page=client.get('/assets?category=IT&q=monitor')
    assert page.status_code==200 and b'Dell' in page.data and b'Ergonomic office chair' not in page.data
    with app.app_context():rid=ExchangeService().reserve(user(11),request_data())
    login(client,1);assert client.get(f'/requests/{rid}').status_code==403


def test_draft_edit_cannot_change_published_sibling_metadata(app):
    with app.app_context():
        repo=Repository()
        repo.write("UPDATE units SET publication='Draft' WHERE id=1")
        before=repo.one('SELECT name FROM listings WHERE id=1')['name']
        data={'version':'1','name':'Unreviewed replacement','description':'Changed description',
              'specifications':'Changed specs','category':'Furniture','condition':'Good',
              'location':'Store','value':'300','reason':'Draft correction'}
        with pytest.raises(RuleError):
            AssetService().edit(user(2),1,data)
        assert repo.one('SELECT name FROM listings WHERE id=1')['name']==before
        assert repo.one('SELECT version FROM units WHERE id=1')['version']==1


def test_edit_invalidates_stale_form_for_draft_sibling(app):
    with app.app_context():
        repo=Repository();repo.write("UPDATE units SET publication='Draft' WHERE listing_id=1")
        data={'version':'1','name':'Reviewed listing','description':'Reviewed description',
              'specifications':'Adjustable','category':'Furniture','condition':'Good',
              'location':'Store','value':'300','reason':'Correction'}
        AssetService().edit(user(2),1,data)
        with pytest.raises(RuleError):
            AssetService().edit(user(2),2,{**data,'name':'Stale replacement'})
        assert repo.one('SELECT name FROM listings WHERE id=1')['name']=='Reviewed listing'


def test_request_options_do_not_expose_private_draft_listings(app,client):
    with app.app_context():
        AssetService().create(user(2),{'name':'Private draft inventory','description':'Internal only',
            'category':'IT','condition':'Good','location':'Store','quantity':'1','value':''})
    login(client,11)
    response=client.get('/requests/new')
    assert response.status_code==200
    assert b'Private draft inventory' not in response.data
    assert b'Dell' in response.data


def test_evidence_rechecks_custody_after_reading_upload(app):
    from PIL import Image
    from werkzeug.datastructures import FileStorage
    raw=io.BytesIO();Image.new('RGB',(1,1)).save(raw,format='PNG')
    class TransferredDuringRead(io.BytesIO):
        def read(self,*args):
            Repository().write('UPDATE units SET custodian_id=3,owner_dept_id=2 WHERE id=1')
            return super().read(*args)
    with app.app_context():
        file=FileStorage(stream=TransferredDuringRead(raw.getvalue()),filename='evidence.png')
        with pytest.raises(RuleError):
            EvidenceService().upload(user(2),1,file)
        assert Repository().one('SELECT COUNT(*) n FROM evidence')['n']==0
