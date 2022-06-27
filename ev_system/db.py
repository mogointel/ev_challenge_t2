import sqlite3

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db


def get_db_ext():
    db = sqlite3.connect('../instance/ev_system.sqlite',
                         detect_types=sqlite3.PARSE_DECLTYPES
    )
    db.row_factory = sqlite3.Row

    return db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()


def close_db_ext(db, e=None):

    if db is not None:
        db.close()


def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

    with sqlite3.connect(
        app.config['DATABASE'],
        detect_types=sqlite3.PARSE_DECLTYPES
    ) as db:
        db.row_factory = sqlite3.Row

        stations = db.execute(
            'SELECT id'
            ' FROM stations'
        )

        for station in stations:
            code = db.execute(
                'SELECT *'
                ' FROM station_code'
                ' WHERE station_id = ?', [station['id']]
            ).fetchone()
            if code is None:
                db.execute(
                    'INSERT INTO station_code (station_id, code)'
                    ' VALUES (?, "NO CODE")', [station['id']]
                )
            # else:
            #     db.execute(
            #         'UPDATE station_code'
            #         ' SET code = "NO CODE"'
            #         ' WHERE station_id = ?', [station['id']]
            #     )
        db.commit()


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')