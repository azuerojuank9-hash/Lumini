# Changelog

All notable changes to this project are documented here.

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
