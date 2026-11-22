from datetime import datetime, time
from zoneinfo import ZoneInfo
from flask import Blueprint, g, request, render_template, redirect, url_for, flash
from .db import Repository, transaction
from .domain import RuleError, ResourceRequest, Transfer, MaintenanceJob, CONDITIONS, stamp
from .forms import text, integer, choice, money
from .security import Policy, signed_in
from .exchange import ExchangeService, expiring_transaction

bp=Blueprint('workflow',__name__)


def evidence_for(repo,eid,uid):
    return repo.one('SELECT * FROM evidence WHERE id=? AND unit_id=?',(eid,uid))


class WorkflowService:
    def release(self,actor,uid,data):
        Policy().require(actor,'workflow_admin')
        repo=Repository()
        decision=choice(data,'decision',('approve','reject'))
        reason=text(data,'reason')
        with transaction():
            unit=repo.one('SELECT u.*,l.creator_id FROM units u JOIN listings l ON l.id=u.listing_id WHERE u.id=?',(uid,))
            if actor['id'] in (unit['custodian_id'],unit['creator_id']):
                raise RuleError('Self-approval is forbidden.',403)
            if unit['publication']!='Release pending':
                raise RuleError('This unit is not awaiting release.',409)
            if decision=='approve' and (unit['serviceability']!='Serviceable' or unit['lifecycle']!='Active'):
                raise RuleError('Only a serviceable active unit can be published.',409)
            publication='Published' if decision=='approve' else 'Draft'
            repo.write('UPDATE units SET publication=?,version=version+1 WHERE id=?',(publication,uid))
            repo.write('INSERT INTO approvals(kind,target_id,actor_id,decision,reason,created_at) VALUES(?,?,?,?,?,?)',('release',uid,actor['id'],decision,reason,stamp()))
            repo.life(actor,uid,'Published' if publication=='Published' else 'Release rejected',reason)
            repo.event(actor,'unit',uid,'Release '+decision,reason,[unit['custodian_id']])

    def decide(self,actor,rid,data):
        Policy().require(actor,'workflow_admin')
        repo=Repository()
        decision=choice(data,'decision',('approve','reject'))
        reason=text(data,'reason')
        with expiring_transaction():
            rec=repo.one('SELECT * FROM requests WHERE id=?',(rid,))
            if actor['id']==rec['creator_id']:
                raise RuleError('You cannot approve your own request.',403)
            ResourceRequest(rid,rec['status']).require('Pending')
            if integer(data,'version')!=rec['version']:
                raise RuleError('This request changed. Reload it before deciding.',409)
            units=repo.all('SELECT u.* FROM units u JOIN holds h ON h.unit_id=u.id WHERE request_id=? AND active=1',(rid,))
            if decision=='approve':
                if len(units)!=rec['quantity'] or any(u['serviceability']!='Serviceable' or u['lifecycle']!='Active' or u['publication']!='Published' for u in units):
                    raise RuleError('The held units are no longer eligible.',409)
                expiry=datetime.combine(datetime.fromisoformat(rec['needed_date']).date(),time.max,ZoneInfo('Asia/Dubai')).isoformat(timespec='seconds')
                repo.write("UPDATE requests SET status='Approved',decision_reason=?,expires_at=?,version=version+1 WHERE id=?",(reason,expiry,rid))
                for unit in units:
                    repo.write('INSERT INTO transfers(request_id,unit_id,source_dept_id,source_custodian_id,source_location) VALUES(?,?,?,?,?)',
                               (rid,unit['id'],unit['owner_dept_id'],unit['custodian_id'],unit['location']))
                    repo.life(actor,unit['id'],'Transfer approved',reason)
            else:
                repo.write("UPDATE requests SET status='Rejected',decision_reason=?,version=version+1 WHERE id=?",(reason,rid))
                repo.write('UPDATE holds SET active=0 WHERE request_id=?',(rid,))
            repo.write('INSERT INTO approvals(kind,target_id,actor_id,decision,reason,created_at) VALUES(?,?,?,?,?,?)',('request',rid,actor['id'],decision,reason,stamp()))
            repo.event(actor,'request',rid,'Request '+decision,reason,[rec['creator_id'],rec['destination_custodian_id']]+[u['custodian_id'] for u in units])

    def collect(self,actor,rid,data):
        Policy().require(actor,'custodian')
        repo=Repository()
        with expiring_transaction():
            rec=repo.one('SELECT * FROM requests WHERE id=?',(rid,))
            ResourceRequest(rid,rec['status']).require('Approved')
            transfers=repo.all('SELECT t.*,u.serviceability,u.lifecycle FROM transfers t JOIN units u ON u.id=t.unit_id WHERE request_id=?',(rid,))
            if not transfers or any(t['source_custodian_id']!=actor['id'] for t in transfers):
                raise RuleError('Only the source custodian can record collection.',403)
            if all(t['status']=='Awaiting receipt' for t in transfers):
                return
            note=text(data,'reason')
            for transfer in transfers:
                Transfer(transfer['status']).collect()
                if transfer['serviceability']!='Serviceable' or transfer['lifecycle']!='Active':
                    raise RuleError('A blocked unit cannot be collected.',409)
                eid=integer(data,'evidence_'+str(transfer['unit_id']))
                evidence_for(repo,eid,transfer['unit_id'])
                repo.write("UPDATE transfers SET status='Awaiting receipt',collection_evidence_id=? WHERE id=?",(eid,transfer['id']))
                repo.life(actor,transfer['unit_id'],'Collected',note)
            repo.write('UPDATE requests SET version=version+1 WHERE id=?',(rid,))
            repo.event(actor,'request',rid,'Collection recorded',note,[rec['creator_id'],rec['destination_custodian_id']])

    def receive(self,actor,rid,data):
        Policy().require(actor,'custodian')
        repo=Repository()
        with expiring_transaction():
            rec=repo.one('SELECT * FROM requests WHERE id=?',(rid,))
            if rec['destination_custodian_id']!=actor['id']:
                raise RuleError('Only the designated receiving custodian may acknowledge receipt.',403)
            if rec['status']=='Completed':
                return
            ResourceRequest(rid,rec['status']).require('Approved')
            transfers=repo.all('SELECT t.*,u.serviceability,u.lifecycle FROM transfers t JOIN units u ON u.id=t.unit_id WHERE request_id=?',(rid,))
            if integer(data,'version')!=rec['version']:
                raise RuleError('The transfer changed. Reload before confirming receipt.',409)
            if choice(data,'outcome',('accept','dispute'))=='dispute':
                if not transfers or any(t['status'] not in ('Awaiting receipt','Receipt disputed') for t in transfers):
                    raise RuleError('Collection must be recorded before raising a receipt dispute.',409)
                repo.write("UPDATE transfers SET status='Receipt disputed' WHERE request_id=?",(rid,))
                repo.write('UPDATE requests SET version=version+1 WHERE id=?',(rid,))
                reason=text(data,'reason')
                repo.event(actor,'request',rid,'Receipt disputed',reason,repo.role_users('workflow_admin'))
                return
            if len(transfers)!=rec['quantity']:
                raise RuleError('All approved units must be received together.',409)
            for transfer in transfers:
                Transfer(transfer['status']).acknowledge()
                if transfer['serviceability']!='Serviceable' or transfer['lifecycle']!='Active':
                    raise RuleError('A blocked unit requires dispute resolution.',409)
                eid=integer(data,'evidence_'+str(transfer['unit_id']))
                evidence_for(repo,eid,transfer['unit_id'])
                repo.write("UPDATE units SET owner_dept_id=?,custodian_id=?,location=?,publication='Draft',version=version+1 WHERE id=?",(rec['destination_dept_id'],actor['id'],rec['destination_location'],transfer['unit_id']))
                repo.write("UPDATE transfers SET status='Completed',receipt_evidence_id=?,completed_at=? WHERE id=?",(eid,stamp(),transfer['id']))
                repo.life(actor,transfer['unit_id'],'Received',f'Request {rid}; owner, custody and location updated')
            repo.write("UPDATE requests SET status='Completed',version=version+1 WHERE id=?",(rid,))
            repo.write('UPDATE holds SET active=0 WHERE request_id=?',(rid,))
            repo.event(actor,'request',rid,'Receipt completed',f'All {len(transfers)} units received',[rec['creator_id']]+[t['source_custodian_id'] for t in transfers])

    def resolve(self,actor,rid,data):
        Policy().require(actor,'workflow_admin')
        repo=Repository()
        with transaction():
            rec=repo.one('SELECT * FROM requests WHERE id=?',(rid,))
            ResourceRequest(rid,rec['status']).require('Approved')
            transfers=repo.all('SELECT * FROM transfers WHERE request_id=?',(rid,))
            if not transfers or any(t['status']!='Receipt disputed' for t in transfers):
                raise RuleError('Only a disputed transfer may be resolved.',409)
            reason=text(data,'reason')
            for transfer in transfers:
                eid=integer(data,'evidence_'+str(transfer['unit_id']))
                evidence_for(repo,eid,transfer['unit_id'])
                repo.write("UPDATE transfers SET status='Cancelled after return',receipt_evidence_id=? WHERE id=?",(eid,transfer['id']))
                repo.life(actor,transfer['unit_id'],'Returned after dispute',reason)
            repo.write("UPDATE requests SET status='Cancelled',version=version+1 WHERE id=?",(rid,))
            repo.write('UPDATE holds SET active=0 WHERE request_id=?',(rid,))
            repo.event(actor,'request',rid,'Dispute resolved by physical return',reason,[rec['creator_id'],rec['destination_custodian_id']])


class LifecycleService:
    def maintain(self,actor,uid,data):
        repo=Repository()
        with transaction():
            unit=repo.one('SELECT * FROM units WHERE id=?',(uid,))
            Policy().unit(actor,unit)
            op=data.get('operation')
            if op=='new_job':
                Policy().require(actor,'custodian')
                Policy().unit(actor,unit,True)
                if repo.all('SELECT id FROM holds WHERE unit_id=? AND active=1',(uid,)):
                    raise RuleError('Resolve or cancel active requests before starting service.',409)
                if unit['lifecycle']!='Active' or repo.all("SELECT id FROM maintenance WHERE unit_id=? AND status<>'Closed'",(uid,)):
                    raise RuleError('The unit must be active and have no open service job.',409)
                assignee=repo.one("SELECT * FROM users WHERE id=? AND role='maintenance' AND active=1 AND department_id=?",(integer(data,'assignee_id'),unit['owner_dept_id']))
                mid=repo.write("INSERT INTO maintenance(unit_id,assignee_id,status,description,created_at) VALUES(?,?,'Reported',?,?)",(uid,assignee['id'],text(data,'reason'),stamp())).lastrowid
                repo.write("UPDATE units SET serviceability='Under service',publication='Draft',version=version+1 WHERE id=?",(uid,))
                repo.life(actor,uid,'Service reported',text(data,'reason'))
                repo.event(actor,'unit',uid,'Maintenance assigned',f'Job {mid}',[assignee['id']])
                return
            job=repo.one('SELECT * FROM maintenance WHERE id=? AND unit_id=?',(integer(data,'job_id'),uid))
            target=text(data,'target',50)
            MaintenanceJob(job['status']).next_state(target)
            if target=='Repair approved':
                Policy().require(actor,'custodian');Policy().unit(actor,unit,True)
            elif actor['role']!='maintenance' or job['assignee_id']!=actor['id']:
                raise RuleError('Only the assigned maintenance user can update this job.',403)
            reason=text(data,'reason')
            eid=None;cost=None
            if target in ('Completed','Closed'):
                eid=integer(data,'evidence_id');evidence_for(repo,eid,uid)
                cost=money(data,'cost')
            repo.write('UPDATE maintenance SET status=?,outcome=?,cost_cents=COALESCE(?,cost_cents),evidence_id=COALESCE(?,evidence_id),completed_at=CASE WHEN ?=\'Closed\' THEN ? ELSE completed_at END WHERE id=?',
                       (target,reason,cost,eid,target,stamp(),job['id']))
            if target=='Closed':
                condition=choice(data,'condition',CONDITIONS)
                repo.write("UPDATE units SET condition=?,serviceability='Quarantined',version=version+1 WHERE id=?",(condition,uid))
            repo.life(actor,uid,'Maintenance '+target,reason,cost)
            repo.event(actor,'unit',uid,'Maintenance '+target,reason,[unit['custodian_id'],job['assignee_id']])

    def inspect(self,actor,uid,data):
        Policy().require(actor,'custodian')
        repo=Repository()
        with transaction():
            unit=repo.one('SELECT * FROM units WHERE id=?',(uid,));Policy().unit(actor,unit,True)
            if unit['lifecycle']!='Active' or repo.all("SELECT id FROM maintenance WHERE unit_id=? AND status<>'Closed'",(uid,)):
                raise RuleError('Complete service before recording inspection clearance.',409)
            if repo.all('SELECT id FROM holds WHERE unit_id=? AND active=1',(uid,)):
                raise RuleError('Resolve or cancel active requests before inspection clearance.',409)
            eid=integer(data,'evidence_id');evidence_for(repo,eid,uid)
            condition=choice(data,'condition',('New','Good','Fair','Poor'))
            repo.write("UPDATE units SET condition=?,serviceability='Serviceable',publication='Draft',version=version+1 WHERE id=?",(condition,uid))
            repo.life(actor,uid,'Inspection clearance',text(data,'reason')+f'; evidence {eid}')
            repo.event(actor,'unit',uid,'Inspection clearance',f'Evidence {eid}',[actor['id']])

    def disposition(self,actor,uid,data):
        repo=Repository()
        with transaction():
            unit=repo.one('SELECT * FROM units WHERE id=?',(uid,))
            if repo.all('SELECT id FROM holds WHERE unit_id=? AND active=1',(uid,)):
                raise RuleError('A held or allocated unit cannot enter disposition.',409)
            op=data.get('operation')
            reason=text(data,'reason')
            if op=='propose_disposition':
                Policy().require(actor,'custodian');Policy().unit(actor,unit,True)
                if unit['lifecycle']!='Active':
                    raise RuleError('Only an active unit can enter retirement.',409)
                if repo.all("SELECT id FROM maintenance WHERE unit_id=? AND status<>'Closed'",(uid,)):
                    raise RuleError('Complete open service jobs before disposition.',409)
                action=choice(data,'action',('Donated','Recycled','Disposed'))
                did=repo.write('INSERT INTO dispositions(unit_id,proposer_id,action,reason,created_at) VALUES(?,?,?,?,?)',(uid,actor['id'],action,reason,stamp())).lastrowid
                repo.write("UPDATE units SET lifecycle='Retired',version=version+1 WHERE id=?",(uid,))
                repo.life(actor,uid,'Disposition proposed',action+': '+reason)
                repo.event(actor,'unit',uid,'Disposition proposed',f'Case {did}',repo.role_users('workflow_admin'))
                return
            case=repo.one('SELECT * FROM dispositions WHERE id=? AND unit_id=?',(integer(data,'disposition_id'),uid))
            if op=='decide_disposition':
                Policy().require(actor,'workflow_admin')
                if case['proposer_id']==actor['id']:
                    raise RuleError('Self-approval is forbidden.',403)
                if case['status']!='Pending':
                    raise RuleError('This case is no longer pending.',409)
                decision=choice(data,'decision',('approve','reject'))
                repo.write('UPDATE dispositions SET status=? WHERE id=?',('Approved' if decision=='approve' else 'Rejected',case['id']))
                if decision=='reject':
                    repo.write("UPDATE units SET lifecycle='Active',version=version+1 WHERE id=?",(uid,))
                repo.write('INSERT INTO approvals(kind,target_id,actor_id,decision,reason,created_at) VALUES(?,?,?,?,?,?)',('disposition',case['id'],actor['id'],decision,reason,stamp()))
                repo.event(actor,'unit',uid,'Disposition '+decision,reason,[case['proposer_id']])
                return
            Policy().require(actor,'custodian');Policy().unit(actor,unit,True)
            if case['status']!='Approved':
                raise RuleError('Disposition execution needs prior approval.',409)
            eid=integer(data,'evidence_id');evidence_for(repo,eid,uid)
            repo.write("UPDATE dispositions SET status='Executed',evidence_id=?,completed_at=? WHERE id=?",(eid,stamp(),case['id']))
            repo.write("UPDATE units SET lifecycle=?,publication='Draft',version=version+1 WHERE id=?",(case['action'],uid))
            repo.life(actor,uid,case['action'],reason+f'; evidence {eid}')
            repo.event(actor,'unit',uid,'Disposition executed',case['action'],[actor['id']]+repo.role_users('workflow_admin'))


@bp.route('/approvals',methods=['GET','POST'])
@signed_in
def approvals():
    Policy().require(g.user,'workflow_admin')
    repo=Repository()
    ExchangeService().expire()
    if request.method=='POST':
        kind=request.form.get('kind');target=integer(request.form,'target_id')
        if kind=='release':WorkflowService().release(g.user,target,request.form)
        elif kind=='request':WorkflowService().decide(g.user,target,request.form)
        elif kind=='disposition':LifecycleService().disposition(g.user,target,request.form)
        else:raise RuleError('Unknown approval type.')
        flash('Decision saved.')
        return redirect(url_for('workflow.approvals'))
    return render_template('approvals.html',releases=repo.all("SELECT u.*,l.name FROM units u JOIN listings l ON l.id=u.listing_id WHERE publication='Release pending'"),
                           pending=repo.all("SELECT * FROM requests WHERE status='Pending'"),dispositions=repo.all("SELECT * FROM dispositions WHERE status='Pending'"))


@bp.post('/requests/<int:rid>/handover')
@signed_in
def handover(rid):
    operation=request.form.get('operation')
    service=WorkflowService()
    if operation=='collect':service.collect(g.user,rid,request.form)
    elif operation=='receive':service.receive(g.user,rid,request.form)
    elif operation=='return':service.resolve(g.user,rid,request.form)
    else:raise RuleError('Unknown handover action.')
    flash('Handover action recorded.')
    return redirect(url_for('exchange.detail',rid=rid))


@bp.route('/assets/<int:uid>/lifecycle',methods=['GET','POST'])
@signed_in
def lifecycle(uid):
    repo=Repository();unit=repo.one('SELECT * FROM units WHERE id=?',(uid,))
    Policy().require(g.user,'custodian','maintenance','workflow_admin')
    Policy().unit(g.user,unit)
    if request.method=='POST':
        op=request.form.get('operation');service=LifecycleService()
        if op in ('new_job','job'):service.maintain(g.user,uid,request.form)
        elif op=='inspect':service.inspect(g.user,uid,request.form)
        elif op in ('propose_disposition','execute_disposition'):service.disposition(g.user,uid,request.form)
        else:raise RuleError('Unknown lifecycle action.')
        return redirect(url_for('workflow.lifecycle',uid=uid))
    return render_template('lifecycle.html',unit=unit,jobs=repo.all('SELECT * FROM maintenance WHERE unit_id=?',(uid,)),
                           service_users=repo.all("SELECT id,name FROM users WHERE role='maintenance' AND active=1 AND department_id=?",(unit['owner_dept_id'],)),dispositions=repo.all('SELECT * FROM dispositions WHERE unit_id=?',(uid,)))


@bp.get('/audit')
@signed_in
def audit():
    Policy().require(g.user,'workflow_admin','system_admin')
    return render_template('audit.html',events=Repository().all('SELECT a.*,u.name actor FROM audit a LEFT JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 500'))
