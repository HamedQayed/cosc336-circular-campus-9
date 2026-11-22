import re

from app.db import Repository
from app.workflow import WorkflowService
from conftest import login, post, user
from test_stage3 import approved, evidence


def forms(page):
    return re.findall(r'<form\b.*?</form>', page.get_data(as_text=True), re.S)


def test_handover_actions_match_actor_and_transfer_state(app, client):
    with app.app_context():
        rid, uid = approved()

    login(client, 11)
    assert 'Record collection' not in client.get(f'/requests/{rid}').get_data(as_text=True)
    login(client, 3)
    assert 'Accept receipt' not in client.get(f'/requests/{rid}').get_data(as_text=True)
    login(client, 2)
    assert 'Record collection' in client.get(f'/requests/{rid}').get_data(as_text=True)

    with app.app_context():
        WorkflowService().collect(user(2), rid, {'reason': 'Collected', f'evidence_{uid}': str(evidence(uid))})
    login(client, 3)
    page = client.get(f'/requests/{rid}')
    receipt_forms = forms(page)
    accept = next(form for form in receipt_forms if 'Accept receipt' in form)
    dispute = next(form for form in receipt_forms if 'Report dispute' in form)
    assert f'name="evidence_{uid}"' in accept
    assert f'name="evidence_{uid}"' not in dispute
    assert 'name="outcome" value="dispute"' in dispute

    login(client, 11)
    assert 'Record collection' not in client.get(f'/requests/{rid}').get_data(as_text=True)
    login(client, 4)
    assert 'Record physical return' not in client.get(f'/requests/{rid}').get_data(as_text=True)


def test_receiver_can_report_dispute_without_uploading_evidence(app, client):
    with app.app_context():
        rid, uid = approved()
        WorkflowService().collect(user(2), rid, {'reason': 'Collected', f'evidence_{uid}': str(evidence(uid))})
        version = Repository().one('SELECT version FROM requests WHERE id=?', (rid,))['version']
    login(client, 3)
    response = post(client, f'/requests/{rid}/handover', operation='receive', outcome='dispute',
                    version=str(version), reason='The delivered unit differs from the request')
    assert response.status_code == 302
    with app.app_context():
        assert Repository().one('SELECT status FROM transfers WHERE request_id=?', (rid,))['status'] == 'Receipt disputed'
    login(client, 4)
    assert 'Record physical return' in client.get(f'/requests/{rid}').get_data(as_text=True)
