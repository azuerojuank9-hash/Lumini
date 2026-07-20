import os
from flask import Blueprint, render_template, send_from_directory

main_bp = Blueprint('main', __name__)


def _fa():
    import flask_app as fa
    return fa


@main_bp.route('/static/<path:filename>')
def static_files(filename):
    fa = _fa()
    resp = send_from_directory(
        os.path.join(os.path.dirname(fa.__file__), 'static'), filename)
    resp.headers['Cache-Control'] = 'public, max-age=604800, immutable'
    return resp


@main_bp.route("/offline")
def offline():
    return render_template("offline.html")


@main_bp.route("/")
def index():
    fa = _fa()
    conn = fa.conectar_master()
    colegios = conn.execute("SELECT slug, nombre, logo FROM colegios WHERE activo=1 ORDER BY nombre").fetchall()
    conn.close()
    return render_template("index_root.html", colegios=colegios)
