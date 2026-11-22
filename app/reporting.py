import csv
import io
import json
from datetime import date
from decimal import Decimal
from flask import Blueprint, g, request, render_template, Response, redirect, url_for, flash
from .db import Repository, transaction
from .domain import RuleError, now
from .forms import integer, text, money
from .security import Policy, signed_in

bp=Blueprint('reporting',__name__)
REPORT_ROLES=('workflow_admin','procurement','finance','sustainability')


def period(data):
    start=data.get('from') or now().date().replace(day=1).isoformat()
    end=data.get('to') or now().date().isoformat()
    try:
        if date.fromisoformat(start)>date.fromisoformat(end):raise ValueError
    except ValueError:
        raise RuleError('Choose a valid inclusive reporting period.') from None
    return start,end


def amount(cents):
    return 'Unavailable' if cents is None else f'{Decimal(cents)/100:.2f}'


class ReportService:
    def calculate(self,actor,start,end):
        Policy().require(actor,*REPORT_ROLES)
        repo=Repository()
        rows=repo.all("SELECT DISTINCT u.id FROM units u JOIN transfers t ON t.unit_id=u.id WHERE t.status='Completed' AND substr(t.completed_at,1,10) BETWEEN ? AND ?",(start,end))
        ids=[r['id'] for r in rows]
        impacts={r['unit_id']:r for r in repo.all('SELECT * FROM impacts')}
        known_finance=[];known_carbon=[]
        for uid in ids:
            impact=impacts.get(uid)
            if impact and impact['finance_validated'] and impact['source'] and all(impact[k] is not None for k in ('replacement_cents','transfer_cents','repair_cents','refurbishment_cents')):
                known_finance.append(impact['replacement_cents']-impact['transfer_cents']-impact['repair_cents']-impact['refurbishment_cents'])
            if impact and impact['environment_validated'] and impact['source'] and impact['replacement_co2'] is not None and impact['reuse_co2'] is not None:
                known_carbon.append(impact['replacement_co2']-impact['reuse_co2'])
        dispositions=repo.all("SELECT DISTINCT unit_id,action FROM dispositions WHERE status='Executed' AND substr(completed_at,1,10) BETWEEN ? AND ?",(start,end))
        diverted=len({r['unit_id'] for r in dispositions if r['action'] in ('Donated','Recycled')})
        repairs=repo.one("SELECT COUNT(*) n,COUNT(DISTINCT unit_id) units FROM maintenance WHERE status='Closed' AND substr(completed_at,1,10) BETWEEN ? AND ?",(start,end))
        transfer_count=repo.one("SELECT COUNT(DISTINCT request_id) n FROM transfers WHERE status='Completed' AND substr(completed_at,1,10) BETWEEN ? AND ?",(start,end))['n']
        metrics={'completed_transfers':str(transfer_count),'unique_reused_units':str(len(ids)),
                 'net_savings_aed':amount(sum(known_finance)) if known_finance else 'Unavailable',
                 'finance_coverage':f'{len(known_finance)}/{len(ids)}',
                 'carbon_kg_co2e':f'{sum(known_carbon):.2f}' if known_carbon else 'Unavailable',
                 'carbon_coverage':f'{len(known_carbon)}/{len(ids)}',
                 'diversion_rate_percent':f'{100*diverted/len(dispositions):.2f}' if dispositions else 'Not applicable',
                 'closed_repair_jobs':str(repairs['n']),'distinct_repaired_units':str(repairs['units'])}
        # Each reporting profile receives only its field family, even before AI retrieval.
        allowed={'procurement':{'completed_transfers','unique_reused_units'},
                 'finance':{'completed_transfers','net_savings_aed','finance_coverage'},
                 'sustainability':{'unique_reused_units','carbon_kg_co2e','carbon_coverage','diversion_rate_percent','closed_repair_jobs','distinct_repaired_units'}}
        if actor['role'] in allowed:
            metrics={k:v for k,v in metrics.items() if k in allowed[actor['role']]}
        return {'from':start,'to':end,'metrics':metrics,'source_unit_ids':ids,'synthetic':True}

    def rows(self,actor,start,end):
        Policy().require(actor,*REPORT_ROLES)
        # Operational details are reserved for the workflow administrator.
        if actor['role']!='workflow_admin':
            return []
        return Repository().all('SELECT r.id,r.status,r.quantity,r.category,r.needed_date,d.name destination,COUNT(t.id) transferred_units FROM requests r JOIN departments d ON d.id=r.destination_dept_id LEFT JOIN transfers t ON t.request_id=r.id AND t.status=\'Completed\' WHERE substr(r.created_at,1,10) BETWEEN ? AND ? GROUP BY r.id ORDER BY r.id',(start,end))

    def save_inputs(self,actor,data):
        Policy().require(actor,'procurement','finance','sustainability')
        repo=Repository();uid=integer(data,'unit_id');source=text(data,'source',1000)
        with transaction():
            repo.one('SELECT id FROM units WHERE id=?',(uid,))
            repo.write('INSERT OR IGNORE INTO impacts(unit_id) VALUES(?)',(uid,))
            if actor['role'] in ('procurement','finance'):
                repo.write('UPDATE impacts SET replacement_cents=?,source=?,finance_validated=0 WHERE unit_id=?',(money(data,'replacement'),source,uid))
                if actor['role']=='finance':
                    repo.write('UPDATE impacts SET transfer_cents=?,repair_cents=?,refurbishment_cents=?,finance_validated=1 WHERE unit_id=?',(money(data,'transfer'),money(data,'repair'),money(data,'refurbishment'),uid))
            else:
                values=[]
                for key in ('replacement_co2','reuse_co2'):
                    raw=str(data.get(key,'')).strip()
                    try:
                        v=float(raw) if raw else None
                        if v is not None and (not __import__('math').isfinite(v) or v<0):raise ValueError
                    except ValueError:
                        raise RuleError('Carbon factors must be finite nonnegative numbers or Unknown.') from None
                    values.append(v)
                repo.write('UPDATE impacts SET replacement_co2=?,reuse_co2=?,source=?,environment_validated=1 WHERE unit_id=?',(*values,source,uid))
            repo.event(actor,'unit',uid,'Reporting inputs validated',source)


@bp.route('/reports',methods=['GET','POST'])
@signed_in
def reports():
    start,end=period(request.args)
    service=ReportService()
    report=service.calculate(g.user,start,end)
    if request.method=='POST':
        service.save_inputs(g.user,request.form)
        flash('Reporting inputs saved with source. Blank amounts remain Unknown.')
        return redirect(url_for('reporting.reports',**{'from':start,'to':end}))
    return render_template('reports.html',report=report,rows=service.rows(g.user,start,end))


def csv_safe(value):
    s='' if value is None else str(value)
    return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s


@bp.get('/reports.csv')
@signed_in
def export_csv():
    start,end=period(request.args);service=ReportService()
    report=service.calculate(g.user,start,end)
    output=io.StringIO(newline='');writer=csv.writer(output)
    writer.writerow(['Synthetic demonstration data',start,end])
    writer.writerow(['Metric','Value'])
    writer.writerows((k,csv_safe(v)) for k,v in report['metrics'].items())
    rows=service.rows(g.user,start,end)
    if rows:
        writer.writerow([]);writer.writerow(rows[0].keys())
        writer.writerows([[csv_safe(v) for v in row] for row in rows])
    return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=campus-report.csv'})
