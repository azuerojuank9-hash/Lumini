# Changelog

All notable changes to this project are documented here.

## [2.1 Stable] — 2026-07-22

### Security
- **XSS**: Added JS string escaping in 4 templates (`directora_panel.html`, `archivados.html`, `rector_gestion.html`, `admin_panel.html`) to prevent injected names from breaking JavaScript contexts
- **XSS**: Added `escH()` HTML escaping in `rector/observador.html` for API-sourced innerHTML injection
- **CSRF**: Added `validar_csrf()` to parent portal login endpoint (`portal_padre_login`)
- **CSRF**: Fixed `X-CSRFToken` → `X-CSRF-Token` header name mismatch in `directora_login.html` and `rector_login.html`
- **Brute-force**: Added rate limiting (`ip_bloqueada`/`registrar_fallo`) to parent portal login endpoint

### Fixed
- **Parent login**: Created missing `parent_portal_login()` function in `auth_service.py` — parent portal login was non-functional after modularization
- **Student login**: Fixed `login_estudiante()` using wrong `alumno['password']` column; students use `alumno['pin']` (plain text comparison)
- **Parent dashboard**: Fixed `n.alumno_id` → `n.aid` in `parent_repository.py` (notas table uses `aid` column)
- **Parent dashboard**: Fixed `asistencia_v2` → `asistencia` table name (renamed by migration v11)
- **Service worker**: Removed stale cache reference to non-existent `/static/css/lumini.css`

### Added
- **DB indexes**: Migration v21 adds 4 missing indexes: `alumno_padre(padre_id)`, `alumno_padre(alumno_id)`, `observador_registros(alumno_id)`, `eventos_calendario(curso)`
- **LICENSE**: MIT license
- **requirements-dev.txt**: Dev dependencies (pytest, ruff, black, isort, mypy)

### Removed
- **Dead modules**: `app/forms/`, `app/config/`, `app/dto/`, `app/validators/` directories (never imported, zero usage)
- **Dead stubs**: `app/repositories/grades.py`, `app/repositories/users.py`, `app/services/auth.py`, `app/services/grades.py` (empty stubs)
- **Dead utils**: `app/utils/bruteforce.py`, `app/utils/notifications.py`, `app/utils/__init__.py` (duplicates or unused shims)

## [Unreleased]

### Fixed
- **Encoding**: Fixed 353 mojibake characters across 21 HTML templates (á, é, í, ó, ú, ñ, ¿, ·, «, »)
- **HTML structure**: Fixed missing `</div>` in `rector_panel.html`, removed 3 orphaned lines in `rector_profesores.html`
- **Runtime crash**: Fixed `|min` filter on int in `index.html:468` causing HTTP 500 on teacher dashboard
- **UTF-8 BOM**: Removed BOM from `flask_app.py` that blocked Python 3.14 compilation

### Changed
- **Email sending**: Consolidated SendGrid logic into a single `enviar_correo()` helper with attachment support; removed duplicate inline implementation from `directora_enviar_correos()`
- **Variable naming**: Renamed local variable `g` to `grade_num` in `generar_destinatarios()` to avoid shadowing Flask's `g` context object
- **Logging**: Added logger context to subject-assignment exception handler during teacher registration

### Removed
- **Dead code**: Removed unused functions `colegio_activo()`, `config_get_nombre_rol()`, `config_get_nombre_institucion()`

### Added
- **Automated tests**: Test suite for authentication flows, CRUD operations, PDF generation, route acceptance, and rendered HTML quality
- **Documentation**: README.md, INSTALL.md, DEPLOY.md

## [Previous work]

### Added
- Server-side pagination for professors and students lists
- DB indexes on frequently-queried columns
- g-caching for `get_profesor()`, `get_rector()`, `get_directora()`
- `config_get()` with `g` cache
- WSGI entry point (`wsgi.py`)
- Production config with Waitress
- gzip compression support via `flask_compress`
- Auto-backup every 24h

### Changed
- Optimized config to reduce DB connections
- Simplified `require_colegio()` middleware
- Refactored `periodo_cerrado()` to use `g` cache
- Pages refactored for performance (smaller DB fetches, reduced loops)
