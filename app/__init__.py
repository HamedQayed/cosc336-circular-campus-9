import os
import secrets
from pathlib import Path
from flask import Flask, g, render_template, request
from .db import Repository, close_db, init_schema
from .domain import RuleError, CATEGORIES, CONDITIONS, now
from .security import load_identity, csrf_token, signed_in


def create_app(test_config=None):
    root = Path(__file__).resolve().parent.parent
    local_settings={}
    env_file=root/'.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key,value=line.split('=',1)
                if key.strip() in ('AI_PROVIDER','AI_MODEL','OPENAI_API_KEY','OPENROUTER_API_KEY'):
                    local_settings[key.strip()]=value.strip().strip('\"\'')
    app = Flask(__name__, instance_path=str(root/'instance'), instance_relative_config=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    secret_file = Path(app.instance_path)/'session-secret'
    if not secret_file.exists():
        try:
            with secret_file.open('x') as f:
                f.write(secrets.token_hex(32))
            secret_file.chmod(0o600)
        except FileExistsError:
            pass
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secret_file.read_text(),
                      DATABASE=str(Path(app.instance_path)/'campus.sqlite'),
                      EVIDENCE_DIR=str(Path(app.instance_path)/'evidence'),
                      STAGE=int((root/'STAGE').read_text().strip()),
                      MAX_CONTENT_LENGTH=6*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
                      AI_PROVIDER=os.environ.get('AI_PROVIDER',local_settings.get('AI_PROVIDER','openrouter')),
                      AI_MODEL=os.environ.get('AI_MODEL',local_settings.get('AI_MODEL','')),
                      OPENROUTER_API_KEY=os.environ.get('OPENROUTER_API_KEY',local_settings.get('OPENROUTER_API_KEY','')),
                      OPENAI_API_KEY=os.environ.get('OPENAI_API_KEY',local_settings.get('OPENAI_API_KEY','')))
    if test_config:
        app.config.update(test_config)
    Path(app.config['EVIDENCE_DIR']).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    app.before_request(load_identity)
    app.jinja_env.globals['csrf_token']=csrf_token
    from .auth import bp
    app.register_blueprint(bp)
    if app.config['STAGE'] >= 2:
        from .assets import bp as assets_bp
        from .exchange import bp as exchange_bp
        app.register_blueprint(assets_bp)
        app.register_blueprint(exchange_bp)
    if app.config['STAGE'] >= 3:
        from .workflow import bp as workflow_bp
        app.register_blueprint(workflow_bp)
    if app.config['STAGE'] >= 4:
        from .reporting import bp as reporting_bp
        from .ai import bp as ai_bp
        from .backup import register_commands
        app.register_blueprint(reporting_bp)
        app.register_blueprint(ai_bp)
        register_commands(app)

    @app.context_processor
    def common():
        return dict(csrf_token=csrf_token, stage=app.config['STAGE'], categories=CATEGORIES,
                    conditions=CONDITIONS, today=now().date().isoformat(),
                    departments=Repository().all('SELECT * FROM departments ORDER BY name'),
                    custodians=Repository().all("SELECT id,name,department_id FROM users WHERE role='custodian' AND active=1"))

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(RuleError)
    def rule_error(error):
        return render_template('error.html', message=str(error), saved=request.form if request.method=='POST' else None), error.status

    @app.errorhandler(413)
    def too_large(_):
        return render_template('error.html', message='File too large. Maximum evidence size is 5 MB.'), 413

    @app.get('/')
    @signed_in
    def home():
        return render_template('home.html')

    @app.route('/notifications', methods=['GET','POST'])
    @signed_in
    def notifications():
        repo=Repository()
        if request.method=='POST':
            from .domain import stamp
            repo.write('UPDATE notifications SET read_at=? WHERE recipient_id=? AND read_at IS NULL',(stamp(),g.user['id']))
        return render_template('notifications.html', notices=repo.all('SELECT n.*,a.created_at FROM notifications n JOIN audit a ON a.id=n.audit_id WHERE recipient_id=? ORDER BY n.id DESC',(g.user['id'],)))

    @app.cli.command('init-demo')
    def init_demo():
        from .seed import seed_demo
        init_schema()
        created=seed_demo()
        print('Created demo.' if created else 'Existing data preserved.')
        print('Credentials: instance/demo-credentials.txt')

    with app.app_context():
        init_schema()
    return app
