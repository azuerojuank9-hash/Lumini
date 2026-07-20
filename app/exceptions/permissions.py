class UnauthorizedError(Exception):
    status_code: int = 401
    message: str = 'No has iniciado sesión'

    def __init__(self, message: str = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class ForbiddenError(Exception):
    status_code: int = 403
    message: str = 'No tienes permiso para realizar esta acción'

    def __init__(self, message: str = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class PermissionError(Exception):
    status_code: int = 403
    message: str = 'Permiso denegado'

    def __init__(self, message: str = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class RoleNotFoundError(Exception):
    status_code: int = 404
    message: str = 'Rol no encontrado'

    def __init__(self, role: str = None):
        msg = f'Rol "{role}" no encontrado' if role else self.message
        super().__init__(msg)
        self.message = msg


class InsufficientPermissionsError(Exception):
    status_code: int = 403
    message: str = 'Permisos insuficientes para realizar esta acción'

    def __init__(self, required: list = None):
        msg = f'Se requieren los permisos: {", ".join(required)}' if required else self.message
        super().__init__(msg)
        self.message = msg
