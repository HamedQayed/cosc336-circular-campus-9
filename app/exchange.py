from datetime import datetime, timedelta, time
from contextlib import contextmanager
from zoneinfo import ZoneInfo
import json
from flask import Blueprint, g, request, render_template, redirect, url_for, flash
from .db import Repository, transaction
from .domain import RuleError, AssetUnit, ResourceRequest, RequestSpecification, now, stamp, CATEGORIES
from .forms import text, integer, choice
from .security import Policy, signed_in

bp=Blueprint('exchange',__name__)


@contextmanager
def expiring_transaction():
    """Keep expiration durable even when the requested action is rejected."""
    try:
        with transaction():
            ExchangeService().expire_locked()
            yield
    except RuleError:
        # The action transaction rolled back, including any expiration it made.
        # Reapply expiration separately, then preserve the original rejection.
        ExchangeService().expire()
        raise


class ExchangeService:
    def __init__(self):
        self.repo=Repository()

    def expire(self):
        with transaction():
            self.expire_locked()

    def expire_locked(self):
        for rec in self.repo.all("SELECT * FROM requests WHERE status IN ('Pending','Approved') AND expires_at<?",(stamp(),)):
            in_transit=self.repo.all("SELECT id FROM transfers WHERE request_id=? AND status IN ('Awaiting receipt','Receipt disputed')",(rec['id'],))
            if in_transit:
                changed=self.repo.write("UPDATE transfers SET status='Receipt disputed' WHERE request_id=? AND status='Awaiting receipt'",(rec['id'],)).rowcount
                if changed:
                    self.repo.write('UPDATE requests SET version=version+1 WHERE id=?',(rec['id'],))
                    self.repo.event(None,'request',rec['id'],'Transfer expired in transit',
                                    'Physical return must be verified before releasing the hold.',
                                    [rec['creator_id'],rec['destination_custodian_id']]+self.repo.role_users('workflow_admin'))
                continue
            self.repo.write("UPDATE requests SET status='Expired',version=version+1 WHERE id=?",(rec['id'],))
            self.repo.write('UPDATE holds SET active=0 WHERE request_id=?',(rec['id'],))
            self.repo.write("UPDATE transfers SET status='Cancelled' WHERE request_id=?",(rec['id'],))
            self.repo.event(None,'request',rec['id'],'Request expired',f'Request {rec["id"]}',[rec['creator_id']])

    def reserve(self,actor,data):
        Policy().require(actor,'requester','representative')
        repo=self.repo
        spec=RequestSpecification(text(data,'purpose'),integer(data,'quantity'),text(data,'needed_date',10))
        spec.validate()
        dept=integer(data,'destination_dept_id')
        if dept!=actor['department_id']:
            raise RuleError('Requests must be for your own department.',403)
        cust=repo.one("SELECT * FROM users WHERE id=? AND role='custodian' AND active=1 AND department_id=?",(integer(data,'destination_custodian_id'),dept))
        location=text(data,'destination_location',150)
        category=choice(data,'category',CATEGORIES)
        urgency=choice(data,'urgency',('Low','Normal','High'))
        preferred=data.get('preferred_condition','')
        if preferred not in ('','New','Good','Fair','Poor'):
            raise RuleError('Choose a valid preferred condition.')
        key=text(data,'request_key',100)
        lid=integer(data,'listing_id') if data.get('listing_id') else None
        with expiring_transaction():
            prior=repo.all('SELECT * FROM requests WHERE request_key=?',(key,))
            if prior:
                if prior[0]['creator_id']!=actor['id']:
                    raise RuleError('Request key belongs to a different user.',409)
                return prior[0]['id']
            units=[]
            if lid:
                listing=repo.one('SELECT * FROM listings WHERE id=?',(lid,))
                if listing['category']!=category:
                    raise RuleError('The selected listing does not match the requested category.')
                candidates=repo.all("SELECT * FROM units u WHERE listing_id=? AND publication='Published' AND serviceability='Serviceable' AND lifecycle='Active' AND owner_dept_id<>? AND (?='' OR condition=?) AND NOT EXISTS(SELECT 1 FROM holds h WHERE h.unit_id=u.id AND active=1) ORDER BY id",
                                    (lid,dept,preferred,preferred))
                if len(candidates)<spec.quantity:
                    raise RuleError('Not enough eligible units remain. No units were reserved.',409)
                # A handover is recorded by one source custodian for the whole
                # request. Do not create a reservation that nobody can collect.
                by_custodian={}
                for unit in candidates:
                    by_custodian.setdefault(unit['custodian_id'],[]).append(unit)
                units=next((group[:spec.quantity] for group in by_custodian.values()
                            if len(group)>=spec.quantity),[])
                if not units:
                    raise RuleError('No single source custodian has enough eligible units for this request. Request smaller quantities separately; no units were reserved.',409)
                for unit in units:
                    AssetUnit(unit['id'],unit['publication'],unit['serviceability'],unit['lifecycle']).reserve()
                # Required specifications are a hard filter, not an AI promise.
                terms=[t.strip().lower() for t in data.get('specifications','').split(',') if t.strip()]
                facts=(listing['name']+' '+listing['description']+' '+listing['specifications']).lower()
                if any(term not in facts for term in terms):
                    raise RuleError('The listing does not establish every required specification. Use comma-separated exact terms or save an unmatched need.',409)
            end=datetime.combine(datetime.fromisoformat(spec.needed_date).date(),time.max,ZoneInfo('Asia/Dubai'))
            expiry=min(now()+timedelta(hours=48),end).isoformat(timespec='seconds') if lid else None
            rid=repo.write('INSERT INTO requests(creator_id,listing_id,purpose,category,specifications,preferred_condition,quantity,urgency,needed_date,destination_dept_id,destination_custodian_id,destination_location,status,created_at,expires_at,request_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (actor['id'],lid,spec.purpose,category,text(data,'specifications',1000,False),preferred,spec.quantity,urgency,spec.needed_date,dept,cust['id'],location,'Pending' if lid else 'Seeking',stamp(),expiry,key)).lastrowid
            for unit in units:
                repo.write('INSERT INTO holds(request_id,unit_id) VALUES(?,?)',(rid,unit['id']))
                repo.life(actor,unit['id'],'Reserved',f'Request {rid}')
            repo.event(actor,'request',rid,'Request submitted',f'Request {rid}; {spec.quantity} unit(s)',[actor['id']]+repo.role_users('workflow_admin'))
        return rid

    def cancel(self,actor,rid):
        repo=self.repo
        with expiring_transaction():
            rec=repo.one('SELECT * FROM requests WHERE id=?',(rid,))
            Policy().request(actor,rec)
            ResourceRequest(rid,rec['status']).require('Seeking','Pending','Approved')
            if rec['status']=='Approved':
                Policy().require(actor,'workflow_admin')
                if repo.all("SELECT id FROM transfers WHERE request_id=? AND status IN ('Awaiting receipt','Receipt disputed')",(rid,)):
                    raise RuleError('Collected units must go through dispute resolution.',409)
            elif rec['creator_id']!=actor['id']:
                raise RuleError('Only the creator can cancel this request.',403)
            repo.write("UPDATE requests SET status='Cancelled',version=version+1 WHERE id=?",(rid,))
            repo.write('UPDATE holds SET active=0 WHERE request_id=?',(rid,))
            repo.write("UPDATE transfers SET status='Cancelled' WHERE request_id=?",(rid,))
            repo.event(actor,'request',rid,'Request cancelled',f'Request {rid}',[rec['creator_id']])


@bp.route('/requests',methods=['GET','POST'])
@signed_in
def requests_page():
    if request.method=='POST':
        rid=ExchangeService().reserve(g.user,request.form)
        flash('Request saved. Selecting an AI recommendation alone does not reserve stock.')
        return redirect(url_for('exchange.detail',rid=rid))
    ExchangeService().expire()
    repo=Repository()
    rows=[]
    for rec in repo.all('SELECT r.*,u.name creator,d.name destination FROM requests r JOIN users u ON u.id=r.creator_id JOIN departments d ON d.id=r.destination_dept_id ORDER BY r.id DESC'):
        try:
            Policy().request(g.user,rec)
            rows.append(rec)
        except RuleError:
            pass
    return render_template('requests.html',requests=rows)


@bp.get('/requests/new')
@signed_in
def new():
    import secrets
    Policy().require(g.user,'requester','representative')
    ExchangeService().expire()
    listings=Repository().all("SELECT l.* FROM listings l WHERE EXISTS(SELECT 1 FROM units u WHERE u.listing_id=l.id AND u.publication='Published' AND u.serviceability='Serviceable' AND u.lifecycle='Active' AND u.owner_dept_id<>? AND NOT EXISTS(SELECT 1 FROM holds h WHERE h.unit_id=u.id AND h.active=1)) ORDER BY l.name",(g.user['department_id'],))
    return render_template('request_form.html',request_key=secrets.token_urlsafe(24),listings=listings)


@bp.route('/requests/<int:rid>',methods=['GET','POST'])
@signed_in
def detail(rid):
    ExchangeService().expire()
    repo=Repository()
    rec=repo.one('SELECT r.*,u.name creator,d.name destination FROM requests r JOIN users u ON u.id=r.creator_id JOIN departments d ON d.id=r.destination_dept_id WHERE r.id=?',(rid,))
    Policy().request(g.user,rec)
    if request.method=='POST':
        ExchangeService().cancel(g.user,rid)
        return redirect(url_for('exchange.detail',rid=rid))
    units=repo.all('SELECT u.*,l.name,h.active,t.status transfer_status,t.source_custodian_id FROM holds h JOIN units u ON u.id=h.unit_id JOIN listings l ON l.id=u.listing_id LEFT JOIN transfers t ON t.request_id=h.request_id AND t.unit_id=u.id WHERE h.request_id=?',(rid,))
    return render_template('request_detail.html',rec=rec,units=units)
