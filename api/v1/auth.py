import jwt
import secrets
import hashlib
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.security import check_password_hash

bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

TOKEN_EXPIRY_HOURS = 8
REFRESH_EXPIRY_DAYS = 30


def _get_secret():
    return current_app.config.get('SECRET_KEY', 'dev-secret-change-in-prod')


def _get_jwk():
    return secrets.token_hex(16)


def _verify_password(plain, stored):
    if stored.startswith('$2b$') or stored.startswith('$2a$'):
        return check_password_hash(stored, plain)
    return hashlib.sha256(plain.encode()).hexdigest() == stored


def generate_token(usuario_id, rol, slug, expires_in=None):
    if expires_in is None:
        expires_in = TOKEN_EXPIRY_HOURS * 3600
    now = int(time.time())
    payload = {
        'sub': str(usuario_id),
        'rol': rol,
        'slug': slug,
        'iat': now,
        'exp': now + expires_in,
        'jti': secrets.token_hex(16),
    }
    return jwt.encode(payload, _get_secret(), algorithm='HS256')


def generate_refresh_token(usuario_id, rol, slug):
    payload = {
        'sub': str(usuario_id),
        'rol': rol,
        'slug': slug,
        'type': 'refresh',
        'iat': int(time.time()),
        'exp': int(time.time()) + REFRESH_EXPIRY_DAYS * 86400,
        'jti': secrets.token_hex(16),
    }
    return jwt.encode(payload, _get_secret(), algorithm='HS256')


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        if not token:
            return jsonify({'error': 'Token requerido', 'code': 'AUTH_REQUIRED'}), 401
        try:
            data = jwt.decode(token, _get_secret(), algorithms=['HS256'])
            if data.get('type') == 'refresh':
                return jsonify({'error': 'Use un token de acceso, no de refresco', 'code': 'INVALID_TOKEN_TYPE'}), 401
            g.api_usuario_id = int(data['sub'])
            g.api_rol = data['rol']
            g.api_slug = data['slug']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expirado', 'code': 'TOKEN_EXPIRED'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token inválido', 'code': 'INVALID_TOKEN'}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            if g.api_rol not in roles:
                return jsonify({'error': 'Permiso denegado', 'code': 'FORBIDDEN'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


@bp.route('/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    usuario = data.get('usuario', '')
    password = data.get('password', '')
    slug = data.get('slug', '')
    if not usuario or not password or not slug:
        return jsonify({'error': 'usuario, password y slug requeridos', 'code': 'MISSING_FIELDS'}), 400

    from flask_app import conectar, verificar_pw
    conn = conectar(slug)
    try:
        roles_to_check = [
            ('rector', 'rectores', 'rector_id'),
            ('authority', 'directoras', 'directora_id'),
            ('teacher', 'profesores', 'profesor_id'),
            ('student', 'alumnos', 'alumno_id'),
        ]
        import sqlite3
        for role, table, id_key in roles_to_check:
            try:
                row = conn.execute(
                    f"SELECT id, password, activo FROM {table} WHERE usuario=?",
                    (usuario,)
                ).fetchone()
            except sqlite3.OperationalError:
                continue
            if row:
                if not row['activo']:
                    return jsonify({'error': 'Usuario inactivo', 'code': 'INACTIVE_USER'}), 403
                if not verificar_pw(password, row['password']):
                    return jsonify({'error': 'Credenciales inválidas', 'code': 'INVALID_CREDENTIALS'}), 401
                token = generate_token(row['id'], role, slug)
                refresh = generate_refresh_token(row['id'], role, slug)
                return jsonify({
                    'token': token,
                    'refresh_token': refresh,
                    'usuario_id': row['id'],
                    'rol': role,
                    'slug': slug,
                    'expires_in': TOKEN_EXPIRY_HOURS * 3600,
                })
        return jsonify({'error': 'Usuario no encontrado', 'code': 'USER_NOT_FOUND'}), 404
    finally:
        conn.close()


@bp.route('/auth/refresh', methods=['POST'])
def api_refresh():
    data = request.get_json(silent=True) or {}
    refresh_token = data.get('refresh_token', '')
    if not refresh_token:
        return jsonify({'error': 'refresh_token requerido', 'code': 'MISSING_FIELDS'}), 400
    try:
        payload = jwt.decode(refresh_token, _get_secret(), algorithms=['HS256'])
        if payload.get('type') != 'refresh':
            return jsonify({'error': 'Token inválido', 'code': 'INVALID_TOKEN'}), 401
        token = generate_token(int(payload['sub']), payload['rol'], payload['slug'])
        return jsonify({'token': token, 'expires_in': TOKEN_EXPIRY_HOURS * 3600})
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Refresh token expirado', 'code': 'REFRESH_EXPIRED'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Refresh token inválido', 'code': 'INVALID_TOKEN'}), 401


@bp.route('/auth/me', methods=['GET'])
@token_required
def api_me():
    return jsonify({
        'usuario_id': g.api_usuario_id,
        'rol': g.api_rol,
        'slug': g.api_slug,
    })


@bp.route('/health', methods=['GET'])
def api_health():
    return jsonify({'status': 'ok', 'version': '1.0.0', 'timestamp': datetime.now(timezone.utc).isoformat()})


@bp.route('/espec', methods=['GET'])
def api_openapi_spec():
    return jsonify(_OPENAPI_SPEC)


_OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "LUMINI API v1",
        "description": "API REST del Sistema de Gestión Escolar LUMINI. Proporciona acceso programático a estudiantes, profesores, cursos, notas, asistencia y más.",
        "version": "1.0.0",
        "contact": {"name": "LUMINI Team", "url": "https://lumini.app"}
    },
    "servers": [
        {"url": "/api/v1", "description": "API v1"}
    ],
    "components": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT"
            }
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "error": {"type": "string"},
                    "code": {"type": "string"}
                }
            },
            "TokenResponse": {
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                    "refresh_token": {"type": "string"},
                    "usuario_id": {"type": "integer"},
                    "rol": {"type": "string", "enum": ["teacher", "student", "rector", "authority"]},
                    "slug": {"type": "string"},
                    "expires_in": {"type": "integer"}
                }
            },
            "LoginRequest": {
                "type": "object",
                "required": ["usuario", "password", "slug"],
                "properties": {
                    "usuario": {"type": "string"},
                    "password": {"type": "string"},
                    "slug": {"type": "string"}
                }
            },
            "Student": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "nombre": {"type": "string"},
                    "curso": {"type": "string"},
                    "jornada": {"type": "string"},
                    "email_acudiente": {"type": "string"},
                    "activo": {"type": "boolean"}
                }
            }
        }
    },
    "paths": {
        "/auth/login": {
            "post": {
                "tags": ["Autenticación"],
                "summary": "Iniciar sesión",
                "description": "Autentica un usuario y devuelve tokens JWT.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/LoginRequest"}
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Login exitoso",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TokenResponse"}
                            }
                        }
                    },
                    "401": {"description": "Credenciales inválidas"},
                    "404": {"description": "Institución no encontrada"}
                }
            }
        },
        "/auth/refresh": {
            "post": {
                "tags": ["Autenticación"],
                "summary": "Refrescar token",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "refresh_token": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "Nuevo token generado"}
                }
            }
        },
        "/auth/me": {
            "get": {
                "tags": ["Autenticación"],
                "summary": "Información del usuario autenticado",
                "security": [{"BearerAuth": []}],
                "responses": {
                    "200": {"description": "Datos del usuario"}
                }
            }
        },
        "/health": {
            "get": {
                "tags": ["Sistema"],
                "summary": "Verificar estado de la API",
                "responses": {
                    "200": {"description": "API funcionando"}
                }
            }
        },
        "/students": {
            "get": {
                "tags": ["Estudiantes"],
                "summary": "Listar estudiantes",
                "security": [{"BearerAuth": []}],
                "parameters": [
                    {"name": "slug", "in": "query", "required": True, "schema": {"type": "string"}},
                    {"name": "curso", "in": "query", "schema": {"type": "string"}},
                    {"name": "activo", "in": "query", "schema": {"type": "boolean"}},
                    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1},
                     "description": "Número de página"},
                    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 50,
                      "maximum": 200}, "description": "Resultados por página"},
                ],
                "responses": {
                    "200": {
                        "description": "Lista de estudiantes",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/Student"}
                                        },
                                        "page": {"type": "integer"},
                                        "per_page": {"type": "integer"},
                                        "total": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

# Import routes module to register data API endpoints on this blueprint
from . import routes  # noqa: E402, F401
