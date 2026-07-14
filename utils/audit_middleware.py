"""
Enterprise Audit Middleware.

Automatically logs all significant actions across the system:
logins, logouts, CRUD operations, exports, permission changes.

Tracks: IP, user agent, device, browser, timestamp.

Usage: call `log_action` from any route handler.
Does NOT use Flask before_request hooks to avoid breaking existing behavior.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

ACTION_CATEGORIES = {
    'auth': ['login', 'logout', 'login_failed', 'password_change', '2fa_setup', '2fa_verify'],
    'crud': ['create', 'update', 'delete', 'restore'],
    'academic': ['grade_save', 'grade_edit', 'attendance_save', 'evaluation_save'],
    'export': ['pdf_download', 'excel_export', 'csv_export', 'report_generate'],
    'admin': ['config_change', 'user_create', 'user_deactivate', 'permission_change'],
    'signature': ['document_sign', 'document_verify'],
    'security': ['ip_blocked', 'suspicious_activity', 'rate_limit_exceeded'],
}


@dataclass
class AuditEntry:
    slug: str
    usuario_id: int
    usuario_tipo: str
    accion: str
    categoria: str
    descripcion: str
    tabla: Optional[str] = None
    registro_id: Optional[int] = None
    valor_anterior: Optional[Dict] = None
    valor_nuevo: Optional[Dict] = None
    ip: str = ''
    user_agent: str = ''
    dispositivo: str = ''
    navegador: str = ''
    sesion_id: str = ''
    nivel: str = 'info'


def _parse_device(user_agent: str) -> str:
    ua = user_agent.lower()
    if 'mobile' in ua or 'iphone' in ua or 'android' in ua:
        return 'mobile'
    if 'tablet' in ua or 'ipad' in ua:
        return 'tablet'
    return 'desktop'


def _parse_browser(user_agent: str) -> str:
    ua = user_agent.lower()
    if 'edg' in ua or 'edge' in ua:
        return 'edge'
    if 'chrome' in ua:
        return 'chrome'
    if 'firefox' in ua:
        return 'firefox'
    if 'safari' in ua:
        return 'safari'
    return 'unknown'


def log_action(
    conn,
    slug: str,
    usuario_id: int,
    usuario_tipo: str,
    accion: str,
    descripcion: str,
    tabla: Optional[str] = None,
    registro_id: Optional[int] = None,
    valor_anterior: Optional[Dict] = None,
    valor_nuevo: Optional[Dict] = None,
    ip: str = '',
    user_agent: str = '',
    nivel: str = 'info',
) -> int:
    """Log an action to the enterprise audit log."""
    categoria = 'admin'
    for cat, actions in ACTION_CATEGORIES.items():
        if accion in actions:
            categoria = cat
            break

    entry = AuditEntry(
        slug=slug, usuario_id=usuario_id, usuario_tipo=usuario_tipo,
        accion=accion, categoria=categoria, descripcion=descripcion,
        tabla=tabla, registro_id=registro_id,
        valor_anterior=valor_anterior, valor_nuevo=valor_nuevo,
        ip=ip, user_agent=user_agent,
        dispositivo=_parse_device(user_agent),
        navegador=_parse_browser(user_agent),
        nivel=nivel,
    )

    conn.execute(
        '''INSERT INTO enterprise_audit_log
           (slug, usuario_id, usuario_tipo, accion, categoria, descripcion,
            tabla, registro_id, valor_anterior, valor_nuevo,
            ip, user_agent, dispositivo, navegador, nivel)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            entry.slug, entry.usuario_id, entry.usuario_tipo,
            entry.accion, entry.categoria, entry.descripcion,
            entry.tabla, entry.registro_id,
            json.dumps(entry.valor_anterior) if entry.valor_anterior else None,
            json.dumps(entry.valor_nuevo) if entry.valor_nuevo else None,
            entry.ip, entry.user_agent, entry.dispositivo, entry.navegador,
            entry.nivel,
        )
    )
    conn.commit()
    return conn.execute('SELECT last_insert_rowid()').fetchone()[0]


def query_audit_log(
    conn, slug: str,
    usuario_id: Optional[int] = None,
    categoria: Optional[str] = None,
    accion: Optional[str] = None,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Query the enterprise audit log with filters and pagination."""
    where = ['slug=?']
    params = [slug]

    if usuario_id is not None:
        where.append('usuario_id=?')
        params.append(usuario_id)
    if categoria:
        where.append('categoria=?')
        params.append(categoria)
    if accion:
        where.append('accion=?')
        params.append(accion)
    if desde:
        where.append('creado>=?')
        params.append(desde)
    if hasta:
        where.append('creado<=?')
        params.append(hasta)

    where_sql = ' AND '.join(where)
    total = conn.execute(
        f'SELECT COUNT(*) FROM enterprise_audit_log WHERE {where_sql}', params
    ).fetchone()[0]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f'SELECT * FROM enterprise_audit_log WHERE {where_sql} '
        f'ORDER BY creado DESC LIMIT ? OFFSET ?',
        params + [per_page, offset]
    ).fetchall()

    return {
        'data': [dict(r) for r in rows],
        'page': page,
        'per_page': per_page,
        'total': total,
    }
