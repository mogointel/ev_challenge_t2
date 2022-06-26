import datetime
import os
import sqlite3
from . import server_time
import time
import random

rand_seed = int(time.mktime(server_time.server_now().timetuple()))
print("Using random seed {}".format(rand_seed))
random.seed(rand_seed)


def periodic_check(db, ):

    # time = datetime.datetime.now()
    time = server_time.server_now()

    next_car_time = time + datetime.timedelta(minutes=30)
    #
    requests = db.execute(
        'SELECT r.id, start_time, duration, position, username, email, station_id'
        ' FROM requests r JOIN slots s on r.slot_id = s.id JOIN user u on r.requester_id = u.id'
        ' WHERE start_time <= ? AND r.status == \'pending\''
        ' ORDER BY start_time ASC', [next_car_time]
    ).fetchall()

    print('periodic check: ' + str(time))

    if len(requests) > 0:
        for req in requests:
            print ('Request {}: Notify {} ({}) to connect car to {} for {} minutes'.format(
                req['id'], req['username'], req['email'], req['position'], req['duration']
            ))

            code_num = random.randrange(100000000)
            code = f"{code_num:08d}"
            db.execute(
                'UPDATE station_code'
                ' SET code = ?'
                ' WHERE station_id = ?', (code, req['station_id'])
            )

            db.execute(
                'UPDATE requests'
                ' SET status = \'notify\''
                ' WHERE id = ?', [req['id']]
            )
            db.commit()
    else:
        print('No requests to update')



