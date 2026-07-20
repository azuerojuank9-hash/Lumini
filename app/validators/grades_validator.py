"""Grade data validators."""
from app.exceptions import InvalidGradeError, ValidationError


class GradesValidator:

    @staticmethod
    def validar_nota(valor, escala_min: float = 0, escala_max: float = 5) -> float:
        if valor is None:
            raise ValidationError('La nota es obligatoria')
        try:
            val = float(str(valor).replace(',', '.'))
        except (ValueError, TypeError):
            raise ValidationError('La nota debe ser un número válido')
        val = round(val, 2)
        if val < escala_min or val > escala_max:
            raise InvalidGradeError(val)
        return val

    @staticmethod
    def validar_nota_batch(aid, actividad_id, val, escala_min=0, escala_max=5):
        if None in (aid, actividad_id, val):
            raise ValidationError('Datos de nota incompletos')
        return aid, actividad_id, GradesValidator.validar_nota(val, escala_min, escala_max)

    @staticmethod
    def validar_porcentaje(valor):
        if valor is None:
            return None
        try:
            v = float(valor)
        except (ValueError, TypeError):
            raise ValidationError('El valor debe ser un número')
        if not (0 <= v <= 100):
            raise ValidationError('El porcentaje debe estar entre 0 y 100')
        return v
