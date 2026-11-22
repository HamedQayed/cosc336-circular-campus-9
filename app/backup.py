"""CLI-only snapshots and isolated restore; never replace the active database."""
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
import click
from flask import current_app
from .db import transaction, get_db


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(destination):
    destination=Path(destination).resolve()
    evidence=Path(current_app.config['EVIDENCE_DIR']).resolve()
    if destination==evidence or evidence in destination.parents:
        raise click.ClickException('Choose a snapshot directory outside active evidence.')
    if destination.exists():raise click.ClickException('Choose a new snapshot directory.')
    destination.mkdir(parents=True)
    try:
        with transaction():
            # BEGIN IMMEDIATE prevents application evidence/record writes during the coordinated snapshot.
            source=sqlite3.connect(current_app.config['DATABASE'])
            target=sqlite3.connect(destination/'campus.sqlite')
            try:source.backup(target)
            finally:target.close();source.close()
            shutil.copytree(evidence,destination/'evidence')
        manifest={str(p.relative_to(destination)):digest(p) for p in destination.rglob('*') if p.is_file()}
        (destination/'manifest.json').write_text(json.dumps({'format':1,'files':manifest},indent=2))
    except BaseException:
        shutil.rmtree(destination)
        raise


def restore(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    active=Path(current_app.config['DATABASE']).resolve().parent
    if destination==active or active in destination.parents or destination in active.parents or destination.exists():
        raise click.ClickException('Restore requires a new isolated directory outside active instance data.')
    manifest=json.loads((source/'manifest.json').read_text())
    for name,expected in manifest['files'].items():
        path=(source/name).resolve()
        if source not in path.parents or not path.is_file() or digest(path)!=expected:
            raise click.ClickException('Snapshot verification failed.')
    destination.mkdir(parents=True)
    for name in manifest['files']:
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/name,target)
    check=sqlite3.connect(destination/'campus.sqlite')
    try:
        if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or check.execute('PRAGMA foreign_key_check').fetchall():
            raise click.ClickException('Restored database failed integrity checks.')
    finally:check.close()


def register_commands(app):
    @app.cli.command('snapshot')
    @click.argument('destination')
    def take_snapshot(destination):
        snapshot(destination);click.echo('Snapshot created with evidence and SHA-256 manifest.')

    @app.cli.command('restore-isolated')
    @click.argument('source')
    @click.argument('destination')
    def isolated(source,destination):
        restore(source,destination);click.echo('Verified isolated restore completed. Active data preserved.')
