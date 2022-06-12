import datetime
import os

from flask import Flask
from flask_qrcode import QRcode
from flask_apscheduler import APScheduler
from . import db
from . import server_time
from . import system


scheduler = APScheduler()


def periodic_check():
    global scheduler
    # app = Flask.app_context()
    with scheduler.app.app_context():
        d = db.get_db()
        system.periodic_check(d)


def fmt_now(is_short=True):
    # dt = datetime.datetime.now()  # TODO: restore this line to use current datetime
    dt = server_time.server_now()
    fmt = "%Y-%m-%d"
    if not is_short:
        fmt += "T%H:%M"
    return dt.strftime(fmt)


def create_app(test_config=None):
    global scheduler

    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'ev_system.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    @app.route('/user')
    def user_page():
        return 'This is a User page'

    @app.route('/station')
    def station_page():
        return 'This is a Station page'

    @app.route('/admin')
    def admin_page():
        return 'This is an Admin page'

    @app.context_processor
    def now_processor():
        return dict(now=fmt_now)

    QRcode(app)

    #scheduler = APScheduler()
    scheduler.init_app(app)
    #from . import system
    scheduler.add_job(id='periodic-task', func=periodic_check, trigger='interval', seconds=10)
    scheduler.start()


    #from . import db
    db.init_app(app)

    from . import auth
    app.register_blueprint(auth.bp)

    from . import request
    app.register_blueprint(request.bp)
    app.add_url_rule('/', endpoint='index')

    return app
