# AGENTS.md — Lumini v2 Architecture Migration

## Objective
Migrate monolithic `flask_app.py` (~9300 lines) into modular Blueprints, services, and repositories while keeping all 298 tests passing end-to-end.

## Critical Constraints
- **No visual changes** — templates untouched, route paths unchanged
- **No permission changes** — session logic preserved identically
- **No schema changes** — DB columns/queries untouched
- **No test modifications** — tests must pass as-is after each step
- **All 298 tests must pass** before marking any module complete
- **`threading.Timer` must be daemon** (`t.daemon = True`) so process can exit after tests

## Architecture Conventions
- **Blueprint name**: `auth_bp` (stays consistent — not `auth_routes`, not `bp_auth`)
- **Blueprint registration**: in the `# ── Blueprint imports & registration` section of `flask_app.py`
- **url_for updates**: moving routes to Blueprints changes endpoint names (e.g. `login` → `auth.login`). Update all `url_for(...)` calls in `flask_app.py` accordingly
- **Lazy imports**: `_import_flask_app()` in route files avoids circular imports during transition
- **No comments** in generated code

## Migration Plan (Phase 1)
1. Module 1 — Authentication ✅ (login, logout, password recovery, CSRF, brute-force)
2. Module 2 — Teacher routes (grade registration, activities, observations, attendance, autosave, analytics)
3. Module 3 — Director routes (dashboard, bulletin PDF, communications)
4. Module 4 — Rector routes (horarios, gestión académica, tesorería)
5. Module 5 — Admin routes (códigos de registro, profesor list)
6. Module 6 — Portal routes (parent portal: dashboard, notes, attendance, communications)
7. Module 7 — Cross-cutting utilities (helpers, decorators, config)

## Module 1 — Authentication (COMPLETE)

### Files Created
- `app/routes/auth.py` — `auth_bp` with 17 endpoints: admin login/logout, teacher login/logout/password change/recovery, rector login/logout/register/recovery, directora login/logout/register, parent portal login
- `app/services/auth_service.py` — `login_profesor`, `login_rector`, `login_directora`, `login_estudiante`, `admin_login`, `parent_portal_login`, `validate_password_change`, `validate_password_recovery`, `set_session_for_rol`
- `app/repositories/user_repository.py` — all user SQL queries (find/create/update by role, username existence checks, parent/child queries, colegio CRUD)
- `app/utils/security.py` — `hash_pw`, `verificar_pw`, `necesita_rehash`, `generar_csrf`, `validar_csrf`, `extension_permitida`, `validar_imagen`
- `app/utils/bruteforce.py` — `ip_bloqueada`, `registrar_fallo`, `limpiar_intentos`

### flask_app.py Changes
- All 43 `url_for('login',...)` → `url_for('auth.login',...)`
- `url_for('admin')` → `url_for('auth.admin')`
- `url_for('rector_login',...)` → `url_for('auth.rector_login',...)`
- `url_for('directora_login',...)` → `url_for('auth.directora_login',...)`
- Removed all duplicate auth route blocks: admin login/logout, teacher cambiar_password, rector login/registrar/buscar/cambiar/logout, directora login/registrar_directo/logout, teacher login/logout/password recovery, parent portal login
- `threading.Timer` daemon flag set

### Verification
- 298/298 tests pass
- 0 duplicate routes in flask_app.py (186 unique routes)

### Remaining
- `get_profesor`, `require_colegio`, `get_colegio`, `get_materias_profesor` stay in `flask_app.py` until all consuming routes are migrated
- All non-auth routes (teacher, director, rector, etc.) remain in `flask_app.py`

## Test Commands
```powershell
cd C:\Users\PC\OneDrive\Documentos\GitHub\Lumini
& "C:\Users\PC\AppData\Local\Python\bin\python.exe" -m pytest --tb=short -q
```
298 passed (≈107s)
