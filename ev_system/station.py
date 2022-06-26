from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

from ev_system.auth import login_required
from ev_system.db import get_db

bp = Blueprint('station', __name__)


def get_station(id):
    s = get_db().execute(
        'SELECT name, code, status'
        ' FROM stations s LEFT JOIN station_code sc ON s.id = sc.station_id'
        ' WHERE s.id = ?',
        (id,)
    ).fetchone()

    if s is None:
        abort(404, f"Request id {id} doesn't exist.")

    return s


@bp.route('/<int:id>/station', methods=["GET"])
def station(id):
    s = get_station(id)

    code = s['code']
    if code is None:
        code = "NO CODE"

    name = s['name']

    status = s['status']

    return render_template('station/index.html', station_name=name, station_code=code, station_status=status)



