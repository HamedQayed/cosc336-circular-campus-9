import io
import json
import time
from pathlib import Path
import pytest
from app.db import Repository
from app.domain import RuleError,now
from app.reporting import ReportService
from app.ai import AIOrchestrator,AIAdapter,AIUnavailable
from app.backup import snapshot,restore
from conftest import user,login,post
from test_stage3 import completed


class FixtureAdapter:
    """A transport fixture, never presented as a successful live AI call."""
    def suggest(self,task,context,timeout,attachment=None):
        outputs={
            'matching':lambda:{'matches':[{'unit_id':context['candidates'][0]['id'],'score':91,'reason':'Provider reason replaced by sourced facts'}]},
            'classification':lambda:{'category':'IT','tags':['monitor'],'description':'Monitor','missing':['material']},
            'advice':lambda:{'action':'reuse','reason':'Review serviceability with the responsible custodian.','missing':['repair assessment']},
            'assistant':lambda:{'answer':'The catalogue contains the listed resource.','unit_ids':[context['candidates'][0]['id']]},
            'report':lambda:{'metrics':[{'name':k,'value':v} for k,v in context['metrics'].items()],'commentary':'These synthetic records describe prototype activity. Missing evidence limits impact estimates.'}}
        return outputs[task](),'fixture-model-not-live'


@pytest.mark.parametrize('task,uid,data',[
    ('matching',11,{'need':'Display for a teaching room','category':'IT','quantity':'1'}),
    ('classification',2,{'unit_id':'7'}),('advice',2,{'unit_id':'7'}),
    ('assistant',11,{'question':'Any monitors?'}),('report',4,{})])
def test_all_ai_task_contracts_with_transport_fixture(app,task,uid,data):
    app.config['AI_ADAPTER']=FixtureAdapter()
    with app.app_context():
        result=AIOrchestrator().invoke(user(uid),task,data)
        assert result['output'] is not None and result['error'] is None
        record=Repository().one('SELECT * FROM ai_records WHERE id=?',(result['id'],))
        assert record['model']=='fixture-model-not-live' and record['review'] is None


def test_unconfigured_ai_preserves_manual_workflow(app,client):
    with app.app_context():
        result=AIOrchestrator().invoke(user(11),'matching',{'need':'Monitor','quantity':'1'})
        assert result['error'] and result['output'] is None and result['context']['candidates']
    login(client,11)
    assert client.get('/assets').status_code==200


def test_ai_rejects_false_ids_and_wrong_totals(app):
    with app.app_context():
        engine=AIOrchestrator()
        with pytest.raises(ValueError):engine.validate('matching',{'candidates':[{'id':7}]},{'matches':[{'unit_id':999,'score':99,'reason':'False'}]})
        with pytest.raises(ValueError):engine.validate('report',{'metrics':{'completed_transfers':'0'}},{'metrics':[{'name':'completed_transfers','value':'100'}],'commentary':'Wrong'})


def test_ai_private_asset_and_report_scopes(app):
    with app.app_context():
        with pytest.raises(RuleError):AIOrchestrator().invoke(user(3),'classification',{'unit_id':'7'})
        with pytest.raises(RuleError):AIOrchestrator().invoke(user(11),'report',{})
        assert 'net_savings_aed' not in ReportService().calculate(user(10),'2026-01-01','2027-01-01')['metrics']
        assert 'carbon_kg_co2e' not in ReportService().calculate(user(9),'2026-01-01','2027-01-01')['metrics']


def test_ai_transport_obeys_wall_clock_deadline(app,monkeypatch):
    def slow(*args,**kwargs):time.sleep(.15);raise RuntimeError('fixture timeout')
    monkeypatch.setattr('app.ai.requests.post',slow)
    app.config.update(OPENROUTER_API_KEY='test-fixture-not-a-key',AI_PROVIDER='openrouter',AI_MODEL='z-ai/glm-5.3-flash')
    with app.app_context():
        start=time.monotonic()
        with pytest.raises(AIUnavailable):AIAdapter().suggest('assistant',{},.02)
        assert time.monotonic()-start<.12


def test_openrouter_transport_uses_correct_endpoint_and_schema(app,monkeypatch):
    called={}
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'model':'fixture-openrouter','choices':[{'finish_reason':'stop','message':{'content':'{"answer":"I do not know","unit_ids":[]}'}}]}
    def transport(url,**kwargs):called.update(url=url,**kwargs);return Response()
    monkeypatch.setattr('app.ai.requests.post',transport)
    app.config.update(AI_PROVIDER='openrouter',OPENROUTER_API_KEY='fixture-not-a-key',AI_MODEL='z-ai/glm-5.3-flash')
    with app.app_context():
        output,model=AIAdapter().suggest('assistant',{},1)
        assert called['url']=='https://openrouter.ai/api/v1/chat/completions'
        assert called['json']['provider']['require_parameters'] is True
        assert called['json']['reasoning']['effort']=='low' and output['unit_ids']==[]


@pytest.mark.parametrize('provider,model',[('openai','z-ai/glm-5.3-flash'),('openrouter','other-model')])
def test_ai_rejects_other_providers_and_models(app,provider,model):
    app.config.update(AI_PROVIDER=provider,AI_MODEL=model,OPENROUTER_API_KEY='fixture')
    with app.app_context(), pytest.raises(AIUnavailable,match='Only OpenRouter'):
        AIAdapter().suggest('assistant',{},1)


def test_report_missing_zero_and_negative_inputs(app):
    with app.app_context():
        rid,uid=completed();service=ReportService();day=now().date().isoformat()
        metrics=service.calculate(user(4),day,day)['metrics']
        assert metrics['net_savings_aed']=='Unavailable' and metrics['diversion_rate_percent']=='Not applicable'
        service.save_inputs(user(9),{'unit_id':str(uid),'source':'Synthetic known purchase case','replacement':'100','transfer':'150','repair':'0','refurbishment':'0'})
        service.save_inputs(user(10),{'unit_id':str(uid),'source':'Synthetic scenario factors','replacement_co2':'10','reuse_co2':'15'})
        metrics=service.calculate(user(4),day,day)['metrics']
        assert metrics['net_savings_aed']=='-50.00' and metrics['carbon_kg_co2e']=='-5.00'
        assert metrics['finance_coverage']=='1/1' and metrics['unique_reused_units']=='1'


def test_diversion_counts_each_disposed_unit_once(app):
    with app.app_context():
        repo=Repository();day=now().date().isoformat()
        for action in ('Donated','Recycled'):
            repo.write("INSERT INTO dispositions(unit_id,proposer_id,action,status,reason,created_at,completed_at) VALUES(1,2,?,'Executed','fixture',?,?)",(action,day,day))
        assert ReportService().calculate(user(4),day,day)['metrics']['diversion_rate_percent']=='100.00'


def test_csv_export_is_authorized_and_real_table(app,client):
    with app.app_context():completed()
    login(client,11);assert client.get('/reports.csv').status_code==403
    login(client,4);response=client.get('/reports.csv')
    assert response.status_code==200 and b'transferred_units' in response.data and b'Completed' in response.data


def test_backup_restores_database_and_evidence_to_isolated_location(app,tmp_path):
    from test_stage3 import evidence
    with app.app_context():
        evidence(1);snapshot(tmp_path/'snapshot');restore(tmp_path/'snapshot',tmp_path/'restore')
        assert (tmp_path/'restore'/'campus.sqlite').exists()
        assert len(list((tmp_path/'restore'/'evidence').iterdir()))==1
        from click import ClickException
        with pytest.raises(ClickException):restore(tmp_path/'snapshot',Path(app.config['DATABASE']).parent)
        with pytest.raises(ClickException):snapshot(Path(app.config['EVIDENCE_DIR'])/'nested')
        assert not (Path(app.config['EVIDENCE_DIR'])/'nested').exists()
        (tmp_path/'snapshot'/'campus.sqlite').write_bytes(b'tampered')
        with pytest.raises(ClickException):restore(tmp_path/'snapshot',tmp_path/'bad-restore')


@pytest.mark.parametrize('uid,path',[(11,'/requests/new'),(2,'/assets/new'),(2,'/assets/mine'),(2,'/assets/1'),(2,'/assets/1/lifecycle'),(4,'/approvals'),(4,'/reports'),(4,'/audit'),(11,'/ai'),(5,'/accounts')])
def test_main_pages_render_for_authorized_roles(client,uid,path):
    login(client,uid);assert client.get(path).status_code==200
