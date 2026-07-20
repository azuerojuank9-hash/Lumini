"""Activity data validators."""
from app.exceptions import ValidationError


class ActivityValidator:

    @staticmethod
    def validar_nombre(nombre: str) -> str:
        nombre = (nombre or '').strip()
        if not nombre:
            raise ValidationError('El nombre de la actividad es obligatorio')
        if len(nombre) > 200:
            raise ValidationError('El nombre de la actividad es demasiado largo (máx. 200 caracteres)')
        return nombre

    @staticmethod
    def validar_orden(orden) -> int:
        try:
            o = int(orden)
        except (ValueError, TypeError):
            raise ValidationError('El orden debe ser un número entero')
        if o < 1:
            raise ValidationError('El orden debe ser mayor a 0')
        return o

    @staticmethod
    def validar_periodo(periodo, periodos_abiertos: set = None) -> int:
        try:
            p = int(periodo)
        except (ValueError, TypeError):
            raise ValidationError('El período debe ser un número entero')
        if p < 1:
            raise ValidationError('Período inválido')
        if periodos_abiertos is not None and p not in periodos_abiertos:
            raise ValidationError(f'El período {p} no está disponible')
        return p
