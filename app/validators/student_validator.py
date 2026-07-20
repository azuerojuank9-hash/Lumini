"""Student data validators — reusable validation logic."""
from app.exceptions import InvalidPasswordError, InvalidSlugError, ValidationError


class StudentValidator:

    @staticmethod
    def validar_slug(slug: str) -> str:
        slug = slug.strip().lower().replace(' ', '-')
        if not slug or not slug.replace('-', '').isalnum():
            raise InvalidSlugError()
        return slug

    @staticmethod
    def validar_password(password: str, min_len: int = 6) -> str:
        if not password or len(password) < min_len:
            raise InvalidPasswordError(f'La contraseña debe tener al menos {min_len} caracteres')
        return password

    @staticmethod
    def validar_password_match(password: str, confirm: str) -> str:
        if password != confirm:
            raise ValidationError('Las contraseñas no coinciden')
        return password

    @staticmethod
    def validar_nombre(nombre: str, field: str = 'Nombre') -> str:
        if not nombre:
            raise ValidationError(f'{field} es obligatorio')
        return nombre.strip()

    @staticmethod
    def validar_codigo(codigo: str) -> str:
        if not codigo:
            raise ValidationError('El código de invitación es obligatorio')
        return codigo.strip()

    @staticmethod
    def validar_email(email: str) -> str:
        if not email:
            raise ValidationError('El correo electrónico es obligatorio')
        return email.strip()
