"""
flask_app.py — Entry point.
All logic lives in app/infra/, app/routes/, app/services/.
This file only creates the Flask app, registers blueprints,
and re-exports symbols for test compatibility.
"""

import json
import os
import threading

from dotenv import load_dotenv

_basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(_basedir, '.env'))

from datetime import timedelta

from flask import (  # noqa: F401
    Flask,
    Response,
    abort,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)

from app.logging import get_logger
from config import settings

app = Flask(__name__)
ENV = settings.ENV

logger = get_logger(__name__)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = settings.SEND_FILE_MAX_AGE_DEFAULT
if not settings.SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está definido en .env. Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\"")
app.secret_key = settings.SECRET_KEY
app.permanent_session_lifetime = timedelta(hours=settings.PERMANENT_SESSION_LIFETIME_HOURS)
app.config['SESSION_COOKIE_HTTPONLY'] = settings.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SAMESITE'] = settings.SESSION_COOKIE_SAMESITE
app.config['SESSION_COOKIE_SECURE'] = settings.SESSION_COOKIE_SECURE

if ENV == 'production' and settings.SESSION_COOKIE_SECURE:
    logger.info("Producción — SESSION_COOKIE_SECURE=True, asegúrate de tener HTTPS.")
elif ENV == 'production' and not settings.SESSION_COOKIE_SECURE:
    logger.warning("Producción con SESSION_COOKIE_SECURE=False. Usa HTTPS y establece SESSION_COOKIE_SECURE=true.")

app.config['JSON_AS_ASCII'] = settings.JSON_AS_ASCII
app.config['TEMPLATES_AUTO_RELOAD'] = ENV != 'production'

if ENV == 'production':
    try:
        from flask_compress import Compress
        Compress(app)
        app.config['COMPRESS_ALGORITHM'] = settings.COMPRESS_ALGORITHM
        app.config['COMPRESS_LEVEL'] = settings.COMPRESS_LEVEL
        app.config['COMPRESS_MIN_SIZE'] = settings.COMPRESS_MIN_SIZE
    except ImportError:
        pass

@app.template_filter('parse_json')
def parse_json_filter(val):
    try: return json.loads(val) if val else {}
    except Exception: return {}

from app.infra.security import generar_csrf

app.jinja_env.globals['csrf_token'] = generar_csrf

# ── Re-export all infra symbols so imports like `from flask_app import conectar` still work ──
from app.infra.attendance import (  # noqa: F401
    COLORES_ASISTENCIA,
    ESTADOS_ASISTENCIA,
    _asistencia_alertas,
    _asistencia_stats,
)
from app.infra.audit import audit_log, auditar_nota, periodo_cerrado  # noqa: F401
from app.infra.config import (  # noqa: F401
    ADMIN_PASSWORD,
    DB_FOLDER,
    EMAIL_ORIGEN,
    JORNADAS,
    LOGO_FOLDER,
    MASTER_DB,
    MATERIAS,
    PREGUNTAS_SECRETAS,
    SCHEMA_VERSION,
    SENDGRID_API_KEY,
)
from app.infra.dashboard import (  # noqa: F401
    _dashboard_profesor_data,
    _dashboard_rector_data,
    _dashboard_student_grades,
    _estadisticas_desc,
)
from app.infra.database import (  # noqa: F401
    _CACHE_TTL,
    MIGRACIONES,
    _cache,
    _cache_get,
    _cache_invalidate,
    _cache_lock,
    _cache_set,
    _ejecutar_migraciones,
    _migrar_v6,
    _migrar_v7,
    _migrar_v8,
    _migrar_v9,
    _migrar_v10,
    _migrar_v11,
    _migrar_v12,
    _migrar_v13,
    _migrar_v14,
    _migrar_v15,
    _migrar_v16,
    _migrar_v17,
    _migrar_v18,
    _migrar_v19,
    _migrar_v20,
    _recrear_si_unique_incorrecto,
    conectar,
    conectar_master,
    config_get,
    db_path,
    get_codigo_registro,
    get_colegio,
    init_db,
    init_master_db,
    migrar_db,
)
from app.infra.excel import _excel_armar_wb  # noqa: F401
from app.infra.grades import (  # noqa: F401
    _promedio_ponderado,
    _promedio_simple,
    calcular_nota_final_estudiante,
    calcular_stats_curso,
    calcular_stats_estudiante,
)
from app.infra.helpers import (  # noqa: F401
    get_cursos_cache,
    get_cursos_profesor,
    get_directora,
    get_jornadas_cache,
    get_materias_cache,
    get_materias_profesor,
    get_profesor,
    get_rector,
    get_sesion_jornada_materia,
    get_usuario_actual,
    require_colegio,
    require_rector_principal,
)
from app.infra.mail import enviar_correo  # noqa: F401
from app.infra.notifications import (  # noqa: F401
    comunicaciones_pendientes,
    crear_notificacion,
    generar_destinatarios,
    notificaciones_no_leidas,
)
from app.infra.pdf import generar_pdf_alumno  # noqa: F401
from app.infra.permissions import (  # noqa: F401
    NIVELES_ROL,
    PERMISOS_POR_CODIGO,
    _permisos_para_rol,
    obtener_roles_usuario,
    requiere_permiso,
    tiene_permiso,
)
from app.infra.security import (  # noqa: F401
    _purgar_intentos_antiguos,
    extension_permitida,
    generar_csrf,
    hash_pw,
    ip_bloqueada,
    limpiar_intentos,
    login_intentos,
    necesita_rehash,
    registrar_fallo,
    validar_csrf,
    validar_imagen,
    verificar_pw,
)


# ── Context processors (need app reference, must stay here) ──
@app.context_processor
def inject_theme():
    def accent_css(colegio):
        primary = (colegio and colegio['primary_color']) or '#7C3AED'
        secondary = (colegio and colegio['secondary_color']) or '#6D28D9'
        h = primary.lstrip('#')
        rgb = f'{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}' if len(h) == 6 else '124,58,237'
        return f'--accent:{primary};--accent2:{secondary};--accent-rgb:{rgb};'
    return dict(accent_css=accent_css)

@app.context_processor
def inject_rector_defaults():
    return dict(
        total_estudiantes=0, total_profesores=0, total_cursos=0,
        total_materias=0, total_directoras=0, asistencia_hoy=0, asis_pct_r=0,
    )

# ── Make dirs ──
os.makedirs(settings.DB_FOLDER, exist_ok=True)
os.makedirs(settings.LOGO_FOLDER, exist_ok=True)

if not settings.ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD no está definido en .env. Crea el archivo .env con: ADMIN_PASSWORD=tu_clave")
if not settings.SENDGRID_API_KEY:
    logger.warning("SENDGRID_API_KEY no definido — el envío de correos estará deshabilitado.")

app.config['MAX_CONTENT_LENGTH'] = settings.MAX_CONTENT_LENGTH

# ── Errors, filters, backup ──
from app.backup import programar_backup
from app.filters import register_template_filters
from app.handlers import register_error_handlers

register_error_handlers(app)
register_template_filters(app)

# ── Blueprints ──
try:
    from api.v1.auth import bp as api_v1_bp
    app.register_blueprint(api_v1_bp)
    logger.info("API v1 blueprint registrado.")
except ImportError as e:
    logger.warning(f"No se pudo registrar API v1: {e}")

try:
    from app.routes import (
        admin_bp,
        attendance_bp,
        channels_bp,
        courses_bp,
        directora_bp,
        files_bp,
        notifications_bp,
        observations_bp,
        parent_bp,
        rector_bp,
        student_bp,
        teacher_bp,
    )
    from app.routes.auth import auth_bp
    from app.routes.main_routes import main_bp
    for bp in [rector_bp, directora_bp, admin_bp, parent_bp, student_bp, notifications_bp,
               teacher_bp, main_bp, auth_bp, observations_bp, courses_bp, attendance_bp,
               channels_bp, files_bp]:
        app.register_blueprint(bp)
    logger.info("Blueprints modulares (app/routes/) registrados.")
except ImportError as e:
    logger.warning(f"No se pudieron registrar blueprints modulares: {e}")

# ── Re-exports for test compatibility (symbols not in infra modules) ──
from app.services.channel_service import (  # noqa: F401
    _enriquecer_mensajes_batch,
    agregar_miembro_canal,
    asignar_miembros_auto,
    canales_usuario,
    nombre_usuario_canal,
)

# ── Init ──
init_master_db()
t = threading.Timer(30, lambda: programar_backup(settings.MASTER_DB, settings.DB_FOLDER, logger))
t.daemon = True
t.start()

if __name__ == '__main__':
    _port = settings.PORT
    try:
        from waitress import serve
        logger.info(f'Servidor Waitress en http://0.0.0.0:{_port}')
        serve(app, host='0.0.0.0', port=_port, threads=8)
    except ImportError:
        logger.warning('waitress no instalado. Usando Flask dev server (sin reloader).')
        app.run(host='127.0.0.1', port=_port, debug=(ENV != 'production'), use_reloader=False)
