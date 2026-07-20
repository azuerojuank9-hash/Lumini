class ValidationError(Exception):
    status_code: int = 400
    message: str = 'Error de validación'

    def __init__(self, message: str = None, status_code: int = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        if status_code:
            self.status_code = status_code


class InvalidSlugError(ValidationError):
    message = 'El slug contiene caracteres no válidos'


class InvalidEmailError(ValidationError):
    message = 'El formato del correo electrónico no es válido'


class InvalidPasswordError(ValidationError):
    message = 'La contraseña no cumple con los requisitos de seguridad'


class MissingFieldError(ValidationError):
    def __init__(self, field: str = None):
        msg = f'El campo {field} es obligatorio' if field else 'Faltan campos obligatorios'
        super().__init__(msg)


class DuplicateEntryError(ValidationError):
    status_code = 409
    message = 'El registro ya existe'
