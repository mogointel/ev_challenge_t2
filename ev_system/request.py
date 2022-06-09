import datetime

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from ev_system.auth import login_required
from ev_system.db import get_db

bp = Blueprint('request', __name__)

@bp.route('/')
def index():
    return render_template('request/index.html')


@bp.route('/schedule')
def schedule():
    db = get_db()
    duration = request.args.get('req_duration', None)
    curr_time = datetime.datetime(year=2022, month=6, day=8, hour=10,
                                  minute=0)  # datetime.datetime.now() TODO: remove this comment
    turn_around = 30 # TODO: get from config
    start_time = request.args.get('req_start', None)
    end_time = datetime.datetime.strptime(start_time, '%Y-%m-%d, %HH:%MM').replace(hour=18, minute=0)
    requests = db.execute(
        'SELECT p.id, start_time, end_time, station_id'
        ' FROM requests p JOIN slots s ON p.station_id = s.id'
        ' WHERE p.start_time >= ?'
        ' AND p.end_time < ?'        
        ' ORDER BY start_time ASC', (start_time, end_time)
    ).fetchall()
    station_ids = db.execute(
        'SELECT s.id FROM slots s'
    ).fetchall()
    stations = list(station_ids)
    available_slots = {}

    # duration_offset = duration % 60
    # if curr_time.minute > duration_offset:
    #     curr_time.hour = curr_time.hour + 1
    while curr_time < end_time:
        available_slots[curr_time] = stations
        curr_time = curr_time + datetime.timedelta(minutes=duration)

    for req in requests:
        req_time = datetime.datetime.strptime(req['start_time'], '%Y-%m-%d, %HH:%MM')
        req_station_id = req['station_id']
        if req_time in available_slots.keys():
            slot_stations = available_slots[req_time]
            if req_station_id in slot_stations:
                slot_stations.remove(req_station_id)
                available_slots[req_time] = slot_stations



    return render_template('request/schedule.html', requests=available_slots)


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        duration = request.form['duration']
        start_date = request.form['start_date']
        error = None

        if not start_date:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            # db = get_db()
            # db.execute(
            #     'INSERT INTO requests (title, body, author_id)'
            #     ' VALUES (?, ?, ?)',
            #     (title, body, g.user['id'])
            # )
            # db.commit()
            return redirect(url_for('request.schedule', req_duration=duration, req_start=start_date))

    return render_template('request/create.html')


def get_request(id, check_author=True):
    req = get_db().execute(
        'SELECT p.id, station_id, start_time, created, requester_id, username'
        ' FROM requests p JOIN user u ON p.requester_id = u.id'
        ' WHERE p.id = ?',
        (id,)
    ).fetchone()

    if req is None:
        abort(404, f"Request id {id} doesn't exist.")

    if check_author and req['author_id'] != g.user['id']:
        abort(403)

    return req


@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    req = get_request(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET title = ?, body = ?'
                ' WHERE id = ?',
                (title, body, id)
            )
            db.commit()
            return redirect(url_for('request.index'))

    return render_template('request/update.html', post=req)


@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_request(id)
    db = get_db()
    db.execute('DELETE FROM post WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('request.index'))