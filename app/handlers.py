from flask import jsonify, render_template, request

from app.exceptions import (
    BusinessError,
    DatabaseError,
    ForbiddenError,
    NotFoundError,
    PermissionError,
    UnauthorizedError,
    ValidationError,
)
from app.logging import get_logger

logger = get_logger(__name__)


def _is_api_request():
    return request.path.startswith('/api/')


def register_error_handlers(app):
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com https://www.datadoghq-browser-agent.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'"
        return response

    @app.errorhandler(400)
    def bad_request(e):
        if _is_api_request():
            return jsonify({'error': 'Solicitud inválida', 'code': 'BAD_REQUEST'}), 400
        return render_template('error.html', codigo=400, mensaje='Solicitud inválida.'), 400

    @app.errorhandler(403)
    def forbidden(e):
        if _is_api_request():
            return jsonify({'error': 'Acceso denegado', 'code': 'FORBIDDEN'}), 403
        return render_template('error.html', codigo=403, mensaje='Acceso denegado.'), 403

    @app.errorhandler(404)
    def not_found(e):
        if _is_api_request():
            return jsonify({'error': 'Página no encontrada', 'code': 'NOT_FOUND'}), 404
        return render_template('error.html', codigo=404, mensaje='Página no encontrada.'), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _is_api_request():
            return jsonify({'error': 'Método no permitido', 'code': 'METHOD_NOT_ALLOWED'}), 405
        return render_template('error.html', codigo=405, mensaje='Método no permitido.'), 405

    @app.errorhandler(413)
    def too_large(e):
        if _is_api_request():
            return jsonify({'error': 'Archivo demasiado grande. Máximo: 2 MB', 'code': 'PAYLOAD_TOO_LARGE'}), 413
        return render_template('error.html', codigo=413,
                               mensaje='El archivo es demasiado grande. Máximo permitido: 2 MB.'), 413

    @app.errorhandler(429)
    def too_many_requests(e):
        if _is_api_request():
            return jsonify({'error': 'Demasiadas solicitudes', 'code': 'RATE_LIMITED'}), 429
        return render_template('error.html', codigo=429,
                               mensaje='Demasiadas solicitudes. Intenta de nuevo más tarde.'), 429

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f'Error interno: {e}')
        if _is_api_request():
            return jsonify({'error': 'Error interno del servidor', 'code': 'INTERNAL_ERROR'}), 500
        return render_template('error.html', codigo=500,
                               mensaje='Error interno del servidor. Intenta de nuevo más tarde.'), 500

    @app.errorhandler(502)
    def bad_gateway(e):
        if _is_api_request():
            return jsonify({'error': 'Servicio temporalmente no disponible', 'code': 'BAD_GATEWAY'}), 502
        return render_template('error.html', codigo=502, mensaje='Servicio temporalmente no disponible.'), 502

    @app.errorhandler(503)
    def service_unavailable(e):
        if _is_api_request():
            return jsonify({'error': 'Servicio en mantenimiento', 'code': 'SERVICE_UNAVAILABLE'}), 503
        return render_template('error.html', codigo=503, mensaje='Servicio en mantenimiento.'), 503

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        logger.warning(f'ValidationError: {e.message}')
        if _is_api_request():
            return jsonify({'error': e.message, 'code': 'VALIDATION_ERROR'}), getattr(e, 'status_code', 400)
        return render_template('error.html', codigo=getattr(e, 'status_code', 400),
                               mensaje=e.message), getattr(e, 'status_code', 400)

    @app.errorhandler(UnauthorizedError)
    def handle_unauthorized(e):
        logger.warning(f'Unauthorized: {e.message}')
        if _is_api_request():
            return jsonify({'error': e.message, 'code': 'UNAUTHORIZED'}), 401
        return render_template('error.html', codigo=401, mensaje=e.message), 401

    @app.errorhandler(ForbiddenError)
    @app.errorhandler(PermissionError)
    def handle_forbidden(e):
        logger.warning(f'Forbidden: {e.message}')
        if _is_api_request():
            return jsonify({'error': e.message, 'code': 'FORBIDDEN'}), 403
        return render_template('error.html', codigo=403, mensaje=e.message), 403

    @app.errorhandler(NotFoundError)
    def handle_not_found(e):
        logger.warning(f'NotFound: {e.message}')
        if _is_api_request():
            return jsonify({'error': e.message, 'code': 'NOT_FOUND'}), 404
        return render_template('error.html', codigo=404, mensaje=e.message), 404

    @app.errorhandler(BusinessError)
    def handle_business_error(e):
        logger.warning(f'BusinessError: {e.message}')
        if _is_api_request():
            return jsonify({'error': e.message, 'code': 'BUSINESS_ERROR'}), getattr(e, 'status_code', 400)
        return render_template('error.html', codigo=getattr(e, 'status_code', 400),
                               mensaje=e.message), getattr(e, 'status_code', 400)

    @app.errorhandler(DatabaseError)
    def handle_database_error(e):
        logger.error(f'DatabaseError: {e.message}')
        if _is_api_request():
            return jsonify({'error': 'Error interno del servidor', 'code': 'DATABASE_ERROR'}), 500
        return render_template('error.html', codigo=500,
                               mensaje='Error interno del servidor.'), 500

    return app
