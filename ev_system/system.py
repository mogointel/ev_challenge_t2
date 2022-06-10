import datetime
import os
from . import db
import ev_system
from flask import Flask


def periodic_check():
    # app = Flask.app_context()
    # with app:
    #     d = db.get_db_ext()
    time = datetime.datetime.now()
    # time = datetime.datetime(year=2022, month=6, day=8, hour=10, minute=0)
    #
    # requests = d.execute(
    #     'SELECT r.id, start_time, duration, position, username, email'
    #     ' FROM requests r JOIN slots s on r.station_id = s.id JOIN user u on r.requester_id = u.id'
    #     ' WHERE start_time > ? AND status == \'pending\''
    #     ' ORDER BY start_time ASC', [time]
    # ).fetchall()

    print('periodic check: ' + str(time))

    # for req in requests:
    #     print ('Request {}: Notify {} ({}) to connect car to {} for {} minutes'.format(
    #         req['id'], req['username'], req['email'], req['position'], req['duration']
    #     ))



