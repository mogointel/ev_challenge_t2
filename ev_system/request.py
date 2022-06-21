import datetime
import time
from . import server_time

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from ev_system.auth import login_required
from ev_system.db import get_db

bp = Blueprint('request', __name__)


@bp.route('/')
@login_required
def index():
    db = get_db()

    requests = db.execute(
        'SELECT r.id, start_time, end_time, created, position, requester_id, username'
        ' FROM requests r join user u on r.requester_id = u.id join slots s on r.slot_id = s.id'
        ' WHERE requester_id == ? AND r.status == \'notify\''
        ' ORDER BY start_time ASC', [g.user['id']]
    ).fetchone()

    if requests is not None:
        return render_template('request/notify.html', requests=requests)

    requests = db.execute(
        'SELECT r.id, start_time, end_time, created, position, requester_id, username'
        ' FROM requests r join user u on r.requester_id = u.id join slots s on r.slot_id = s.id'
        ' WHERE requester_id == ?'
        ' ORDER BY start_time ASC', [g.user['id']]
    ).fetchall()

    return render_template('request/all_request.html', requests=requests)


@bp.route('/schedule')
@login_required
def schedule():
    db = get_db()
    duration_id = int(request.args.get('req_duration', None))
    db = get_db()
    duration_db = db.execute(
        'SELECT *'
        ' FROM durations'
        ' WHERE id = ?', [duration_id]
    ).fetchone()

    duration = {'duration': int(duration_db['duration']), 'cost_weight': float(duration_db['cost_weight'])}
    est_cost = int(float(duration['duration']) * duration['cost_weight'])

    turn_around = 30 # TODO: get from config
    #curr_time = server_time.server_now()
    start_time = datetime.datetime.strptime(request.args.get('req_start', None), '%Y-%m-%dT%H:%M')
    end_time = start_time.replace(hour=18, minute=0)
    requests = db.execute(
        'SELECT r.id, start_time, end_time, slot_id'
        ' FROM requests r JOIN slots s on r.slot_id = s.id'
        ' WHERE (start_time BETWEEN ? AND ?) or (end_time BETWEEN ? AND ?) '
        ' ORDER BY start_time ASC', [start_time, end_time, start_time, end_time]
    ).fetchall()
    station_db = db.execute(
        'SELECT id, position FROM slots s WHERE (status != \'disabled\') AND (? BETWEEN min_slot_duration and max_slot_duration)', [duration['duration']]
    ).fetchall()
    #stations_names = [s[1] for s in station_db]
    stations_ids = [s[0] for s in station_db]
    available_slots = {}

    curr_time = start_time
    duration_offset = duration['duration'] % 60
    if curr_time.minute > duration_offset:
        curr_time = curr_time.replace(minute=0, hour=curr_time.hour+1)
    else:
        curr_time = curr_time.replace(minute=duration_offset)

    while curr_time < end_time:
        available_slots[curr_time] = list(stations_ids)
        curr_time = curr_time + datetime.timedelta(minutes=duration['duration'])

    for req in requests:
        req_start_time = req['start_time']
        req_end_time = req['end_time']
        req_slot_id = req['slot_id']
        curr_time = req_start_time
        while curr_time <= req_end_time:
            if curr_time in available_slots.keys():
                slot_stations = available_slots[curr_time]
                if req_slot_id in slot_stations:
                    slot_stations.remove(req_slot_id)
                    available_slots[curr_time] = slot_stations
                    if len(slot_stations) == 0:
                        available_slots.pop(curr_time)
                        print("No available stations for slot {}".format(curr_time))
            curr_time = curr_time + datetime.timedelta(minutes=duration['duration'])

    return render_template('request/schedule.html', slots=available_slots, duration=duration_id, cost=est_cost)


@bp.route('/request', methods=('GET', 'POST'))
@login_required
def request_page():
    if request.method == 'POST':
        duration = request.form['duration']
        start_date = request.form['start_date']
        error = None

        if not start_date:
            error = 'No start date supplied'

        if error is not None:
            flash(error, 'error')
        else:
            return redirect(url_for('request.schedule', req_duration=duration, req_start=start_date))

    db = get_db()
    durations_db = db.execute(
        'SELECT *'
        ' FROM durations'
        ' ORDER BY duration ASC'
    ).fetchall()

    user_credits = g.user['current_credits']

    durations = {}
    for d in durations_db:
        dur = int(d['duration'])
        cost_w = float(d['cost_weight'])
        cost = int(float(dur) * cost_w)
        has_credit = cost <= user_credits
        durations[d['id']] = {'name': d['name'], 'duration': dur, 'cost': cost, 'id': d['id'], 'has_credit': has_credit}

    return render_template('request/request.html', durations=durations_db)


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
            'SELECT r.id, start_time, end_time, slot_id'
            ' FROM requests r JOIN slots s on r.slot_id = s.id'
            ' WHERE ((? BETWEEN start_time AND end_time) OR'
            ' (? BETWEEN start_time AND end_time)) AND r.slot_id == ?'
            ' ORDER BY start_time ASC', [start_time, end_time, curr_station]
        ).fetchall()

    if len(requests) > 0:
        return redirect(url_for('request.index'))  # TODO: show error

    # Insert the request into the requests table

    available_station = stations[station_index]

    db.execute(
        'INSERT INTO requests (requester_id, start_time, end_time, slot_id, duration, status)'
        ' VALUES (?, ?, ?, ?, ? ,?)',
        (g.user['id'], start_time, end_time, available_station, duration, 'pending')
    )
    db.commit()
    flash("Added request for {} minutes @ {} on {}".format(duration, available_station, start_time))
    return redirect(url_for('request.index'))


def get_request(id, check_author=True):
    req = get_db().execute(
        'SELECT r.id, slot_id, start_time, created, requester_id, username, r.status AS req_status,'
        ' st.name AS station_name, sc.code AS station_code'
        ' FROM requests r'
        ' LEFT JOIN user u ON r.requester_id = u.id'
        ' LEFT JOIN slots sl ON r.slot_id = sl.id'
        ' LEFT JOIN stations st on sl.station_id = st.id'
        ' LEFT JOIN station_code sc on st.id = sc.station_id'
        ' WHERE r.id = ?',
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
            flash(error, "error")
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


@bp.route('/<int:id>/start', methods=('GET', 'POST'))
@login_required
def start(id):
    r = get_request(id)
    u = g.user

    # Verify that the request started is by current user
    if r['requester_id'] != u['id']:
        flash("Invalid request for user", 'error')
        return redirect(url_for('request.index'))

    if r['req_status'] != 'notify':
        flash("Request is not yet active", 'error')
        return redirect(url_for('request.index'))

    if request.method == 'POST':
        code_json = request.get_json()
        print("Trying to verify request {}: user code {} vs station code {}".format(r['id'], code_json['code'], r['station_code']))
        if r['station_code'] == code_json['code']:
            print("Codes match!")
            return redirect(url_for('request.charging', id=id))
        else:
            print("Codes do not match!")
            flash("Invalid code", 'error')
            return redirect(url_for('request.index'))

    return render_template('request/start.html', station_name=r['station_name'])


@bp.route('/<int:id>/charging', methods=('GET', 'POST'))
@login_required
def charging(id):

    return render_template('request/charging.html')

