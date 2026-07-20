from datetime import date as _date


def register_template_filters(app):
    @app.template_filter('dias_restantes')
    def dias_restantes(fecha_str):
        try:
            fecha = _date.fromisoformat(str(fecha_str))
            return (fecha - _date.today()).days
        except Exception:
            return None

    @app.template_filter('hex_to_rgb')
    def hex_to_rgb(hex_color):
        h = hex_color.lstrip('#')
        if len(h) != 6:
            return '108,99,255'
        return f'{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}'

    return app
