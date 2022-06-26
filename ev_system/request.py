import datetime
import time

import flask

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
        'SELECT r.id, start_time, end_time, created, position, requester_id, username, estimated_cost, s.status as slot_status'
        ' FROM requests r join user u on r.requester_id = u.id join slots s on r.slot_id = s.id'
        ' WHERE requester_id == ? AND r.status == \'notify\''
        ' ORDER BY start_time ASC', [g.user['id']]
    ).fetchone()

    if requests is not None:
        return render_template('request/notify.html', requests=requests, server_now=server_time.server_now())

    requests = db.execute(
        'SELECT r.id, start_time, end_time, created, position, requester_id, username, estimated_cost, duration, b.name as building'
        ' FROM requests r join user u on r.requester_id = u.id join slots s on r.slot_id = s.id join building b on s.building_id = b.id'
        ' WHERE requester_id == ? AND r.status == \'pending\''
        ' ORDER BY start_time ASC', [g.user['id']]
    ).fetchall()

    return render_template('request/all_request.html', requests=requests)


def compute_cost(cost_id, curr_cost):
    cost = curr_cost

    if cost_id is not None:
        db = get_db()
        cost_db = db.execute(
            'SELECT type, value'
            ' FROM extra_cost'
            ' WHERE id = ?', [cost_id]
        ).fetchone()

        if cost_db['type'] == 'percent':
            cost += int(float(curr_cost) * (float(cost_db['value'])/100.0))
        elif cost_db['type'] == 'fixed':
            cost += int(cost_db['value'])

    return cost


def compute_extra_cost(station_db, est_cost):
    station_cost_id = station_db['station_cost']
    slot_cost_id = station_db['slot_cost']

    cost = est_cost

    cost = compute_cost(station_cost_id, cost)
    cost = compute_cost(slot_cost_id, cost)

    return cost


@bp.context_processor
def comp_cost():
    def _comp_cost(station_db, est_cost):
        return compute_extra_cost(station_db, est_cost)
    return dict(comp_cost=_comp_cost)


@bp.context_processor
def has_budget():
    def _has_budget(cost):
        has = int(g.user['current_credits']) >= cost
        return has
    return dict(has_budget=_has_budget)


@bp.route('/schedule')
@login_required
def schedule():
    duration_id = int(request.args.get('req_duration', None))
    db = get_db()
    duration_db = db.execute(
        'SELECT *'
        ' FROM durations'
        ' WHERE id = ?', [duration_id]
    ).fetchone()

    if duration_db is None:
        flash("Unsupported duration", "error")
        return redirect(url_for('request.request'))

    duration = {'duration': int(duration_db['duration']), 'cost_weight': float(duration_db['cost_weight'])}
    est_cost = int(float(duration['duration']) * duration['cost_weight'])

    turn_around = 30 # TODO: get from config
    time_offset = request.args.get('offset', None)

    if time_offset is not None:
        time_offset = int(time_offset)
        start_time = datetime.datetime.strptime(request.args.get('req_start', None), '%Y-%m-%d %H:%M:%S')
        start_time = start_time.replace(hour=8, minute=0) + datetime.timedelta(days=time_offset)
    else:
        start_time = datetime.datetime.strptime(request.args.get('req_start', None), '%Y-%m-%dT%H:%M')

    curr_time = server_time.server_now()

    if start_time < curr_time:
        start_time = curr_time
    if start_time > (curr_time + datetime.timedelta(days=7)):
        start_time = (curr_time + datetime.timedelta(days=7))

    end_time = start_time.replace(hour=18, minute=0)
    requests = db.execute(
        'SELECT r.id, start_time, end_time, slot_id'
        ' FROM requests r JOIN slots s on r.slot_id = s.id'
        ' WHERE (start_time BETWEEN ? AND ?) or (end_time BETWEEN ? AND ?) '
        ' ORDER BY start_time ASC', [start_time, end_time, start_time, end_time]
    ).fetchall()

    site_id = int(request.args.get('site_id', -1))
    bldg_query = ""
    if site_id >= 0:
        bldg_name = request.args.get('bldg_name', None)
        if bldg_name != "-1":
            bldg_query = " AND b.name = '" + bldg_name + "'"
        else:
            bldg_query = " AND b.site_id = " + str(site_id)

    station_db = db.execute(
        'SELECT sl.id, sl.position as name, sl.extra_cost_id as slot_cost, st.extra_cost_id as station_cost,'
        ' b.name as building'
        ' FROM slots sl JOIN stations st on sl.station_id = st.id JOIN building b on sl.building_id = b.id'
        ' WHERE (st.status != \'disabled\') AND (sl.status != \'disabled\')'
        '       AND (? BETWEEN min_slot_duration and max_slot_duration)' + bldg_query,
        [duration['duration']]
    ).fetchall()

    stations = {}
    stations_db = {}
    stations_ids = []
    for s in station_db:
        stations[s[0]] = s
        stations_ids.append(s[0])

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

    return render_template('request/schedule.html', slots=available_slots, duration=duration_id, cost=est_cost,
                           curr_budget=int(g.user['current_credits']), station_data=stations, day=start_time)


@bp.route('/request', methods=('GET', 'POST'))
@login_required
def request_page():
    if request.method == 'POST':
        duration = request.form['duration']
        start_date = request.form['start_date']
        bldg = request.form['bldg']
        site = request.form['site']
        error = None

        if not start_date:
            error = 'No start date supplied'

        if error is not None:
            flash(error, 'error')
        else:
            return redirect(url_for('request.schedule', req_duration=duration, req_start=start_date, bldg_name=bldg, site_id=site))

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

    sites_db = db.execute(
        'SELECT *'
        ' FROM site'
        ' ORDER BY name ASC'
    ).fetchall()

    bldgs_db = db.execute(
        'SELECT *'
        ' FROM building'
        ' ORDER BY name ASC'
    ).fetchall()

    bldgs = {}
    curr_bldgs = []
    for bldg in bldgs_db:
        curr_bldgs.append(bldg['name'])
    bldgs[-1] = curr_bldgs

    for site in sites_db:
        curr_bldgs = []
        for bldg in bldgs_db:
            if bldg['site_id'] == site['id']:
                curr_bldgs.append(bldg['name'])
        bldgs[site['id']] = curr_bldgs

    return render_template('request/request.html', durations=durations_db, sites=sites_db, buildings=bldgs)


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    start_time = datetime.datetime.strptime(request.args['start_time'], '%Y-%m-%d %H:%M:%S')
    station = int(request.args['stations'])
    duration_id = int(request.args['duration'])
    est_cost = int(request.args['cost'])
    turn_around = 30  # TODO: get from config


    db = get_db()

    duration_db = db.execute(
        'SELECT duration'
        ' FROM durations'
        ' WHERE id = ?', [duration_id]
    ).fetchone()
    duration = int(duration_db['duration'])

    # Make sure that at least one of the stations does not have a conflict
    station_index = -1
    available_station = -1

    end_time = start_time + datetime.timedelta(minutes=(duration + turn_around))

    station_index += 1
    curr_station = int(station)
    requests = db.execute(
        'SELECT r.id, start_time, end_time, slot_id'
        ' FROM requests r JOIN slots s on r.slot_id = s.id'
        ' WHERE ((? BETWEEN start_time AND end_time) OR'
        ' (? BETWEEN start_time AND end_time)) AND r.slot_id == ?'
        ' ORDER BY start_time ASC', [start_time, end_time, curr_station]
    ).fetchall()

    if len(requests) > 0:
        flash("Slot {} is not available".format(curr_station), 'error')
        return redirect(url_for('request.index'))

    # Insert the request into the requests table

    available_station = station

    # Update request
    db.execute(
        'INSERT INTO requests (requester_id, start_time, end_time, slot_id, duration, status, estimated_cost)'
        ' VALUES (?, ?, ?, ?, ? ,?, ?)',
        (g.user['id'], start_time, end_time, available_station, duration, 'pending', est_cost)
    )

    # Update user
    db.execute(
        'UPDATE user'
        ' SET current_credits = ?'
        ' WHERE id = ?', (int(g.user['current_credits'])-est_cost, g.user['id'])
    )
    db.commit()

    flash("Added request for {} minutes @ {} on {}".format(duration, available_station, start_time))
    return redirect(url_for('request.index'))


def get_request(id, check_author=True):
    req = get_db().execute(
        'SELECT r.id, slot_id, start_time, end_time, duration, requester_id, username, r.status AS req_status,'        
        ' st.name AS station_name, sc.code AS station_code, slot_id, sl.station_id, estimated_cost'
        ' FROM requests r'
        ' LEFT JOIN user u ON r.requester_id = u.id'
        ' LEFT JOIN slots sl ON r.slot_id = sl.id'
        ' LEFT JOIN stations st on sl.station_id = st.id'
        ' LEFT JOIN station_code sc on st.id = sc.station_id'
        ' WHERE r.id = ?',
        (id,)
    ).fetchone()

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

    req = db.execute(
        'SELECT estimated_cost'
        ' FROM requests'
        ' WHERE id = ?', [id]
    ).fetchone()

    new_credits = int(g.user['current_credits']) + int(req['estimated_cost'])

    db.execute(
        'DELETE FROM requests'
        ' WHERE id = ?',
        [id]
    )

    db.execute(
        'UPDATE user'
        ' SET current_credits = ?'
        ' WHERE id = ?', (new_credits, g.user['id'])
    )

    db.commit()
    return redirect(url_for('request.index'))


@bp.route('/<int:id>/start', methods=('GET', 'POST'))
@login_required
def start(id):
    r = get_request(id)
    u = g.user

    if r is None:
        print("Failed to load start for request id {}".format(id))
        flash("Could not find request {}".format(id), 'error')
        return redirect(url_for('request.index'))

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
        if True: #r['station_code'] == code_json['code']:
            db = get_db()
            print("Codes match!")
            # TODO: handle request start DB
            # Update request status
            # Move request from pending to active requests table
            #
            db.execute(
                'UPDATE requests'
                ' SET status = ?'
                ' WHERE id = ?', ['charging', id]
            )

            db.execute(
                'UPDATE slots'
                ' SET status = ?'
                ' WHERE id = ?', ['occupied', r['slot_id']]
            )

            db.execute(
                'UPDATE stations'
                ' SET status = ?'
                ' WHERE id = ?', ['charging', r['station_id']]
            )

            db.commit()

            return url_for('request.charging', id=id)
        else:
            print("Codes do not match!")
            flash("Invalid code", 'error')

    return render_template('request/start.html', station_name=r['station_name'])


@bp.route('/<int:id>/charging', methods=('GET',))
@login_required
def charging(id):
    r = get_request(id)
    u = g.user

    if r is None:
        print("Failed to load charging for request id {}".format(id))
        flash("Could not find request {}".format(id), 'error')
        return redirect(url_for('request.index'))

    if r['req_status'] != 'charging':
        flash("Request is not charging", 'error')
        return redirect(url_for('request.index'))

    start_time = r['start_time']
    duration = int(r['duration'])
    charge_end = start_time + datetime.timedelta(minutes=duration)

    if charge_end <= server_time.server_now():
        db = get_db()

        db.execute(
            'UPDATE requests'
            ' SET status = ?'
            ' WHERE id = ?', ['evacuate', r['id']]
        )

        db.commit()

        return redirect(url_for('request.notify_end'))

    return render_template('request/charging.html', requests=r, charge_end=charge_end, server_now=server_time.server_now())


@bp.route('/<int:id>/notify_end', methods=('GET',))
@login_required
def notify_end(id):
    r = get_request(id)
    u = g.user

    if r is None:
        print("Failed to load charging for request id {}".format(id))
        flash("Could not find request {}".format(id), 'error')
        return redirect(url_for('request.index'))

    if r['req_status'] != 'evacuate':
        flash("Charging still active", 'error')
        return redirect(url_for('request.charging'))

    end_time = r['end_time']
    duration = 30
    charge_end = end_time + datetime.timedelta(minutes=duration)

    # if charge_end >= server_time.server_now():
    #     return redirect(url_for('request.notify_end'))

    return render_template('request/notify_end.html', requests=r, charge_end=charge_end,
                           server_now=server_time.server_now())


@bp.route('/<int:id>/stop', methods=('GET', 'POST'))
@login_required
def stop(id):
    r = get_request(id)
    u = g.user

    if r is None:
        print("Failed to load stop for request id {}".format(id))
        flash("Could not find request {}".format(id), 'error')
        return redirect(url_for('request.index'))

    # Verify that the request started is by current user
    if r['requester_id'] != u['id']:
        flash("Invalid request for user", 'error')
        return redirect(url_for('request.index'))

    if r['req_status'] != 'charging':
        flash("Request is not charging", 'error')
        return redirect(url_for('request.index'))

    if request.method == 'POST':
        code_json = request.get_json()
        print("Trying to verify request stop {}: user code {} vs station code {}".format(r['id'], code_json['code'], r['station_code']))
        if True: #r['station_code'] == code_json['code']:
            print("Codes match!")
            # TODO: handle request start DB
            # Update request status
            # Move request from active to finished
            # Update actual end time
            # Calculate power consumption
            # Calculate final credits (add penalty)

            final_cost = r['estimated_cost']
            penalty = 0

            actual_end = server_time.server_now()
            total_duration_td = actual_end - r['start_time']
            total_duration = int(total_duration_td.total_seconds() / 60)
            if actual_end > r['end_time']:
                minutes_late_td = actual_end - r['end_time']
                minutes_late = int(minutes_late_td.total_seconds() / 60)
                penalty = int(minutes_late / 10)
                print("Request {} was {} minutes late".format(id, minutes_late))

            final_cost += penalty

            db = get_db()

            station = db.execute(
                'SELECT power_per_hour'
                ' FROM stations'
                ' WHERE id = ?', [r['station_id']]
            ).fetchone()
            power_est = round(station['power_per_hour'] * (total_duration / 60), 0)

            db.execute(
                'UPDATE requests'
                ' SET status = ?'
                ' WHERE id = ?', ['finished', id]
            )

            db.execute(
                'UPDATE slots'
                ' SET status = ?'
                ' WHERE id = ?', ['free', r['slot_id']]
            )

            db.execute(
                'UPDATE stations'
                ' SET status = ?'
                ' WHERE id = ?', ['idle', r['station_id']]
            )

            # Place request in finished_requests table
            db.execute(
                'INSERT INTO finished_requests (request_id, start_time, power_est, station_id, user_name, actual_cost)'
                ' VALUES (?, ?, ?, ?, ?, ?)',
                (id, r['start_time'], power_est, r['station_id'], r['username'], final_cost)
            )

            db.commit()
            end_msg = "Finished charging\nat {}\nfor {} minutes".format(r['station_name'], total_duration)
            flash(end_msg)

            return url_for('request.index')
        else:
            print("Codes do not match!")
            flash("Invalid code", 'error')

    return render_template('request/stop.html', station_name=r['station_name'])

