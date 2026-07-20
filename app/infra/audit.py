import json
import logging
from app.infra.database import conectar

logger = logging.getLogger(__name__)


def periodo_cerrado(slug, periodo):
    conn = conectar(slug)
    row = conn.execute(
        'SELECT estado FROM periodos_estado WHERE periodo=?',
        (periodo,)).fetchone()
    conn.close()
    return row is not None and row['estado'] == 'cerrado'


def audit_log(slug, usuario_id, accion, tabla, registro_id=None, valor_anterior=None, valor_nuevo=None):
    from flask import request as flask_request
    conn = None
    try:
        conn = conectar(slug)
        conn.execute(
            '''INSERT INTO audit_log (usuario_id, accion, tabla, registro_id, valor_anterior, valor_nuevo, ip, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (usuario_id, accion, tabla, registro_id,
             json.dumps(valor_anterior) if valor_anterior else None,
             json.dumps(valor_nuevo) if valor_nuevo else None,
             flask_request.remote_addr,
             flask_request.user_agent.string if flask_request.user_agent else None)
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"[audit] {e}")
    finally:
        if conn:
            conn.close()


def auditar_nota(slug, usuario_id, rol, tipo_accion, tabla, aid, curso, materia, periodo, campo=None, actividad_id=None, registro_id=None, valor_anterior=None, valor_nuevo=None, motivo=None):
    from flask import request as flask_request
    conn = None
    try:
        conn = conectar(slug)
        conn.execute(
            '''INSERT INTO auditoria_notas
               (usuario_id, rol, ip, curso, materia, periodo, tipo_accion, tabla, registro_id, aid, actividad_id, campo, valor_anterior, valor_nuevo, motivo)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (usuario_id, rol, flask_request.remote_addr, curso, materia, periodo,
             tipo_accion, tabla, registro_id, aid, actividad_id, campo,
             json.dumps(valor_anterior) if valor_anterior is not None else None,
             json.dumps(valor_nuevo) if valor_nuevo is not None else None,
             motivo)
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"[auditar_nota] {e}")
    finally:
        if conn:
            conn.close()
