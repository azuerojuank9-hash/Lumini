from typing import Any

from flask import session as _flask_session


def clear() -> None:
    _flask_session.clear()


def set_permanent(flag: bool = True) -> None:
    _flask_session.permanent = flag


def get(key: str, default: Any = None) -> Any:
    return _flask_session.get(key, default)


def set(key: str, value: Any) -> None:
    _flask_session[key] = value


def pop(key: str, default: Any = None) -> Any:
    return _flask_session.pop(key, default)
