import datetime
import time

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from ev_system.auth import login_required
from ev_system.db import get_db

bp = Blueprint('request', __name__)


@bp.route('/')
def index():
    db = get_db()
    requests = db.execute(
        'SELECT r.id, start_time, end_time, created, position, requester_id, username'
        ' FROM requests r join user u on r.requester_id = u.id join slots s on r.station_id = s.id'
        ' WHERE requester_id == ?'
        ' ORDER BY start_time ASC', [g.user['id']]
    ).fetchall()
    return render_template('request/all_request.html', requests=requests)


@bp.route('/schedule')
@login_required
def schedule():
    db = get_db()
    duration = int(request.args.get('req_duration', None))
    curr_time = datetime.datetime(year=2022, month=6, day=8, hour=10,
                                  minute=0)  # datetime.datetime.now() TODO: remove this comment
    turn_around = 30 # TODO: get from config
    start_time = datetime.datetime.strptime(request.args.get('req_start', None), '%Y-%m-%dT%H:%M')
    end_time = start_time.replace(hour=18, minute=0)
    requests = db.execute(
        'SELECT r.id, start_time, end_time, station_id'
        ' FROM requests r JOIN slots s on r.station_id = s.id'
        ' WHERE start_time > ?'
        ' ORDER BY start_time ASC', [start_time]
    ).fetchall()
    station_ids = db.execute(
        'SELECT id FROM slots WHERE status != \'disabled\''
    ).fetchall()
    stations = [s[0] for s in station_ids]
    available_slots = {}

    # duration_offset = duration % 60
    # if curr_time.minute > duration_offset:
    #     curr_time.hour = curr_time.hour + 1
    while curr_time < end_time:
        available_slots[curr_time] = list(stations)
        curr_time = curr_time + datetime.timedelta(minutes=duration)

    for req in requests:
        req_start_time = req['start_time']
        req_end_time = req['end_time']
        req_station_id = req['station_id']
        curr_time = req_start_time
        while curr_time <= req_end_time:
            if curr_time in available_slots.keys():
                slot_stations = available_slots[curr_time]
                if req_station_id in slot_stations:
                    slot_stations.remove(req_station_id)
                    available_slots[curr_time] = slot_stations
            curr_time = curr_time + datetime.timedelta(minutes=duration)

    return render_template('request/schedule.html', slots=available_slots, duration=duration)


@bp.route('/request', methods=('GET', 'POST'))
@login_required
def request_page():
    if request.method == 'POST':
        duration = request.form['duration']
        start_date = request.form['start_date']
        error = None

        if not start_date:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            return redirect(url_for('request.schedule', req_duration=duration, req_start=start_date))

    return render_template('request/request.html')


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    start_time = datetime.datetime.strptime(request.args['start_time'], '%Y-%m-%d %H:%M:%S')
    stations = request.args['stations'].strip('][').split(', ')
    duration = int(request.args['duration'])
    turn_around = 30  # TODO: get from config
    end_time = start_time + datetime.timedelta(minutes=(duration + turn_around))

    if len(stations) == 0:
        return redirect(url_for('request.index')) # TODO: show error

    db = get_db()

    # Make sure that at least one of the stations does not have a conflict
    station_index = -1
    available_station = -1

    requests = [1]
    while (len(requests) > 0) and (station_index < len(stations)):
        station_index += 1
        curr_station = int(stations[station_index])
        requests = db.execute(
            'SELECT r.id, start_time, end_time, station_id'
            ' FROM requests r JOIN slots s on r.station_id = s.id'
            ' WHERE ((? BETWEEN start_time AND end_time) OR'
            ' (? BETWEEN start_time AND end_time)) AND r.station_id == ?'
            ' ORDER BY start_time ASC', [start_time, end_time, curr_station]
        ).fetchall()

    if len(requests) > 0:
        return redirect(url_for('request.index'))  # TODO: show error

    # Insert the request into the requests table

    available_station = stations[station_index]

    db.execute(
        'INSERT INTO requests (requester_id, start_time, end_time, station_id, duration, status)'
        ' VALUES (?, ?, ?, ?, ? ,?)',
        (g.user['id'], start_time, end_time, available_station, duration, 'pending')
    )
    db.commit()
    return redirect(url_for('request.index'))


def get_request(id, check_author=True):
    req = get_db().execute(
        'SELECT p.id, station_id, start_time, created, requester_id, username'
        ' FROM requests p JOIN user u ON p.requester_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if req is None:
        abort(404, f"Request id {id} doesn't exist.")

    if check_author and req['requester_id'] != g.user['id']:
        abort(403)

    return req


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    req = get_request(id)

    if request.method == 'POST':
        error = None

        if error is not None:
            flash(error)
        else:
            # db = get_db()
            # db.execute(
            #     'UPDATE post SET title = ?, body = ?'
            #     ' WHERE id = ?',
            #     (title, body, id)
            # )
            # db.commit()
            return redirect(url_for('request.index'))

    flash("Removed request {}".format(id))
    db = get_db()
    db.execute(
        'DELETE FROM requests'
        ' WHERE id = ?',
        [id]
    )
    db.commit()
    return redirect(url_for('request.index'))




@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_request(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('request.index'))