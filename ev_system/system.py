import datetime
import os
import sqlite3
from . import server_time


def periodic_check(db, ):

    # time = datetime.datetime.now()
    time = server_time.server_now()
    #
    requests = db.execute(
        'SELECT r.id, start_time, duration, position, username, email'
        ' FROM requests r JOIN slots s on r.station_id = s.id JOIN user u on r.requester_id = u.id'
        ' WHERE start_time <= ? AND r.status == \'pending\''
        ' ORDER BY start_time ASC', [time]
    ).fetchall()

    print('periodic check: ' + str(time))

    if len(requests) > 0:
        for req in requests:
            print ('Request {}: Notify {} ({}) to connect car to {} for {} minutes'.format(
                req['id'], req['username'], req['email'], req['position'], req['duration']
            ))

            db.execute(
                'UPDATE requests'
                ' SET status = \'notify\''
                ' WHERE id = ?', [req['id']]
            )
            db.commit()
    else:
        print('No requests to update')



