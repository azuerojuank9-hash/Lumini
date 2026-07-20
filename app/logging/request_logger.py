import logging
import uuid

from flask import g, request


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            try:
                record.request_id = getattr(g, 'request_id', '-')
            except RuntimeError:
                record.request_id = '-'
        return True


def get_request_id() -> str:
    if not hasattr(g, 'request_id'):
        g.request_id = request.headers.get('X-Request-Id') or uuid.uuid4().hex[:12]
    return g.request_id


def log_request(response):
    get_request_id()
    extra = {
        'method': request.method,
        'path': request.path,
        'status': response.status_code,
        'ip': request.remote_addr,
        'user_agent': request.user_agent.string[:120] if request.user_agent else '-',
    }
    log = logging.getLogger('lumini.request')
    log.info(f'{extra["method"]} {extra["path"]} -> {extra["status"]}', extra=extra)
    return response
