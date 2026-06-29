# LUMINI — Arquitectura Técnica v1.0

> **Propósito**: Este documento define la arquitectura técnica definitiva del proyecto. Toda implementación debe seguir estrictamente lo aquí especificado. Cualquier desviación debe ser documentada y aprobada antes de ser incorporada.
>
> **Vigencia**: A partir del 27 de junio de 2026.

---

## Índice

1. [Arquitectura General del Sistema](#1-arquitectura-general-del-sistema)
2. [Diagrama de Módulos y Dependencias](#2-diagrama-de-módulos-y-dependencias)
3. [Modelo de Aislamiento por Institución](#3-modelo-de-aislamiento-por-institución)
4. [Arquitectura del Sistema de Permisos](#4-arquitectura-del-sistema-de-permisos)
5. [Flujo Completo de Autenticación y Autorización](#5-flujo-completo-de-autenticación-y-autorización)
6. [Flujo de Comunicación entre Módulos](#6-flujo-de-comunicación-entre-módulos)
7. [Modelo de Configuración Institucional](#7-modelo-de-configuración-institucional)
8. [Diagrama de Relaciones de la Base de Datos](#8-diagrama-de-relaciones-de-la-base-de-datos)
9. [Estrategia de Escalabilidad](#9-estrategia-de-escalabilidad)
10. [Estrategia de Migraciones](#10-estrategia-de-migraciones)
11. [Estrategia de Auditoría Ampliada](#11-estrategia-de-auditoría-ampliada)
12. [Convenciones de Desarrollo](#12-convenciones-de-desarrollo)

---

## 1. Arquitectura General del Sistema

### 1.1 Diagrama de capas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────────────┐  │
│  │ Jinja2       │  │ CSS (vars)   │  │ JavaScript (vanilla ES6+)       │  │
│  │ Templates    │  │ · dark/light │  │ · crearSistemaCanales()         │  │
│  │ · herencia   │  │ · instit.   │  │ · polling (3s, 30s)             │  │
│  │ · bloques    │  │ · responsive│  │ · fetch API (GET/POST JSON)     │  │
│  └──────┬───────┘  └──────────────┘  └──────────────────────────────────┘  │
├──────────┼──────────────────────────────────────────────────────────────────┤
│          └──────────────┬──────────────────────────────────┘                │
│                         ▼                                                   │
│                    ┌──────────────────────────────────────────────────┐     │
│                    │              API LAYER (Routes)                  │     │
│                    │  · Flask route handlers                          │     │
│                    │  · Validación de entrada                         │     │
│                    │  · CSRF protection                               │     │
│                    │  · Content-Type negotiation                      │     │
│                    │  · Rate limiting (fuerza bruta)                  │     │
│                    └──────────────────────┬───────────────────────────┘     │
├───────────────────────────────────────────┼─────────────────────────────────┤
│                                           ▼                                  │
│                    ┌──────────────────────────────────────────────────┐     │
│                    │         BUSINESS LOGIC LAYER (Services)          │     │
│                    │                                                   │     │
│                    │  ┌────────────┐ ┌────────────┐ ┌──────────────┐  │     │
│                    │  │ Auth       │ │ Persons    │ │ Academic     │  │     │
│                    │  │ Service    │ │ Service    │ │ Service      │  │     │
│                    │  └────────────┘ └────────────┘ └──────────────┘  │     │
│                    │  ┌────────────┐ ┌────────────┐ ┌──────────────┐  │     │
│                    │  │ Comm       │ │ Reports    │ │ Notification │  │     │
│                    │  │ Service    │ │ Service    │ │ Service      │  │     │
│                    │  └────────────┘ └────────────┘ └──────────────┘  │     │
│                    │  ┌────────────┐ ┌────────────┐ ┌──────────────┐  │     │
│                    │  │ Audit      │ │ Config     │ │ Permission   │  │     │
│                    │  │ Service    │ │ Service    │ │ Service      │  │     │
│                    │  └────────────┘ └────────────┘ └──────────────┘  │     │
│                    └──────────────────────┬───────────────────────────┘     │
├───────────────────────────────────────────┼─────────────────────────────────┤
│                                           ▼                                  │
│                    ┌──────────────────────────────────────────────────┐     │
│                    │           DATA ACCESS LAYER (DAL)                │     │
│                    │  · conectar(slug) → sqlite3.Connection          │     │
│                    │  · Connection pool (per-request)                │     │
│                    │  · Row factory (sqlite3.Row)                    │     │
│                    │  · WAL mode (concurrent reads)                  │     │
│                    └──────────────────────┬───────────────────────────┘     │
├───────────────────────────────────────────┼─────────────────────────────────┤
│                                           ▼                                  │
│                    ┌──────────────────────────────────────────────────┐     │
│                    │              DATA LAYER                          │     │
│                    │                                                   │     │
│                    │  ┌──────────────────┐  ┌──────────────────┐      │     │
│                    │  │   master.db      │  │  colegios_db/     │      │     │
│                    │  │  · instituciones │  │  · {slug}.db      │      │     │
│                    │  │  · admins        │  │  · {slug2}.db     │      │     │
│                    │  │  · global_config │  │  · ...            │      │     │
│                    │  └──────────────────┘  └──────────────────┘      │     │
│                    └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Stack tecnológico (fijo)

| Componente | Tecnología | Versión mínima | Justificación |
|------------|-----------|----------------|---------------|
| Backend | Flask (Python) | 3.10+ | Sin cambios. Maduro, liviano, suficiente. |
| Base de datos | SQLite 3 | 3.35+ (WAL support) | Embebido, cero configuración, una DB por institución. |
| Frontend | HTML5 + CSS3 + JS ES6+ | — | Sin frameworks. Control total, sin dependencias externas. |
| Servidor de correo | SendGrid API (SMTP futuro) | — | Transaccional (solo recovery). |
| Entorno | Python dotenv | — | Configuración vía `.env`. |
| Hash de contraseñas | hashlib (sha256 + salt) | — | Sin bcrypt para mantener compatibilidad con DB existente. |

### 1.3 Flujo de solicitud (request lifecycle)

```
Cliente ──HTTP──► Flask ──► Middleware ──► Route ──► Service ──► DAL ──► SQLite
                        │                                                │
                        ├── CSRF validation                              │
                        ├── Session load                                 │
                        ├── Permission check                             │
                        └── Audit log (write operations)                 │
                        ▲                                                ▼
                        └────────────── HTTP Response ◄──────────────────┘
```

Cada request pasa por:

1. **Flask WSGI** — recibe la solicitud
2. **Middleware implícito** — `before_request`: carga sesión, detecta slug, carga config institucional
3. **Validación CSRF** — si es POST/PUT/DELETE sin X-CSRF-Token, rechazar
4. **Route handler** — valida parámetros, llama al servicio correspondiente
5. **Permission check** — verifica que el usuario tenga permiso para la acción
6. **Audit** — si la operación es de escritura, registrar en audit_log
7. **Response** — JSON o HTML renderizado con Jinja2

---

## 2. Diagrama de Módulos y Dependencias

### 2.1 Mapa de módulos

```
                    ┌──────────────────────────────────────────────────────┐
                    │                     NÚCLEO                           │
                    │  (sin dependencias de otros módulos)                 │
                    │                                                      │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
                    │  │ Auth     │  │ Config   │  │ Permission       │   │
                    │  │ Module   │◄─┤ Module   │◄─┤ Module           │   │
                    │  └──────────┘  └──────────┘  └──────────────────┘   │
                    │       │              │                │              │
                    │       ▼              ▼                ▼              │
                    │  ┌──────────────────────────────────────────┐       │
                    │  │              Audit Module                │       │
                    │  └──────────────────────────────────────────┘       │
                    │       │                                             │
                    │       ▼                                             │
                    │  ┌──────────────────────────────────────────┐       │
                    │  │         Notification Module              │       │
                    │  └──────────────────────────────────────────┘       │
                    └──────────────────────────────────────────────────────┘
                                       │
                  ┌────────────────────┼────────────────────┐
                  ▼                    ▼                    ▼
    ┌────────────────────────┐ ┌──────────────────┐ ┌──────────────────┐
    │ Gestión Institucional  │ │  Gestión         │ │  Comunicación    │
    │                        │ │  Académica       │ │  Institucional   │
    │ Depende de:            │ │                  │ │                  │
    │  · Auth (identidad)    │ │ Depende de:      │ │ Depende de:      │
    │  · Config (estructura) │ │  · Auth          │ │  · Auth          │
    │  · Permissions         │ │  · Config        │ │  · Permissions   │
    │  · Audit               │ │  · Permissions   │ │  · Audit         │
    │                        │ │  · Audit         │ │  · Notifications │
    └────────────────────────┘ │  · Institución   │ └──────────────────┘
                               │  · Notifications │         │
                               └──────────────────┘         │
                                       │                     │
                                       ▼                     ▼
                               ┌──────────────────────────────────────────┐
                               │         Analítica y Reportes             │
                               │                                          │
                               │ Depende de: TODOS los módulos anteriores │
                               └──────────────────────────────────────────┘
```

### 2.2 Reglas de dependencia

1. **Núcleo no depende de ningún módulo funcional.** Es la base del sistema.
2. **Los módulos funcionales dependen del Núcleo**, no entre sí directamente.
3. Si un módulo A necesita datos del módulo B, lo hace a través del Núcleo (vía Notification o Audit), no con llamada directa.
4. **Excepción**: Comunicación Institucional puede leer datos de Gestión Institucional (nombres de usuarios, cursos) para destinatarios. Esta es una dependencia de solo lectura, autorizada.
5. **Excepción 2**: Analítica puede leer datos de todos los módulos. Solo lectura. Nunca escribe.

### 2.3 Interfaz entre módulos

Cada módulo exporta un conjunto de funciones Python con prefijo claro:

```python
# Módulo Auth
auth_login(slug, email, password) → (usuario, error)
auth_logout(slug)
auth_recover(slug, email) → token
auth_reset(slug, token, new_password) → bool

# Módulo Permission
perm_tiene(slug, usuario_id, permiso, entidad_tipo=None, entidad_id=None) → bool
perm_roles_usuario(slug, usuario_id) → [Role]
perm_usuarios_con_permiso(slug, permiso) → [Usuario]

# Módulo Audit
audit_log(slug, usuario_id, accion, tabla, registro_id, valor_anterior, valor_nuevo)
audit_consulta(slug, filtros) → [AuditEntry]

# Módulo Config
config_get(slug) → dict
config_set(slug, clave, valor) → bool
config_get_escala(slug) → dict  # tipo, min, max, nota_minima

# Módulo Notification
notif_crear(slug, destinatario_tipo, destinatario_id, titulo, mensaje, tipo, link)
notif_no_leidas(slug, usuario_tipo, usuario_id) → int
notif_marcar_leidas(slug, usuario_tipo, usuario_id)
```

---

## 3. Modelo de Aislamiento por Institución

### 3.1 Filosofía

Cada institución opera sobre su propia base de datos SQLite. No hay datos compartidos entre instituciones a nivel de aplicación. Esto garantiza:

- **Aislamiento total**: una institución nunca accede a datos de otra.
- **Portabilidad**: la DB de una institución es un solo archivo. Se puede respaldar, migrar, clonar.
- **Escalabilidad horizontal**: las instituciones no compiten por recursos de DB.
- **Privacidad por diseño**: no hay riesgo de fuga de datos entre instituciones.

### 3.2 Estructura de archivos

```
proyecto/
├── master.db                  ← Base de datos maestra (instituciones + admins globales)
├── colegios_db/               ← Bases de datos por institución
│   ├── colegio-san-jose.db
│   ├── universidad-nacional.db
│   ├── instituto-tecnico.db
│   └── ...
├── static/
│   └── logos/                 ← Logos institucionales
│       ├── colegio-san-jose.png
│       └── ...
├── templates/
│   ├── base.html              ← Template base
│   ├── admin/                 ← Templates de administración global
│   ├── rector/                ← Templates de rector (compartidos)
│   ├── docente/               ← Templates de docente
│   ├── estudiante/            ← Templates de estudiante
│   └── components/            ← Componentes reutilizables
└── flask_app.py               ← Aplicación monolítica
```

### 3.3 Master DB (`master.db`)

```sql
CREATE TABLE instituciones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT UNIQUE NOT NULL,       -- identificador URL
    nombre          TEXT NOT NULL,
    logo            TEXT DEFAULT '',
    activo          INTEGER DEFAULT 1,
    tipo            TEXT DEFAULT 'colegio',      -- colegio, universidad, instituto, centro
    creado          TEXT DEFAULT (date('now')),
    vencimiento     TEXT,
    plan            TEXT DEFAULT 'basic',        -- basic, professional, enterprise

    -- Branding
    primary_color   TEXT DEFAULT '#7C3AED',
    secondary_color TEXT DEFAULT '#6D28D9',

    -- Schema version (control de migraciones)
    schema_version  INTEGER DEFAULT 0,

    -- Códigos legacy
    codigo_registro     TEXT DEFAULT '',
    codigo_profesores   TEXT DEFAULT '',
    codigo_directoras   TEXT DEFAULT '',
    codigo_rectores     TEXT DEFAULT ''
);

CREATE TABLE admins_globales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario         TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    activo          INTEGER DEFAULT 1,
    ultimo_acceso   TEXT
);
```

### 3.4 Per-Instance DB (`colegios_db/{slug}.db`)

Cada base de datos institucional contiene todas las tablas del sistema. El esquema completo se define en la sección 8.

### 3.5 Conexión y ciclo de vida

```python
def conectar(slug):
    """Retorna una conexión a la DB de la institución."""
    db_path = os.path.join(DB_FOLDER, f'{slug}.db')
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Institución no encontrada: {slug}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")     # Concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")       # Integrity
    conn.execute("PRAGMA busy_timeout=5000")    # Wait 5s on lock
    return conn

# Por request, se abre y cierra la conexión.
# No hay connection pooling persistente (SQLite no lo necesita).
```

### 3.6 Aislamiento en práctica

```python
def obtener_datos_institucion(slug):
    """Solo accede a la DB de la institución autenticada."""
    conn = conectar(slug)
    # ... solo datos de esta institución ...
    conn.close()

# Cada slug se valida al inicio del request.
# No existe ninguna ruta que permita pasar un slug de otra institución
# (excepto el admin global que puede seleccionar cualquier slug).
```

---

## 4. Arquitectura del Sistema de Permisos

### 4.1 Modelo conceptual

```
┌──────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────────┐
│  Usuario  │────►│  Rol en      │────►│ Permisos  │────►│  Políticas   │
│           │     │  Institución │     │ del rol   │     │  de acceso   │
└──────────┘     └──────────────┘     └──────────┘     └──────────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │  ¿Tiene acceso?  │
                                                     │  Sí / No         │
                                                     └──────────────────┘
```

### 4.2 Estructura de datos

```sql
-- roles_base: definiciones del sistema (no editables)
CREATE TABLE roles_base (
    codigo          TEXT PRIMARY KEY,       -- 'admin','rector','authority','teacher','student','guardian'
    nombre_default  TEXT NOT NULL,          -- nombre por defecto
    nivel           INTEGER NOT NULL,       -- 0=admin (más alto), 5=acudiente (más bajo)
    descripcion     TEXT
);

-- roles_instancia: personalización por institución
CREATE TABLE roles_instancia (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT NOT NULL,
    codigo          TEXT NOT NULL REFERENCES roles_base(codigo),
    nombre          TEXT NOT NULL,           -- nombre personalizado
    activo          INTEGER DEFAULT 1,
    UNIQUE(slug, codigo)
);

-- permisos_rol: qué permisos tiene cada rol en cada institución
CREATE TABLE permisos_rol (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rol_instancia_id INTEGER NOT NULL REFERENCES roles_instancia(id),
    permiso         TEXT NOT NULL,           -- 'academic.grades.write'
    UNIQUE(rol_instancia_id, permiso)
);

-- usuarios (ver sección 8)
-- usuarios_roles: qué rol tiene cada usuario y en qué ámbito
CREATE TABLE usuarios_roles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER NOT NULL,
    rol_instancia_id INTEGER NOT NULL,
    entidad_tipo    TEXT,                    -- NULL (global), 'programa', 'curso', 'materia'
    entidad_id      INTEGER,
    asignado_por    INTEGER,
    creado          TEXT,
    UNIQUE(usuario_id, rol_instancia_id, entidad_tipo, entidad_id)
);
```

### 4.3 Catálogo de permisos

Los permisos se organizan en una jerarquía de tres niveles:

```
<módulo>.<submódulo>.<acción>
```

#### Módulo: `institution`
| Permiso | Afecta | Roles por defecto |
|---------|--------|-------------------|
| `institution.view` | Ver datos de la institución | admin, rector |
| `institution.edit` | Editar nombre, logo, colores | admin |
| `institution.delete` | Eliminar institución | admin |

#### Módulo: `people`
| Permiso | Afecta | Roles por defecto |
|---------|--------|-------------------|
| `people.teachers.view` | Ver lista de docentes | rector, authority |
| `people.teachers.create` | Crear docentes | rector |
| `people.teachers.edit` | Editar docentes | rector |
| `people.teachers.archive` | Archivar docentes | rector |
| `people.students.view` | Ver lista de estudiantes | rector, authority, teacher |
| `people.students.create` | Crear estudiantes | rector, authority |
| `people.students.edit` | Editar estudiantes | rector, authority |
| `people.students.archive` | Archivar estudiantes | rector |

#### Módulo: `structure`
| Permiso | Roles por defecto |
|---------|-------------------|
| `structure.sedes.manage` | rector |
| `structure.faculties.manage` | rector |
| `structure.programs.manage` | rector |
| `structure.courses.manage` | rector |
| `structure.subjects.manage` | rector |

#### Módulo: `academic`
| Permiso | Roles por defecto |
|---------|-------------------|
| `academic.grades.view` | rector, authority, teacher, student, guardian |
| `academic.grades.write` | teacher (solo sus materias) |
| `academic.grades.approve` | authority, rector (cierre de período) |
| `academic.grades.history` | rector, authority |
| `academic.attendance.view` | rector, authority, teacher, student, guardian |
| `academic.attendance.write` | teacher (solo sus materias) |
| `academic.observations.view` | rector, authority, teacher, guardian |
| `academic.observations.write` | teacher, authority |
| `academic.evaluations.create` | teacher |
| `academic.evaluations.edit` | teacher |
| `academic.activities.create` | teacher |
| `academic.activities.edit` | teacher |

#### Módulo: `communication`
| Permiso | Roles por defecto |
|---------|-------------------|
| `communication.communicados.view` | Todos |
| `communication.communicados.create` | rector, authority |
| `communication.communicados.publish` | rector (autoridad para publicar) |
| `communication.communicados.archive` | rector |
| `communication.channels.create` | rector |
| `communication.channels.delete` | rector |
| `communication.channels.manage_members` | rector |
| `communication.channels.send` | teacher, estudiante (en sus canales) |
| `communication.channels.read` | Todos |

#### Módulo: `reports`
| Permiso | Roles por defecto |
|---------|-------------------|
| `reports.grades` | rector, authority |
| `reports.attendance` | rector, authority |
| `reports.consolidated` | rector |
| `reports.audit` | rector |
| `reports.export` | rector, authority |

#### Módulo: `config`
| Permiso | Roles por defecto |
|---------|-------------------|
| `config.academic.edit` | rector |
| `config.roles.edit` | rector |
| `config.branding.edit` | rector |
| `config.users.manage` | admin |

#### Módulo: `audit`
| Permiso | Roles por defecto |
|---------|-------------------|
| `audit.log.view` | rector |
| `audit.log.export` | rector |

### 4.4 Evaluación de permisos (políticas)

```python
def tiene_permiso(slug, usuario_id, permiso, entidad_tipo=None, entidad_id=None):
    """
    Evalúa si un usuario tiene un permiso específico.

    Algoritmo:
    1. Obtener todos los roles del usuario en la institución
    2. Para cada rol, obtener sus permisos
    3. Si el rol tiene un '*' (admin/rector), retornar True
    4. Si el permiso solicitado está en la lista, verificar alcance
    5. Si el rol tiene alcance (entidad_tipo), verificar que coincida
    6. Si no hay alcance, el permiso es global y aplica
    """
    roles = obtener_roles_con_permisos(slug, usuario_id)

    for rol in roles:
        # Admin y rector tienen todos los permisos
        if rol['codigo'] in ('admin', 'rector'):
            return True

        # Si el rol no tiene el permiso, saltar
        if permiso not in rol['permisos'] and '*' not in rol['permisos']:
            continue

        # Verificar alcance
        if entidad_tipo and rol['entidad_tipo']:
            # El rol está limitado a una entidad específica
            if rol['entidad_tipo'] != entidad_tipo or rol['entidad_id'] != entidad_id:
                continue

        # Permiso concedido
        return True

    return False
```

### 4.5 Herencia jerárquica

```python
PERMISOS_POR_NIVEL = {
    'admin':     ['*'],                                    # TODO
    'rector':    ['*'],                                    # TODO (todo excepto admin)
    'authority': ['people.*', 'structure.*', 'academic.*', 'communication.*', 'reports.*'],
    'teacher':   ['academic.*', 'communication.communicados.view', 'communication.channels.*'],
    'student':   ['academic.grades.view', 'academic.attendance.view',
                  'communication.communicados.view', 'communication.channels.read',
                  'communication.channels.send'],
    'guardian':  ['academic.grades.view', 'academic.attendance.view',
                  'communication.communicados.view', 'communication.channels.read'],
}
```

**Regla de herencia**: Un rol de nivel N hereda todos los permisos de los roles de nivel > N (roles inferiores en la jerarquía). Esto significa que un `rector` (nivel 1) tiene todo lo que tiene un `authority` (nivel 2), más los suyos propios.

---

## 5. Flujo Completo de Autenticación y Autorización

### 5.1 Diagrama de flujo de login

```
Usuario ──► /{slug}/login (GET)
                │
                ▼
           Render login.html
           (form: email + password)
                │
                ▼
Usuario ──► POST /{slug}/login
                │
                ├── Validar CSRF ──► Fail ──► 400
                │
                ├── Verificar IP bloqueada ──► Sí ──► Mostrar "Demasiados intentos. Espere N segundos."
                │
                ├── Buscar usuario por email en DB ──► No existe ──► "Credenciales incorrectas" (genérico)
                │
                ├── Verificar usuario activo ──► No ──► "Cuenta desactivada. Contacte al administrador."
                │
                ├── Verificar password_hash ──► No coincide ──► registrar_fallo(), "Credenciales incorrectas"
                │
                ├── (Éxito) Limpiar intentos fallidos
                │
                ├── Registrar en audit_log (login exitoso)
                │
                ├── Crear sesión Flask:
                │   ├── session['user_id'] = usuario.id
                │   ├── session['slug'] = slug
                │   ├── session['roles'] = [rol.codigo for rol in obtener_roles(usuario.id)]
                │   └── session.permanent = True (4h por defecto)
                │
                ├── Actualizar ultimo_acceso en usuarios
                │
                └── Redirect a:
                    ├── /{slug}/admin-dashboard    (si es admin global)
                    ├── /{slug}/rector-dashboard   (si el rol activo es rector)
                    ├── /{slug}/authority-dashboard(si es authority)
                    ├── /{slug}/docente-dashboard  (si es teacher)
                    ├── /{slug}/estudiante-dashboard(si es student)
                    └── /{slug}/acudiente-dashboard(si es guardian)
```

### 5.2 Manejo de sesiones

```python
@app.before_request
def before_request():
    """Cargar slug y configuración institucional antes de cada request."""
    g.slug = request.view_args.get('slug', None)
    g.usuario = None
    g.roles = []
    g.config = {}

    if g.slug:
        # Verificar que la institución existe y está activa
        inst = get_institucion(g.slug)
        if not inst or not inst['activo']:
            abort(404)

        # Cargar configuración
        g.config = config_get(g.slug)

        # Cargar usuario desde sesión
        user_id = session.get('user_id')
        if user_id:
            g.usuario = usuario_get(g.slug, user_id)
            g.roles = obtener_roles_usuario(g.slug, user_id)
            g.permissions = obtener_permisos_usuario(g.slug, user_id)
```

### 5.3 Decorador de autorización

```python
def requiere_permiso(permiso, entidad_tipo=None, entidad_id=None):
    """Decorador para verificar permisos en rutas."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            slug = g.slug
            if not g.usuario:
                return redirect(url_for('login', slug=slug))

            # Extraer entidad_id de kwargs si es necesario
            e_id = entidad_id(kwargs) if callable(entidad_id) else entidad_id
            e_tipo = entidad_tipo(kwargs) if callable(entidad_tipo) else entidad_tipo

            if not tiene_permiso(slug, g.usuario['id'], permiso, e_tipo, e_id):
                abort(403)

            return f(*args, **kwargs)
        return wrapper
    return decorator
```

### 5.4 Ejemplos de uso

```python
@app.route('/<slug>/docente/notas/<int:curso_id>/<int:materia_id>')
@requiere_permiso('academic.grades.write', 'materia', lambda k: k['materia_id'])
def notas_curso(slug, curso_id, materia_id):
    # Ya verificado: el usuario tiene permiso para escribir notas en esta materia
    ...
```

### 5.5 Recuperación de acceso

```
Flujo de recovery (sin preguntas secretas):

1. Usuario hace clic en "¿Olvidó su contraseña?"
2. Ingresa su email
3. Sistema:
   a. Busca el email en la tabla usuarios
   b. Si existe, genera un token único (secrets.token_urlsafe(32))
   c. Almacena token + expiración (30 min) en tabla password_resets
   d. Envía email con link: /{slug}/reset-password?token=XXX
4. Usuario abre el link
5. Sistema verifica token + expiración
6. Usuario ingresa nueva contraseña (x2 para confirmar)
7. Sistema actualiza password_hash y elimina el token

NOTA: No mostrar "Email enviado" vs "Email no encontrado".
Siempre mostrar: "Si el email está registrado, recibirá un enlace de recuperación."
```

---

## 6. Flujo de Comunicación entre Módulos

### 6.1 Principios

1. **Comunicación directa**: al ser una aplicación monolítica, los módulos se comunican mediante llamadas a funciones Python. No hay HTTP interno, no hay message broker.
2. **Inyección de dependencia manual**: los servicios se importan directamente. No hay DI container.
3. **El módulo de Notification actúa como bus de eventos interno** para operaciones asíncronas ligeras.
4. **Toda comunicación de escritura pasa por Audit**.

### 6.2 Mapa de comunicación

```
┌─────────────┐     ┌──────────────┐
│  Evaluación  │────►│  Notas       │  (cuando se crea una evaluación, afecta notas)
│  (create)    │     │  (calc)      │
└─────────────┘     └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Audit       │  (registrar creación)
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Notification│  (notificar a estudiantes)
                    └──────────────┘

┌─────────────┐     ┌──────────────┐
│  Comunicado  │────►│  Notification│  (notificar a destinatarios)
│  (publish)   │     └──────────────┘
└─────────────┘
       │
       ▼
┌─────────────┐
│  Audit       │  (registrar publicación)
└─────────────┘

┌─────────────┐     ┌──────────────┐
│  Asistencia  │────►│  Alertas     │  (si 3+ faltas consecutivas)
│  (write)     │     └──────────────┘
└─────────────┘        │
       │               ▼
       ▼        ┌──────────────┐
┌─────────────┐ │  Notification│
│  Audit       │ └──────────────┘
└─────────────┘
```

### 6.3 Notification como bus interno

```python
def notif_crear(slug, destinatario_tipo, destinatario_id, titulo, mensaje, tipo='info', link=''):
    """
    Crea una notificación en la BD.
    - destinatario_tipo: 'usuario', 'rol', 'curso', 'materia'
    - destinatario_id: ID según el tipo
    """
    conn = conectar(slug)
    if destinatario_tipo == 'usuario':
        conn.execute(
            'INSERT INTO notificaciones (usuario_tipo, usuario_id, titulo, mensaje, tipo, link) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            ('usuario', destinatario_id, titulo, mensaje, tipo, link)
        )
    elif destinatario_tipo == 'rol':
        # Buscar todos los usuarios con ese rol y crear notificaciones
        usuarios = obtener_usuarios_por_rol(slug, destinatario_id)
        for u in usuarios:
            conn.execute(
                'INSERT INTO notificaciones (usuario_tipo, usuario_id, titulo, mensaje, tipo, link) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                ('usuario', u['id'], titulo, mensaje, tipo, link)
            )
    conn.commit()
    conn.close()
```

### 6.4 Reglas de notificaciones automáticas

| Evento | Notificación a | Tipo |
|--------|---------------|------|
| Nuevo comunicado | Destinatarios (rol/curso) | `comunicado` |
| Nuevo mensaje en canal | Miembros del canal | `mensaje` |
| Nota registrada/modificada | Estudiante afectado | `nota` |
| Observación creada | Estudiante + acudiente | `observacion` |
| 3+ inasistencias consecutivas | Autoridad académica del curso | `alerta` |
| Promedio < nota mínima | Docente + autoridad académica | `alerta` |
| Cierre de período | Docentes del curso | `sistema` |

---

## 7. Modelo de Configuración Institucional

### 7.1 Estructura

```sql
CREATE TABLE config_institucion (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                TEXT NOT NULL UNIQUE,

    -- Académico
    tipo_evaluacion     TEXT DEFAULT 'numerica',   -- numerica, conceptual, porcentaje, letras
    escala_min          REAL DEFAULT 1.0,
    escala_max          REAL DEFAULT 10.0,
    nota_minima_aprobar REAL DEFAULT 6.0,
    decimales_notas     INTEGER DEFAULT 1,
    creditos_activo     INTEGER DEFAULT 0,
    escala_conceptual   TEXT DEFAULT '["A","B","C","D","E","F"]',

    -- Períodos
    num_periodos        INTEGER DEFAULT 4,
    periodos_json       TEXT,  -- [{"nombre":"Semestre 1","inicio":"2026-02-01","fin":"2026-06-30","orden":1}]

    -- Jornadas
    jornadas_json       TEXT,  -- '["Mañana","Tarde","Nocturna"]'

    -- Estructura
    jerarquia_activa    INTEGER DEFAULT 0,
    niveles_json        TEXT,  -- [{"nivel":0,"nombre":"Sede","plural":"Sedes","opcional":true},
                              --  {"nivel":1,"nombre":"Facultad","plural":"Facultades","opcional":true},
                              --  {"nivel":2,"nombre":"Programa","plural":"Programas","opcional":false}]

    -- Roles (nombres personalizados)
    roles_json          TEXT,  -- {"rector":"Rector","authority":"Coordinador Académico",
                              --  "teacher":"Docente","student":"Estudiante","guardian":"Acudiente"}

    -- Comunicación
    acuse_recibo        INTEGER DEFAULT 1,
    firmas_activas      INTEGER DEFAULT 0,

    -- Privacidad
    notas_publicas_entre_pares INTEGER DEFAULT 0,

    -- Sistema
    idioma              TEXT DEFAULT 'es',
    huso_horario        TEXT DEFAULT 'America/Bogota',
    updated_at          TEXT DEFAULT (datetime('now','localtime'))
);
```

### 7.2 API de configuración

```python
class ConfigService:
    @staticmethod
    def get(slug):
        """Retorna toda la configuración como dict."""
        conn = conectar(slug)
        c = conn.execute('SELECT * FROM config_institucion WHERE slug=?', (slug,)).fetchone()
        conn.close()
        if not c:
            return ConfigService.crear_default(slug)
        return dict(c)

    @staticmethod
    def crear_default(slug):
        """Crea configuración por defecto para una institución nueva."""
        defaults = {
            'slug': slug,
            'tipo_evaluacion': 'numerica',
            'escala_min': 1.0,
            'escala_max': 10.0,
            'nota_minima_aprobar': 6.0,
            'decimales_notas': 1,
            'num_periodos': 4,
            'jornadas_json': json.dumps(['Mañana', 'Tarde', 'Nocturna']),
            'roles_json': json.dumps({
                'rector': 'Rector',
                'authority': 'Coordinador',
                'teacher': 'Docente',
                'student': 'Estudiante',
                'guardian': 'Acudiente'
            }),
            'acuse_recibo': 1,
        }
        conn = conectar(slug)
        conn.execute('INSERT INTO config_institucion (slug, tipo_evaluacion, escala_min, escala_max, '
                     'nota_minima_aprobar, decimales_notas, num_periodos, jornadas_json, roles_json, acuse_recibo) '
                     'VALUES (:slug, :tipo_evaluacion, :escala_min, :escala_max, :nota_minima_aprobar, '
                     ':decimales_notas, :num_periodos, :jornadas_json, :roles_json, :acuse_recibo)', defaults)
        conn.commit()
        conn.close()
        return defaults

    @staticmethod
    def actualizar(slug, clave, valor):
        """Actualiza un campo de configuración."""
        permitidos = [
            'tipo_evaluacion', 'escala_min', 'escala_max', 'nota_minima_aprobar',
            'decimales_notas', 'num_periodos', 'periodos_json', 'jornadas_json',
            'jerarquia_activa', 'niveles_json', 'roles_json', 'acuse_recibo',
            'firmas_activas', 'notas_publicas_entre_pares', 'idioma', 'huso_horario',
            'creditos_activo', 'escala_conceptual'
        ]
        if clave not in permitidos:
            raise ValueError(f"Configuración no permitida: {clave}")
        conn = conectar(slug)
        conn.execute(f'UPDATE config_institucion SET {clave}=?, updated_at=datetime("now","localtime") WHERE slug=?',
                     (valor, slug))
        conn.commit()
        conn.close()

    @staticmethod
    def get_nombre_rol(slug, codigo):
        """Retorna el nombre personalizado de un rol."""
        config = ConfigService.get(slug)
        roles = json.loads(config.get('roles_json', '{}'))
        return roles.get(codigo, codigo.capitalize())
```

### 7.3 Cómo afecta la configuración al sistema

| Configuración | Afecta |
|--------------|--------|
| `tipo_evaluacion` | Cómo se ingresan y muestran las notas. Si es `conceptual`, el input es un `<select>`. Si es `numerica`, es un `<input type="number">`. |
| `escala_min/max` | Validación de rango de notas. |
| `nota_minima_aprobar` | Umbral para aprobar/reprobar. Afecta color, estadísticas, alertas. |
| `num_periodos` | Cuántas columnas de período se muestran. |
| `jerarquia_activa` | Si se muestra UI de facultades/programas o solo cursos planos. |
| `roles_json` | Nombres visibles en toda la interfaz. El código interno usa `codigo`, pero la UI muestra el nombre personalizado. |
| `acuse_recibo` | Si los comunicados registran lectura. |
| `jornadas_json` | Opciones disponibles en selects de jornada. |

---

## 8. Diagrama de Relaciones de la Base de Datos

### 8.1 Diagrama entidad-relación (textual)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MASTER DB (master.db)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐                                               │
│  │  instituciones   │                                               │
│  ├──────────────────┤                                               │
│  │  id (PK)         │──┐                                            │
│  │  slug (UQ)       │  │  (una institución = una DB aparte)         │
│  │  nombre          │  │                                            │
│  │  activo          │  │                                            │
│  │  tipo            │  │                                            │
│  │  schema_version  │  │                                            │
│  │  ...             │  │                                            │
│  └──────────────────┘  │                                            │
│                         │                                            │
│  ┌──────────────────┐  │                                            │
│  │ admins_globales  │  │                                            │
│  ├──────────────────┤  │                                            │
│  │ id               │  │                                            │
│  │ usuario (UQ)     │  │                                            │
│  │ password_hash    │  │                                            │
│  └──────────────────┘  │                                            │
└────────────────────────┼────────────────────────────────────────────┘
                         │
                         ▼  (slug determina qué DB abrir)
┌─────────────────────────────────────────────────────────────────────┐
│                    PER-INSTANCE DB ({slug}.db)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐   │
│  │  usuarios     │    │  roles_instancia  │    │  usuarios_roles  │   │
│  ├──────────────┤    ├──────────────────┤    ├──────────────────┤   │
│  │  id (PK)     │───►│  id (PK)         │◄───│  usuario_id (FK) │   │
│  │  slug        │    │  slug            │    │  rol_id (FK)     │   │
│  │  email (UQ)  │    │  codigo          │    │  entidad_tipo    │   │
│  │  password    │    │  nombre          │    │  entidad_id      │   │
│  │  nombre      │    │  jerarquia       │    │  asignado_por    │   │
│  │  apellido    │    │  activo          │    └──────────────────┘   │
│  │  activo      │    └──────────────────┘          │                │
│  └──────────────┘                                  │                │
│         │                                          │                │
│         │  ┌────────────────────┐                  │                │
│         │  │  password_resets   │                  │                │
│         │  ├────────────────────┤                  │                │
│         │  │  id                │                  │                │
│         └──│  usuario_id (FK)   │                  │                │
│            │  token (UQ)        │                  │                │
│            │  expira            │                  │                │
│            └────────────────────┘                  │                │
│                                                    │                │
│  ┌────────────────┐   ┌──────────────────┐         │                │
│  │  estructura_    │   │  cursos          │         │                │
│  │  academica     │   ├──────────────────┤         │                │
│  ├────────────────┤   │  id (PK)         │         │                │
│  │  id (PK)       │◄──│  estructura_id   │         │                │
│  │  slug          │   │  nombre          │         │                │
│  │  nivel         │   │  jornada         │         │                │
│  │  nombre        │   │  activo          │         │                │
│  │  nombre_tipo   │   └────────┬─────────┘         │                │
│  │  padre_id      │            │                   │                │
│  └────────────────┘            │                   │                │
│                                ▼                   │                │
│  ┌────────────────┐   ┌──────────────────┐         │                │
│  │  materias      │   │  curso_materias   │         │                │
│  ├────────────────┤   ├──────────────────┤         │                │
│  │  id (PK)       │◄──│  materia_id (FK) │         │                │
│  │  slug          │   │  curso_id (FK)   │         │                │
│  │  nombre        │   │  docente_id (FK)─┼─────────┘                │
│  │  activo        │   └──────────────────┘                          │
│  └────────────────┘                                                 │
│                                                                     │
│  ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │  evaluaciones   │   │  actividades     │   │  notas           │   │
│  ├────────────────┤   ├──────────────────┤   ├──────────────────┤   │
│  │  id (PK)       │   │  id (PK)         │   │  id (PK)         │   │
│  │  curso_id (FK) │   │  evaluacion_id   │   │  actividad_id(FK)│   │
│  │  materia_id(FK)│   │  nombre          │   │  estudiante_id   │   │
│  │  nombre        │   │  orden           │   │  val             │   │
│  │  tipo          │   │  max_puntaje     │   │  UNIQUE(act,est) │   │
│  │  peso          │──►│  ...             │──►└──────────────────┘   │
│  │  periodo       │   └──────────────────┘         │                │
│  └────────────────┘                                │                │
│                                                    ▼                │
│  ┌────────────────┐                          ┌──────────────────┐   │
│  │  asistencia    │                          │  audit_log       │   │
│  ├────────────────┤                          ├──────────────────┤   │
│  │  id (PK)       │                          │  id (PK)         │   │
│  │  estudiante_id │                          │  usuario_id      │   │
│  │  materia_id    │                          │  accion          │   │
│  │  fecha         │                          │  tabla           │   │
│  │  estado        │                          │  registro_id     │   │
│  └────────────────┘                          │  valor_anterior  │   │
│                                              │  valor_nuevo     │   │
│  ┌────────────────┐                          │  ip              │   │
│  │  observaciones │                          │  creado          │   │
│  ├────────────────┤                          └──────────────────┘   │
│  │  id (PK)       │                                                   │
│  │  estudiante_id │  ┌──────────────────┐                            │
│  │  materia_id    │  │  compromisos     │                            │
│  │  texto         │  ├──────────────────┤                            │
│  │  autor_id      │  │  id (PK)         │                            │
│  │  fecha         │  │  estudiante_id   │                            │
│  └────────────────┘  │  titulo          │                            │
│                      │  descripcion     │                            │
│  ┌────────────────┐  │  fecha           │                            │
│  │  config_        │  │  estado          │                            │
│  │  institucion   │  └──────────────────┘                            │
│  ├────────────────┤                                                   │
│  │  id (PK)       │  ┌──────────────────┐                            │
│  │  slug (UQ)     │  │  horarios_curso  │                            │
│  │  tipo_evaluacion│  ├──────────────────┤                            │
│  │  ...            │  │  id (PK)         │                            │
│  └────────────────┘  │  curso_id        │                            │
│                      │  dia             │                            │
│  ┌────────────────┐  │  franja          │                            │
│  │  comunicaciones │  │  materia_id      │                            │
│  ├────────────────┤  │  docente_id      │                            │
│  │  id (PK)        │  └──────────────────┘                            │
│  │  autor_id       │                                                   │
│  │  titulo         │  ┌──────────────────┐                            │
│  │  contenido      │  │  comunicaciones_ │                            │
│  │  destinatario   │  │  leidas          │                            │
│  │  prioridad      │  ├──────────────────┤                            │
│  │  estado         │  │  comunicacion_id │                            │
│  │  fecha_creacion │  │  usuario_id      │                            │
│  └────────────────┘  │  fecha_lectura   │                            │
│                      └──────────────────┘                            │
│  ┌────────────────┐                                                   │
│  │  canales       │  ┌──────────────────┐                            │
│  ├────────────────┤  │  canal_miembros  │                            │
│  │  id (PK)       │──┤  canal_id        │                            │
│  │  slug          │  │  usuario_id      │                            │
│  │  tipo          │  │  fecha_ingreso   │                            │
│  │  nombre        │  └──────────────────┘                            │
│  │  curso_id      │             │                                    │
│  │  materia_id    │             ▼                                    │
│  └────────────────┘  ┌──────────────────┐                            │
│                      │  mensajes_canal  │                            │
│                      ├──────────────────┤                            │
│                      │  id (PK)         │                            │
│                      │  canal_id        │                            │
│                      │  autor_id        │                            │
│                      │  mensaje         │                            │
│                      │  fecha           │                            │
│                      └──────────────────┘                            │
│                             │                                         │
│                             ▼                                         │
│                      ┌──────────────────┐                            │
│                      │  mensajes_leidos │                            │
│                      ├──────────────────┤                            │
│                      │  mensaje_id      │                            │
│                      │  usuario_id      │                            │
│                      └──────────────────┘                            │
│                                                                     │
│  ┌────────────────┐                                                 │
│  │  notificaciones │                                                 │
│  ├────────────────┤                                                 │
│  │  id (PK)       │                                                 │
│  │  usuario_id    │                                                 │
│  │  titulo        │                                                 │
│  │  mensaje       │                                                 │
│  │  tipo          │                                                 │
│  │  leida         │                                                 │
│  │  fecha_creacion│                                                 │
│  └────────────────┘                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 Resumen de tablas

| Tabla | Propósito | Tipo |
|-------|-----------|------|
| `instituciones` | Catálogo de instituciones | Maestra |
| `admins_globales` | Administradores del sistema | Maestra |
| `usuarios` | Todos los usuarios de una institución | Por instancia |
| `roles_instancia` | Roles personalizados por institución | Por instancia |
| `usuarios_roles` | Asignación de roles a usuarios | Por instancia |
| `password_resets` | Tokens de recuperación | Por instancia |
| `config_institucion` | Configuración de la institución | Por instancia |
| `estructura_academica` | Nodos jerárquicos (facultades, programas) | Por instancia |
| `cursos` | Cursos/grupos | Por instancia |
| `materias` | Catálogo de materias | Por instancia |
| `curso_materias` | Asignación materia-curso-docente | Por instancia |
| `evaluaciones` | Evaluaciones por curso-materia | Por instancia |
| `actividades` | Actividades dentro de evaluaciones | Por instancia |
| `notas` | Calificaciones de estudiantes en actividades | Por instancia |
| `asistencia` | Registro de asistencia | Por instancia |
| `observaciones` | Observaciones por estudiante | Por instancia |
| `compromisos` | Actas de compromiso | Por instancia |
| `horarios_curso` | Horarios por curso | Por instancia |
| `comunicaciones` | Comunicados oficiales | Por instancia |
| `comunicaciones_leidas` | Acuse de recibo de comunicados | Por instancia |
| `canales` | Canales de conversación | Por instancia |
| `canal_miembros` | Miembros de canales | Por instancia |
| `mensajes_canal` | Mensajes en canales | Por instancia |
| `mensajes_leidos` | Lectura de mensajes | Por instancia |
| `notificaciones` | Notificaciones del sistema | Por instancia |
| `audit_log` | Registro de auditoría | Por instancia |

---

## 9. Estrategia de Escalabilidad

### 9.1 Dimensiones de escala

| Dimensión | Escala actual | Escala objetivo | Estrategia |
|-----------|--------------|----------------|------------|
| Instituciones | Decenas | Miles | Una DB por institución. La DB maestra no es cuello de botella. |
| Usuarios por institución | ~200 | ~10,000 | SQLite con WAL soporta cientos de lecturas concurrentes. Para >500 usuarios concurrentes, migrar a PostgreSQL. |
| Requests por segundo | ~10 | ~100 | Flask + Waitress/Gunicorn. Stateless (sesión en cookies). |
| Almacenamiento | MB | GB por institución | SQLite soporta hasta 140TB teóricos. En la práctica, alertar cuando la DB supere 1GB y ofrecer migración a PostgreSQL. |
| Archivos (logos, futuros) | Local | CDN | Los archivos estáticos (logos) se sirven desde Flask. Futuro: S3/Cloudflare. |

### 9.2 SQLite en producción — lineamientos

```python
# Cada conexión debe configurarse así:
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL")        # Write-Ahead Logging: lecturas no bloquean escrituras
conn.execute("PRAGMA synchronous=NORMAL")      # Balance seguridad/rendimiento (WAL mode)
conn.execute("PRAGMA busy_timeout=5000")       # Esperar 5s si la DB está bloqueada
conn.execute("PRAGMA foreign_keys=ON")         # Integridad referencial
conn.execute("PRAGMA cache_size=-8000")        # 8MB de caché
conn.row_factory = sqlite3.Row                 # Acceso por nombre de columna
```

### 9.3 Estrategia de crecimiento

```
Fase 1 (hoy): SQLite por institución
  ├── Máximo: ~500 usuarios concurrentes por institución
  ├── Backup: copia del archivo .db
  └── Ideal para: colegios, institutos pequeños

Fase 2 (cuando una institución supere 500 concurrentes):
  └── Migrar esa institución a PostgreSQL
      ├── Misma API, mismo esquema (adaptar tipos)
      ├── Script de migración: SQLite → PostgreSQL
      └── La instancia sigue funcionando igual, solo cambia el motor de DB

Fase 3 (cuando el sistema tenga 100+ instituciones grandes):
  └── Separar master.db a PostgreSQL
      └── Las instituciones pueden estar en SQLite o PostgreSQL según su tamaño
```

### 9.4 Punto de quiebre y alertas

```python
def check_db_health(slug):
    """Verificar salud de la base de datos de una institución."""
    db_path = os.path.join(DB_FOLDER, f'{slug}.db')
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    conn = conectar(slug)
    usuarios = conn.execute('SELECT COUNT(*) as c FROM usuarios').fetchone()['c']
    conn.close()

    alerts = []
    if size_mb > 1000:  # 1GB
        alerts.append(f"DB supera 1GB ({size_mb:.0f}MB). Considerar migrar a PostgreSQL.")
    if usuarios > 500:
        alerts.append(f"Más de 500 usuarios ({usuarios}). Monitorear rendimiento.")
    if size_mb > 5000:  # 5GB
        alerts.append(f"DB crítica ({size_mb:.0f}MB). Migrar a PostgreSQL urgentemente.")

    return {'size_mb': size_mb, 'usuarios': usuarios, 'alerts': alerts}
```

---

## 10. Estrategia de Migraciones

### 10.1 Sistema de versiones

Cada base de datos institucional tiene un número de versión de esquema (`schema_version` en la tabla `instituciones` de master.db y también almacenado en la propia DB institucional).

```sql
-- Tabla de metadata en cada DB institucional
CREATE TABLE schema_meta (
    version INTEGER NOT NULL,
    applied_at TEXT DEFAULT (datetime('now','localtime'))
);
```

### 10.2 Flujo de migración

```python
# En cada init_db():
def init_db(slug):
    conn = conectar(slug)

    # Crear tabla de metadata si no existe
    conn.execute('''CREATE TABLE IF NOT EXISTS schema_meta (
        version INTEGER NOT NULL,
        applied_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    # Obtener versión actual
    row = conn.execute('SELECT MAX(version) as v FROM schema_meta').fetchone()
    current_version = row['v'] if row['v'] else 0

    # Ejecutar migraciones pendientes
    for version in range(current_version + 1, SCHEMA_VERSION + 1):
        migracion = MIGRACIONES.get(version)
        if migracion:
            logger.info(f"Migrando {slug} a versión {version}...")
            migracion(conn)
            conn.execute('INSERT INTO schema_meta (version) VALUES (?)', (version,))
            conn.commit()
            logger.info(f"  → {slug} ahora en versión {version}")

    conn.close()
```

### 10.3 Migraciones definidas

```python
SCHEMA_VERSION = 10  # Versión más reciente

MIGRACIONES = {
    # Versiones 1-5: esquema legacy (actual, no tocar)
    # 1: Creación inicial (profesores, alumnos, etc.)
    # 2: Comunicaciones
    # 3: Canales y mensajes
    # 4: Notificaciones
    # 5: Migraciones de columnas

    6: lambda c: c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        email TEXT NOT NULL,
        password_hash TEXT,
        nombre TEXT NOT NULL,
        apellido TEXT DEFAULT '',
        tipo_documento TEXT DEFAULT '',
        documento TEXT DEFAULT '',
        telefono TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        activo INTEGER DEFAULT 1,
        creado TEXT DEFAULT (datetime('now','localtime')),
        actualizado TEXT DEFAULT (datetime('now','localtime')),
        ultimo_acceso TEXT,
        UNIQUE(slug, email)
    )'''),

    7: lambda c: c.execute('''CREATE TABLE IF NOT EXISTS roles_base (
        codigo TEXT PRIMARY KEY,
        nombre_default TEXT NOT NULL,
        nivel INTEGER NOT NULL,
        descripcion TEXT
    )'''),
    # ... insertar roles por defecto

    8: lambda c: c.execute('''CREATE TABLE IF NOT EXISTS roles_instancia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        codigo TEXT NOT NULL,
        nombre TEXT NOT NULL,
        jerarquia INTEGER DEFAULT 1,
        activo INTEGER DEFAULT 1,
        UNIQUE(slug, codigo)
    )'''),

    9: lambda c: c.execute('''CREATE TABLE IF NOT EXISTS usuarios_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        rol_id INTEGER NOT NULL,
        entidad_tipo TEXT,
        entidad_id INTEGER,
        asignado_por INTEGER,
        creado TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(usuario_id, rol_id, entidad_tipo, entidad_id)
    )'''),

    10: lambda c: c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        accion TEXT NOT NULL,
        tabla TEXT NOT NULL,
        registro_id INTEGER,
        valor_anterior TEXT,
        valor_nuevo TEXT,
        ip TEXT,
        creado TEXT DEFAULT (datetime('now','localtime'))
    )'''),
    # 11: audit_log index
}
```

### 10.4 Principios de migración

1. **Nunca eliminar una tabla existente** en una migración automática. Solo crear nuevas tablas y columnas.
2. **Nunca renombrar una tabla existente** en una migración automática. La migración de datos es un script manual supervisado.
3. **Toda migración debe ser idempotente**: ejecutarla N veces produce el mismo resultado que ejecutarla 1 vez.
4. **Las migraciones no deben tener dependencias externas** (API, red, archivos). Solo SQL.
5. **Cada migración debe poder revertirse** teóricamente, aunque en la práctica no implementamos rollback automático.

---

## 11. Estrategia de Auditoría Ampliada

### 11.1 ¿Qué se audita?

| Acción | Tabla auditada | Datos registrados |
|--------|---------------|-------------------|
| Crear/editar/eliminar nota | `notas` | `valor_anterior`, `valor_nuevo`, `actividad_id`, `estudiante_id` |
| Crear/editar evaluación | `evaluaciones` | `nombre`, `peso`, `tipo`, `curso_id`, `materia_id` |
| Crear/editar actividad | `actividades` | `nombre`, `orden`, `max_puntaje` |
| Marcar asistencia | `asistencia` | `fecha`, `estado`, `estudiante_id` (solo si se modifica una existente) |
| Crear observación | `observaciones` | `texto_resumen`, `estudiante_id` |
| Publicar/archivar comunicado | `comunicaciones` | `estado` anterior → nuevo |
| Inicio/cierre de sesión | — | `accion`: 'login', 'logout' |
| Crear/eliminar usuario | `usuarios` | `email`, `nombre` |
| Asignar/remover rol | `usuarios_roles` | `rol_id`, `entidad_tipo`, `entidad_id` |
| Cambiar configuración | `config_institucion` | `clave`, `valor_anterior`, `valor_nuevo` |

### 11.2 Estructura de audit_log

```sql
CREATE TABLE audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER,                 -- NULL para acciones del sistema
    accion          TEXT NOT NULL,            -- 'create', 'update', 'delete', 'login', 'logout'
    tabla           TEXT NOT NULL,            -- 'notas', 'evaluaciones', etc.
    registro_id     INTEGER,                 -- ID del registro afectado
    valor_anterior  TEXT,                    -- JSON con valores anteriores
    valor_nuevo     TEXT,                    -- JSON con valores nuevos
    ip              TEXT,                    -- Dirección IP del usuario
    user_agent      TEXT,                    -- Navegador/agente
    creado          TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX idx_audit_tabla ON audit_log(tabla, registro_id);
CREATE INDEX idx_audit_usuario ON audit_log(usuario_id);
CREATE INDEX idx_audit_fecha ON audit_log(creado);
```

### 11.3 Helper de auditoría

```python
def audit(slug, usuario_id, accion, tabla, registro_id, valor_anterior=None, valor_nuevo=None):
    """
    Registrar una acción de auditoría.

    Ejemplos:
        audit(slug, uid, 'update', 'notas', nid,
              {'val': 7.5}, {'val': 8.0})

        audit(slug, uid, 'login', 'sesion', None, None, None)
    """
    valor_anterior_json = json.dumps(valor_anterior) if valor_anterior else None
    valor_nuevo_json = json.dumps(valor_nuevo) if valor_nuevo else None

    conn = conectar(slug)
    conn.execute(
        'INSERT INTO audit_log (usuario_id, accion, tabla, registro_id, valor_anterior, valor_nuevo, ip, user_agent) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (usuario_id, accion, tabla, registro_id, valor_anterior_json, valor_nuevo_json,
         request.remote_addr, request.user_agent.string if request.user_agent else None)
    )
    conn.commit()
    conn.close()
```

### 11.4 Vista de auditoría para el rector

```python
@app.route('/<slug>/rector/auditoria')
@requiere_permiso('audit.log.view')
def rector_auditoria(slug):
    filtros = {}
    if request.args.get('tabla'):
        filtros['tabla'] = request.args.get('tabla')
    if request.args.get('usuario_id'):
        filtros['usuario_id'] = int(request.args.get('usuario_id'))
    if request.args.get('desde'):
        filtros['desde'] = request.args.get('desde')
    if request.args.get('hasta'):
        filtros['hasta'] = request.args.get('hasta')

    page = int(request.args.get('page', 1))
    limit = 50
    offset = (page - 1) * limit

    conn = conectar(slug)
    query = 'SELECT a.*, u.nombre as usuario_nombre FROM audit_log a LEFT JOIN usuarios u ON a.usuario_id = u.id WHERE 1=1'
    params = []
    for key, val in filtros.items():
        if key == 'tabla':
            query += ' AND a.tabla = ?'
            params.append(val)
        elif key == 'usuario_id':
            query += ' AND a.usuario_id = ?'
            params.append(val)
        elif key == 'desde':
            query += ' AND a.creado >= ?'
            params.append(val)
        elif key == 'hasta':
            query += ' AND a.creado <= ?'
            params.append(val + ' 23:59:59')
    query += ' ORDER BY a.creado DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    registros = conn.execute(query, params).fetchall()
    conn.close()

    return render_template('rector/auditoria.html',
                         registros=registros,
                         filtros=filtros,
                         page=page,
                         slug=slug)
```

---

## 12. Convenciones de Desarrollo

### 12.1 Estructura del proyecto

```
Lumini/
├── flask_app.py              ← Único archivo de aplicación (por ahora)
├── master.db                 ← DB maestra
├── colegios_db/              ← DBs por institución
├── static/
│   ├── css/
│   │   ├── lumini.css        ← Estilos principales
│   │   └── login.css         ← Estilos de login
│   ├── js/
│   │   ├── lumini.js         ← Funciones globales
│   │   ├── canales.js        ← Sistema de canales
│   │   └── comunicados.js    ← Comunicados
│   └── logos/                ← Logos institucionales
├── templates/
│   ├── base.html             ← Template base (herencia)
│   ├── components/           ← Componentes reutilizables (toast, sidebar, etc.)
│   ├── login.html
│   ├── admin/                ← Administración global
│   ├── rector/               ← Rector / Dirección
│   ├── authority/            ← Autoridades académicas
│   ├── docente/              ← Docentes
│   ├── estudiante/           ← Estudiantes
│   └── guardian/             ← Acudientes (futuro)
├── docs/                     ← Documentación
├── .env                      ← Variables de entorno
└── requirements.txt          ← Dependencias Python
```

### 12.2 Convenciones de código Python

#### Nombres
```python
# Archivos: snake_case
# flask_app.py

# Variables y funciones: snake_case
def conectar_base(slug): ...
def get_usuario_actual(): ...

# Clases: PascalCase (solo para servicios complejos)
class ConfigService: ...

# Constantes: UPPER_SNAKE_CASE
SCHEMA_VERSION = 10
DB_FOLDER = 'colegios_db'

# Rutas Flask: snake_case con nombre descriptivo
@app.route('/<slug>/docente/notas')
def docente_notas(slug): ...
```

#### Organización de imports
```python
# 1. Standard library
import os, json, time, hashlib, secrets, logging
from datetime import datetime, timedelta

# 2. Third-party
from flask import Flask, render_template, request, session, jsonify

# 3. Local (cuando el proyecto crezca)
# from services.auth import AuthService
```

#### Estilo de rutas
```python
# Una ruta = una función. No mezclar GET/POST en el mismo handler.
@app.route('/<slug>/ruta', methods=['GET'])
def ruta_get(slug):
    ...

@app.route('/<slug>/ruta', methods=['POST'])
def ruta_post(slug):
    ...

# Las rutas POST siempre validan CSRF al inicio.
@app.route('/<slug>/recurso/crear', methods=['POST'])
def recurso_crear(slug):
    if not validar_csrf():
        return jsonify({'error': 'CSRF inválido'}), 400
    ...
```

### 12.3 Convenciones de JavaScript

```javascript
// Nombres: camelCase
function crearSistemaCanales(opts) { ... }
function obtenerMensajes(canalId) { ... }

// Constantes: UPPER_SNAKE_CASE
const POLLING_INTERVAL = 3000;

// Preferir fetch() sobre XMLHttpRequest
async function enviarMensaje(canalId, texto) {
    const resp = await fetch(`/${slug}/api/canales/${canalId}/enviar`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({ mensaje: texto })
    });
    return resp.json();
}

// Event delegation, no onclick en HTML
document.querySelector('#canales-panel').addEventListener('click', (e) => {
    const btn = e.target.closest('.canal-abrir');
    if (btn) abrirCanal(btn.dataset.canalId);
});

// Polling con setTimeout recursivo (no setInterval)
function iniciarPolling() {
    if (pollingTimeout) clearTimeout(pollingTimeout);
    pollingTimeout = setTimeout(async () => {
        await checkNuevosMensajes();
        iniciarPolling();  // Recursivo para control preciso
    }, POLLING_INTERVAL);
}
```

### 12.4 Convenciones de CSS

```css
/* Nombres: kebab-case con prefijo de módulo */
.canales-split { ... }
.canales-sidebar { ... }
.comunicado-prioridad-alta { ... }
.nota-promedio { ... }

/* Variables globales en :root */
:root {
    --primary: #7C3AED;
    --primary-hover: #6D28D9;
    --bg: #0f0f1a;
    --bg-card: #1a1a2e;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --border: #2d2d44;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #ef4444;
    --radius: 8px;
}

/* Los colores institucionales sobreescriben variables */
[data-theme="institucion"] {
    --primary: var(--primary-color-institucion);
    --primary-hover: var(--secondary-color-institucion);
}

/* Sin !important. Sin frameworks CSS. Sin preprocesadores. */
```

### 12.5 Convenciones de base de datos

```sql
-- Nombres de tablas: snake_case, plural
CREATE TABLE usuarios_roles (...);

-- Nombres de columnas: snake_case
usuario_id INTEGER NOT NULL,
fecha_creacion TEXT DEFAULT (datetime('now','localtime'));

-- Primary key siempre 'id' (Integer)
id INTEGER PRIMARY KEY AUTOINCREMENT

-- Foreign keys: {tabla_origen}_id
usuario_id INTEGER REFERENCES usuarios(id)

-- Timestamps en texto ISO (SQLite no tiene tipo DATETIME)
creado TEXT DEFAULT (datetime('now','localtime'))
actualizado TEXT

-- Boolean como INTEGER (0/1)
activo INTEGER DEFAULT 1

-- UNIQUE constraints explícitas
UNIQUE(slug, email)
```

### 12.6 Convenciones de Git

```
Ramas:
  main          ← Código estable en producción
  develop       ← Integración de características
  feature/XXX   ← Nuevas funcionalidades (XXX = nombre corto)
  fix/XXX       ← Corrección de bugs

Commits:
  Formato: tipo(ámbito): mensaje
  Tipos: feat, fix, refactor, docs, style, chore
  Ejemplo: feat(auth): implementar login unificado por email
           fix(grades): corregir cálculo de promedio ponderado

Nunca commitea:
  - Archivos .db (a menos que sean seed)
  - .env
  - __pycache__/
  - logs
```

### 12.7 Estándar de respuestas API (JSON)

```python
# Éxito
{ "ok": true, "data": { ... } }

# Error
{ "ok": false, "error": "Mensaje descriptivo" }

# Lista paginada
{ "ok": true, "data": [...], "page": 1, "total": 50, "pages": 5 }

# Códigos HTTP:
# 200 — Éxito
# 201 — Creado
# 400 — Error de validación (parámetros inválidos)
# 403 — Sin permiso
# 404 — No encontrado
# 409 — Conflicto (duplicado)
# 429 — Demasiadas solicitudes (fuerza bruta)
# 500 — Error interno
```

### 12.8 Pruebas (futuro)

```python
# Cuando se implementen pruebas:
# - tests/ con mirror de estructura del proyecto
# - Una DB de prueba por test (no tocar datos reales)
# - pytest como framework
# - fixtures para crear estado inicial

# def test_login_exitoso():
#     crear_institucion_test('test-slug')
#     crear_usuario_test('test-slug', email='test@test.com', password='123456')
#     # POST /test-slug/login
#     assert session['user_id'] is not None
```

### 12.9 Proceso antes de implementar cualquier cambio

1. **Verificar** que la funcionalidad cumple los 6 criterios de aprobación (sección 1.4 del documento funcional)
2. **Diseñar** en este documento técnico (o en un anexo) si afecta la arquitectura
3. **Crear rama** `feature/XXX` o `fix/XXX`
4. **Implementar** siguiendo las convenciones
5. **Verificar** que no rompe funcionalidad existente (probar con DB real copiada)
6. **Actualizar** `schema_version` si agrega tablas/columnas
7. **Commit** con mensaje descriptivo
8. **Solicitar revisión** antes de mergear a develop

---

*Documento generado el 27 de junio de 2026.*
*Versión 1.0 — Pendiente de aprobación para inicio de implementación de P0.*

*Una vez aprobado, este documento es la única fuente de verdad arquitectónica. Cualquier desviación debe ser documentada como enmienda y aprobada antes de ser implementada.*
