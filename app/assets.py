import io
import uuid
from datetime import date
from pathlib import Path
from flask import Blueprint, g, request, render_template, redirect, url_for, flash, current_app, send_file
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from .db import Repository, transaction
from .domain import CATEGORIES, CONDITIONS, RuleError, stamp, now
from .forms import text, integer, choice, money
from .security import Policy, signed_in

bp=Blueprint('assets',__name__)


class AssetService:
    def edit(self,actor,unit_id,data):
        Policy().require(actor,'custodian')
        repo=Repository()
        with transaction():
            unit=repo.one('SELECT * FROM units WHERE id=?',(unit_id,));Policy().unit(actor,unit,True)
            if unit['publication']!='Draft' or unit['lifecycle']!='Active' or repo.all('SELECT id FROM holds WHERE unit_id=? AND active=1',(unit_id,)):
                raise RuleError('Edit only active Draft units without stock holds.',409)
            if integer(data,'version')!=unit['version']:
                raise RuleError('This unit changed. Reload before saving.',409)
            condition=choice(data,'condition',CONDITIONS)
            serviceability='Quarantined' if condition=='Unsafe' else unit['serviceability']
            if repo.all('SELECT id FROM units WHERE listing_id=? AND custodian_id<>?',(unit['listing_id'],actor['id'])):
                raise RuleError('Shared listing metadata cannot be changed after units transfer to another custodian. Register a new listing for different metadata.',409)
            if repo.all("SELECT id FROM units u WHERE listing_id=? AND (publication<>'Draft' OR lifecycle<>'Active' OR EXISTS(SELECT 1 FROM holds h WHERE h.unit_id=u.id AND h.active=1))",(unit['listing_id'],)):
                raise RuleError('Shared listing metadata can only be edited while every unit is active, Draft and without stock holds.',409)
            repo.write('UPDATE listings SET name=?,description=?,category=?,specifications=? WHERE id=?',
                       (text(data,'name',120),text(data,'description',2000),choice(data,'category',CATEGORIES),text(data,'specifications',1000,False),unit['listing_id']))
            repo.write('UPDATE units SET location=?,condition=?,value_cents=?,serviceability=?,version=version+1 WHERE id=?',
                       (text(data,'location',150),condition,money(data,'value'),serviceability,unit_id))
            repo.write('UPDATE units SET version=version+1 WHERE listing_id=? AND id<>?',(unit['listing_id'],unit_id))
            repo.life(actor,unit_id,'Metadata edited',text(data,'reason')+'; prior condition '+unit['condition']+'; prior location '+unit['location'])
            repo.event(actor,'unit',unit_id,'Metadata edited',text(data,'reason'))

    def create(self, actor, data):
        Policy().require(actor,'custodian')
        repo=Repository()
        quantity=integer(data,'quantity')
        if not 1<=quantity<=100:
            raise RuleError('Quantity must be between 1 and 100.')
        name, description=text(data,'name',120),text(data,'description',2000)
        category=choice(data,'category',CATEGORIES)
        condition=choice(data,'condition',CONDITIONS)
        location=text(data,'location',150)
        value=money(data,'value')
        purchase=data.get('purchase_date','').strip() or None
        if purchase:
            try:
                if date.fromisoformat(purchase)>now().date():
                    raise ValueError
            except ValueError:
                raise RuleError('Purchase date must be valid and cannot be in the future.') from None
        with transaction():
            lid=repo.write('INSERT INTO listings(name,description,category,specifications,creator_id) VALUES(?,?,?,?,?)',
                           (name,description,category,text(data,'specifications',1000,False),actor['id'])).lastrowid
            for _ in range(quantity):
                uid=repo.write('INSERT INTO units(listing_id,owner_dept_id,custodian_id,location,condition,serviceability,value_cents,purchase_date) VALUES(?,?,?,?,?,?,?,?)',
                               (lid,actor['department_id'],actor['id'],location,condition,
                                'Quarantined' if condition=='Unsafe' else 'Serviceable',value,purchase)).lastrowid
                repo.life(actor,uid,'Registered',f'{name}; Draft publication')
            repo.event(actor,'listing',lid,'Asset registered',f'{quantity} physical units registered')
        return lid

    def propose_release(self, actor, unit_id):
        repo=Repository()
        with transaction():
            unit=repo.one('SELECT * FROM units WHERE id=?',(unit_id,))
            Policy().require(actor,'custodian')
            Policy().unit(actor,unit,True)
            if unit['publication']!='Draft' or unit['serviceability']!='Serviceable' or unit['lifecycle']!='Active':
                raise RuleError('Release requires a Draft, Serviceable, Active unit.',409)
            repo.write("UPDATE units SET publication='Release pending',version=version+1 WHERE id=?",(unit_id,))
            repo.life(actor,unit_id,'Release proposed','Awaiting workflow administrator approval')
            repo.event(actor,'unit',unit_id,'Release proposed',f'Unit {unit_id}',repo.role_users('workflow_admin'))


class EvidenceService:
    def require_upload(self,actor,unit):
        repo=Repository()
        unit_id=unit['id']
        Policy().unit(actor,unit)
        allowed=actor['role']=='custodian' and unit['custodian_id']==actor['id']
        allowed=allowed or actor['role']=='maintenance' and bool(repo.all('SELECT id FROM maintenance WHERE unit_id=? AND assignee_id=?',(unit_id,actor['id'])))
        allowed=allowed or actor['role']=='custodian' and bool(repo.all("SELECT r.id FROM requests r JOIN holds h ON h.request_id=r.id WHERE h.unit_id=? AND r.destination_custodian_id=? AND r.status='Approved'",(unit_id,actor['id'])))
        if not allowed:
            raise RuleError('Only the assigned or receiving custodian or assigned service user can attach evidence.',403)

    def upload(self,actor,unit_id,file):
        repo=Repository()
        unit=repo.one('SELECT * FROM units WHERE id=?',(unit_id,))
        self.require_upload(actor,unit)
        raw=file.read(5*1024*1024+1)
        if not raw or len(raw)>5*1024*1024:
            raise RuleError('Evidence must contain between 1 byte and 5 MB.')
        ext=Path(file.filename or '').suffix.lower()
        mime={'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','pdf':'application/pdf'}.get(ext.lstrip('.'))
        if not mime:
            raise RuleError('Evidence supports JPEG, PNG and PDF only.')
        try:
            if ext=='.pdf':
                if not raw.startswith(b'%PDF-') or not PdfReader(io.BytesIO(raw),strict=True).pages:
                    raise ValueError
            else:
                image=Image.open(io.BytesIO(raw))
                if image.format not in ('PNG','JPEG') or Image.MIME[image.format]!=mime:
                    raise ValueError
                image.verify()
        except Exception:
            raise RuleError('The file contents do not match a valid supported evidence file.') from None
        storage=uuid.uuid4().hex+ext
        path=Path(current_app.config['EVIDENCE_DIR'])/storage
        try:
            with transaction():
                # Permissions are checked again while holding the write lock.
                unit=repo.one('SELECT * FROM units WHERE id=?',(unit_id,))
                self.require_upload(actor,unit)
                path.write_bytes(raw)
                eid=repo.write('INSERT INTO evidence(unit_id,uploader_id,filename,storage_name,mime,created_at) VALUES(?,?,?,?,?,?)',
                               (unit_id,actor['id'],secure_filename(file.filename)[:150] or 'evidence'+ext,storage,mime,stamp())).lastrowid
                repo.event(actor,'unit',unit_id,'Evidence attached',f'Evidence {eid}')
            return eid
        except BaseException:
            path.unlink(missing_ok=True)
            raise


@bp.get('/assets')
@signed_in
def catalogue():
    from .exchange import ExchangeService
    ExchangeService().expire()
    args=[]
    filters=["u.publication='Published'","u.serviceability='Serviceable'","u.lifecycle='Active'",
             'NOT EXISTS(SELECT 1 FROM holds h WHERE h.unit_id=u.id AND h.active=1)']
    for field,column in [('category','l.category'),('condition','u.condition'),('department','u.owner_dept_id')]:
        if request.args.get(field):
            filters.append(column+'=?');args.append(request.args[field])
    if request.args.get('q'):
        filters.append('(l.name LIKE ? OR l.description LIKE ? OR l.specifications LIKE ?)')
        args.extend(['%'+request.args['q']+'%']*3)
    rows=Repository().all('SELECT l.*,u.id unit_id,u.condition,u.location,d.name department FROM listings l JOIN units u ON u.listing_id=l.id JOIN departments d ON d.id=u.owner_dept_id WHERE '+' AND '.join(filters)+' ORDER BY l.id,u.id',args)
    return render_template('catalogue.html',units=rows)


@bp.route('/assets/new',methods=['GET','POST'])
@signed_in
def new():
    Policy().require(g.user,'custodian')
    if request.method=='POST':
        AssetService().create(g.user,request.form)
        flash('Asset registered in Draft. Propose each unit for release when ready.')
        return redirect(url_for('assets.mine'))
    return render_template('asset_form.html')


@bp.get('/assets/mine')
@signed_in
def mine():
    Policy().require(g.user,'custodian')
    return render_template('my_assets.html',units=Repository().all('SELECT u.*,l.name FROM units u JOIN listings l ON l.id=u.listing_id WHERE custodian_id=? ORDER BY u.id',(g.user['id'],)))


@bp.route('/assets/<int:unit_id>/edit',methods=['GET','POST'])
@signed_in
def edit(unit_id):
    unit=Repository().one('SELECT u.*,l.name,l.description,l.category,l.specifications FROM units u JOIN listings l ON l.id=u.listing_id WHERE u.id=?',(unit_id,))
    Policy().require(g.user,'custodian');Policy().unit(g.user,unit,True)
    if request.method=='POST':
        AssetService().edit(g.user,unit_id,request.form)
        return redirect(url_for('assets.detail',unit_id=unit_id))
    return render_template('asset_edit.html',unit=unit)


@bp.route('/assets/<int:unit_id>',methods=['GET','POST'])
@signed_in
def detail(unit_id):
    repo=Repository()
    unit=repo.one('SELECT u.*,l.name,l.description,l.category,l.specifications FROM units u JOIN listings l ON l.id=u.listing_id WHERE u.id=?',(unit_id,))
    Policy().unit(g.user,unit)
    if request.method=='POST':
        if request.form.get('operation')=='release':
            AssetService().propose_release(g.user,unit_id)
        elif request.form.get('operation')=='evidence':
            if 'file' not in request.files:
                raise RuleError('Choose an evidence file.')
            eid=EvidenceService().upload(g.user,unit_id,request.files['file'])
            flash(f'Evidence {eid} attached. Use this ID when recording a handover or service event.')
        else:
            raise RuleError('Unknown asset action.')
        return redirect(url_for('assets.detail',unit_id=unit_id))
    return render_template('asset_detail.html',unit=unit,history=repo.all('SELECT e.*,u.name actor FROM events e JOIN users u ON u.id=e.actor_id WHERE unit_id=? ORDER BY e.id DESC',(unit_id,)),
                           evidence=repo.all('SELECT * FROM evidence WHERE unit_id=?',(unit_id,)))


@bp.get('/evidence/<int:evidence_id>')
@signed_in
def download(evidence_id):
    repo=Repository()
    ev=repo.one('SELECT * FROM evidence WHERE id=?',(evidence_id,))
    unit=repo.one('SELECT * FROM units WHERE id=?',(ev['unit_id'],))
    # Evidence is more restricted than the published catalogue.
    Policy().evidence(g.user,unit)
    return send_file(Path(current_app.config['EVIDENCE_DIR'])/ev['storage_name'],mimetype=ev['mime'],as_attachment=True,download_name=ev['filename'])
