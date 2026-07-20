"""Generate architecture and route documentation from source code."""
import os, ast, inspect, importlib, pkgutil
from pathlib import Path

_BASEDIR = Path(__file__).resolve().parent.parent
_DOCS_DIR = _BASEDIR / 'docs'


def _iter_modules(package_path, prefix=''):
    pkg_dir = _BASEDIR / package_path
    if not pkg_dir.is_dir():
        return
    for entry in pkg_dir.iterdir():
        if entry.suffix == '.py' and entry.stem != '__init__':
            mod_name = f'{prefix}{entry.stem}'
            yield mod_name, str(entry)
        elif entry.is_dir() and (entry / '__init__.py').exists():
            yield from _iter_modules(
                str(entry.relative_to(_BASEDIR)),
                prefix=f'{prefix}{entry.name}.',
            )


def _extract_docstring(path):
    try:
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
            return tree.body[0].value.value
    except Exception:
        pass
    return ''


def _extract_functions(path):
    try:
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ''
                funcs.append((node.name, doc.split('\n')[0] if doc else ''))
        return funcs
    except Exception:
        return []


def generate_architecture_doc():
    lines = [
        '# Lumini — Arquitectura',
        '',
        '## Estructura del proyecto',
        '',
        '```',
        'lumini/',
        '  config/         # Configuración por ambientes',
        '  app/',
        '    dto/          # Data Transfer Objects',
        '    exceptions/   # Excepciones tipadas',
        '    infra/        # Infraestructura (DB, seguridad, helpers)',
        '    logging/      # Logging profesional',
        '    repositories/ # Acceso a datos',
        '    routes/       # Blueprints Flask',
        '    services/     # Lógica de negocio',
        '    validators/   # Validadores reutilizables',
        '  tests/          # Tests (298 tests)',
        '```',
        '',
    ]

    for section, pkg_path, prefix in [
        ('Infraestructura', 'app/infra', 'app.infra.'),
        ('Servicios', 'app/services', 'app.services.'),
        ('Repositorios', 'app/repositories', 'app.repositories.'),
        ('Rutas', 'app/routes', 'app.routes.'),
        ('DTOs', 'app/dto', 'app.dto.'),
        ('Excepciones', 'app/exceptions', 'app.exceptions.'),
        ('Validadores', 'app/validators', 'app.validators.'),
        ('Config', 'config', ''),
    ]:
        lines.append(f'## {section}')
        lines.append('')
        for mod_name, path in sorted(_iter_modules(pkg_path, prefix)):
            doc = _extract_docstring(path)
            funcs = _extract_functions(path)
            lines.append(f'- **{mod_name}**')
            if doc:
                lines.append(f'  - {doc.split(chr(10))[0]}')
            if funcs:
                for fname, fdoc in funcs[:5]:
                    if fdoc:
                        lines.append(f'  - `{fname}()` — {fdoc}')
            lines.append('')
        lines.append('')

    (_DOCS_DIR / 'architecture.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'OK docs/architecture.md generated ({len(lines)} lines)')


def generate_routes_doc():
    lines = ['# Lumini — Rutas', '', '| Blueprint | Ruta | Métodos |', '|-----------|------|---------|']

    route_files = sorted((_BASEDIR / 'app' / 'routes').glob('*.py'))
    for rf in route_files:
        if rf.stem == '__init__':
            continue
        content = rf.read_text(encoding='utf-8')
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and hasattr(dec.func, 'attr') and dec.func.attr in ('route', 'get', 'post', 'put', 'delete'):
                        route_path = ''
                        methods = 'GET'
                        for kw in dec.keywords:
                            if kw.arg == 'methods':
                                methods = ', '.join(ast.literal_eval(kw.value))
                            elif kw.arg == 'defaults':
                                pass
                        if dec.args:
                            if isinstance(dec.args[0], ast.Constant):
                                route_path = dec.args[0].value
                            else:
                                route_path = ''
                        lines.append(f'| {rf.stem} | `{route_path}` | {methods} |')

    (_DOCS_DIR / 'routes.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'OK docs/routes.md generated ({len(lines)} lines)')


def generate_services_doc():
    lines = ['# Lumini — Servicios', '', '| Módulo | Función | Descripción |', '|--------|---------|-------------|']

    for mod_name, path in sorted(_iter_modules('app/services', 'app.services.')):
        funcs = _extract_functions(path)
        for fname, fdoc in funcs:
            desc = fdoc.replace('|', '/') if fdoc else ''
            lines.append(f'| {mod_name} | `{fname}()` | {desc} |')

    (_DOCS_DIR / 'services.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'OK docs/services.md generated ({len(lines)} lines)')


def generate_repositories_doc():
    lines = ['# Lumini — Repositorios', '', '| Módulo | Función | Descripción |', '|--------|---------|-------------|']

    for mod_name, path in sorted(_iter_modules('app/repositories', 'app.repositories.')):
        funcs = _extract_functions(path)
        for fname, fdoc in funcs:
            desc = fdoc.replace('|', '/') if fdoc else ''
            lines.append(f'| {mod_name} | `{fname}()` | {desc} |')

    (_DOCS_DIR / 'repositories.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'OK docs/repositories.md generated ({len(lines)} lines)')


def generate_database_doc():
    lines = [
        '# Lumini — Base de Datos',
        '',
        '## Esquema',
        '',
        'La base de datos usa SQLite con WAL mode.',
        '',
        '### Base de datos maestra (`master.db`)',
        '- `colegios` — registro de colegios',
        '- `schema_meta` — versión del esquema',
        '',
        '### Bases de datos por colegio (`colegios_db/{slug}.db`)',
        '- `alumnos` — estudiantes',
        '- `profesores` — docentes',
        '- `directoras` — coordinadoras',
        '- `rectores` — administradores del colegio',
        '- `notas` — calificaciones',
        '- `actividades` — tareas/exámenes',
        '- `asistencia` — registro de asistencia',
        '- `asignaciones_curso` — profesor -> curso/materia/jornada',
        '- `canales` / `mensajes_canal` / `canal_miembros` — mensajería',
        '- `notificaciones` — sistema de notificaciones',
        '- `observaciones` — observaciones de estudiantes',
        '- `auditoria_notas` / `auditoria_log` — auditoría',
        '- `periodos_estado` — estado de periodos académicos',
        '- `evaluaciones` — evaluaciones/autoevaluaciones',
        '- `configuracion` — configuración del colegio',
        '',
        '## Migraciones',
        '',
        'Las migraciones se manejan secuencialmente (v6 a v20 actualmente)',
        'en `app/infra/database.py`.',
        '',
        '## Cache',
        '',
        'Cache en memoria con TTL configurable (`_cache`, `_cache_lock`, `_CACHE_TTL`).',
    ]
    (_DOCS_DIR / 'database.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'OK docs/database.md generated ({len(lines)} lines)')


if __name__ == '__main__':
    _DOCS_DIR.mkdir(parents=True, exist_ok=True)
    generate_architecture_doc()
    generate_routes_doc()
    generate_services_doc()
    generate_repositories_doc()
    generate_database_doc()
    print('\nDocumentacion generada en docs/')
