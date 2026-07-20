import logging
import traceback


def log_exception(exc: Exception, context: str = '', extra: dict = None):
    log = logging.getLogger('lumini.error')
    tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    msg = f'{context}: {exc}\n{tb}' if context else f'{exc}\n{tb}'
    log.error(msg, extra=extra)


def log_security_event(event: str, usuario: str = None, ip: str = None, extra: dict = None):
    log = logging.getLogger('lumini.security')
    parts = [f'usuario={usuario}', f'ip={ip}'] if usuario or ip else []
    if extra:
        parts.extend(f'{k}={v}' for k, v in extra.items())
    detail = ' | '.join(parts)
    log.info(f'{event} | {detail}' if detail else event)


def log_audit_event(action: str, slug: str = None, usuario: str = None, detalle: str = None):
    log = logging.getLogger('lumini.audit')
    parts = [f'slug={slug}', f'usuario={usuario}', f'detalle={detalle}']
    detail = ' | '.join(p for p in parts if p)
    log.info(f'{action} | {detail}')
