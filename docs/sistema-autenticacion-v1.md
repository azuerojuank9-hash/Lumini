# LUMINI — Sistema de Autenticación v1.0

> **Propósito**: Definir el sistema de autenticación configurable por institución, sin implementar código. Este documento es la base técnica para P0.5.
>
> **Estado**: Diseño — pendiente de aprobación para implementación.

---

## Índice

1. [Objetivos](#1-objetivos)
2. [Tipos de Autenticación](#2-tipos-de-autenticación)
3. [Compatibilidad con el Sistema Actual](#3-compatibilidad-con-el-sistema-actual)
4. [Flujo Completo de Inicio de Sesión](#4-flujo-completo-de-inicio-de-sesión)
5. [Recuperación de Cuenta](#5-recuperación-de-cuenta)
6. [Cambio de Contraseña](#6-cambio-de-contraseña)
7. [Gestión de Sesiones](#7-gestión-de-sesiones)
8. [Recordar Sesión](#8-recordar-sesión)
9. [Cierre de Sesión](#9-cierre-de-sesión)
10. [Bloqueo por Intentos Fallidos](#10-bloqueo-por-intentos-fallidos)
11. [Doble Factor (Preparación)](#11-doble-factor-preparación)
12. [Integración con Permisos (RBAC)](#12-integración-con-permisos-rbac)
13. [Integración con Auditoría](#13-integración-con-auditoría)
14. [Integración Multiinstitución](#14-integración-multiinstitución)
15. [Configuración por Institución](#15-configuración-por-institución)

---

## 1. Objetivos

### 1.1 Objetivo general

Implementar un sistema de autenticación configurable por institución que soporte múltiples métodos de ingreso según el rol del usuario, manteniendo compatibilidad total con el sistema legacy.

### 1.2 Objetivos específicos

1. **Configurabilidad**: cada institución define cómo autentica cada rol, sin modificar código.
2. **Multi-método**: soportar email, usuario, código institucional, documento de identidad y PIN, según la configuración.
3. **Compatibilidad**: mantener el sistema legacy funcionando en paralelo durante la migración.
4. **Seguridad**: hash con salt, bloqueo por fuerza bruta, CSRF en formularios, sesiones HttpOnly.
5. **Trazabilidad**: cada intento de login (éxito o fallo) queda registrado en auditoría.
6. **Preparación para 2FA**: la arquitectura debe permitir agregar doble factor sin reescribir el sistema.

### 1.3 No objetivos

- No reemplazar el sistema legacy de inmediato (convivencia).
- No implementar SSO, OAuth, LDAP ni SAML en esta versión.
- No implementar 2FA funcional (solo preparación arquitectónica).
- No implementar registro público (solo invitación).

---

## 2. Tipos de Autenticación

### 2.1 Métodos soportados

| Código | Método | Input | Almacenamiento |
|--------|--------|-------|----------------|
| `email` | Email + contraseña | Campo email, campo password | `usuarios.email` + `usuarios.password_hash` |
| `username` | Usuario + contraseña | Campo usuario, campo password | `usuarios.username` + `usuarios.password_hash` |
| `email_or_username` | Email o usuario + contraseña | Campo único, campo password | Busca por email o username |
| `document` | Documento de identidad + contraseña | Campo documento, campo password | `usuarios.documento` + `usuarios.password_hash` |
| `code` | Código institucional + contraseña | Campo código, campo password | `usuarios.codigo_institucional` + `usuarios.password_hash` |
| `pin` | PIN (solo estudiantes, legacy) | Campo nombre, campo pin | `alumnos.pin` (tabla legacy) |

### 2.2 Método por defecto por rol

| Rol | Método por defecto | Alternativas configurables |
|-----|-------------------|---------------------------|
| `admin` | `email` | — |
| `rector` | `email_or_username` | `email`, `username` |
| `authority` | `email_or_username` | `email`, `username` |
| `teacher` | `email_or_username` | `email`, `username`, `document` |
| `student` | `code` | `document`, `username`, `email`, `pin` (legacy) |
| `guardian` | `email` | `document` |

### 2.3 Flujo de selección de método

```
Usuario ingresa a /{slug}/login
         │
         ▼
Cargar config institucional → auth_config.json
         │
         ▼
Mostrar formulario según rol:
  - Si el usuario selecciona un rol específico → mostrar campos según método configurado
  - Si no selecciona rol → campo único de identificación + password
    (el sistema detecta automáticamente en qué tabla/usuario existe)
         │
         ▼
Procesar login:
  1. Identificar método según rol (si se especificó) o detectar automáticamente
  2. Buscar usuario según el método
  3. Verificar contraseña
  4. Crear sesión
```

---

## 3. Compatibilidad con el Sistema Actual

### 3.1 Estrategia de convivencia

El nuevo sistema de autenticación **se agrega como complemento**, no como reemplazo inmediato.

| Componente legacy | Acción |
|-------------------|--------|
| `/<slug>/login` (profesor/estudiante) | Se mantiene activo. El nuevo login se sirve en la misma URL con diseño unificado. |
| `/<slug>/rector/login` | Se mantiene activo. Redirige al nuevo login unificado. |
| `/<slug>/directora/login` | Se mantiene activo. Redirige al nuevo login unificado. |
| `alumnos.pin` | Se mantiene como método `pin` para estudiantes. |
| `pregunta_secreta` / `respuesta_secreta` | Se mantiene como fallback de recuperación. El nuevo sistema prioriza email. |
| Sesiones legacy (`profesor_id_*`, etc.) | Se mantienen. El nuevo sistema crea sesiones en ambos formatos durante la migración. |

### 3.2 Migración progresiva de usuarios

```
Fase 1: Nuevo login convive con legacy
  - Usuarios existentes: siguen usando su método actual
  - Usuarios nuevos: se crean en la tabla `usuarios`
  - El login unificado detecta automáticamente si el usuario está en `usuarios` o en tablas legacy

Fase 2: Migración asistida
  - Script que crea registros en `usuarios` a partir de `profesores`, `alumnos`, etc.
  - Genera email automático para quienes no tengan
  - Asigna rol en `usuarios_roles`

Fase 3: Legacy congelado
  - Tablas legacy se marcan como solo lectura
  - Todo login pasa por `usuarios`

Fase 4: Legacy eliminado
  - Tablas legacy eliminadas (versión mayor)
```

### 3.3 Detector automático de usuario

```python
def buscar_usuario(slug, identificador):
    """
    Busca un usuario en todas las tablas (nuevas y legacy).
    Retorna (tabla_origen, id, datos_usuario, password_hash, tipo_usuario)
    
    Orden de búsqueda:
    1. usuarios (tabla nueva) — por email, username, documento o código
    2. profesores — por usuario o email
    3. rectores — por usuario o email
    4. directoras — por usuario o email
    5. alumnos — por nombre (compatible con PIN legacy)
    """
    conn = conectar(slug)
    
    # 1. Buscar en tabla nueva
    for campo in ['email', 'username', 'documento', 'codigo_institucional']:
        u = conn.execute(
            f'SELECT * FROM usuarios WHERE {campo}=? AND activo=1', 
            (identificador,)
        ).fetchone()
        if u:
            return ('usuarios', u)
    
    # 2. Buscar en tablas legacy
    for tabla, campo_usuario in [
        ('rectores', 'usuario'),
        ('rectores', 'email'),
        ('profesores', 'usuario'),
        ('profesores', 'email'),
        ('directoras', 'usuario'),
        ('directoras', 'email'),
    ]:
        u = conn.execute(
            f'SELECT * FROM {tabla} WHERE {campo_usuario}=? AND activo=1',
            (identificador,)
        ).fetchone()
        if u:
            return (tabla, u)
    
    # 3. Buscar alumno por nombre (PIN legacy)
    a = conn.execute(
        'SELECT * FROM alumnos WHERE nombre=? AND activo=1',
        (identificador,)
    ).fetchone()
    if a:
        return ('alumnos', a)
    
    conn.close()
    return (None, None)
```

---

## 4. Flujo Completo de Inicio de Sesión

### 4.1 Diagrama

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE INICIO DE SESIÓN                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  GET /{slug}/login                                                      │
│       │                                                                  │
│       ▼                                                                  │
│  Renderizar login_unificado.html                                        │
│  - Campo único: "Correo, usuario, documento o código"                   │
│  - Campo: contraseña                                                    │
│  - Botón: "Ingresar"                                                    │
│  - Link: "¿Olvidó su contraseña?"                                       │
│  - (Opcional) Selector de rol para autenticación específica             │
│       │                                                                  │
│       ▼                                                                  │
│  POST /{slug}/login                                                     │
│       │                                                                  │
│       ├── Validar CSRF ──── Fallo ──── 400                              │
│       │                                                                  │
│       ├── Verificar IP bloqueada ──── Sí ──── Mostrar tiempo restante   │
│       │                                                                  │
│       ├── Buscar usuario (buscar_usuario) ──── No existe ────           │
│       │   "Credenciales incorrectas" (genérico, sin revelar existencia) │
│       │                                                                  │
│       ├── Verificar método según rol/config                             │
│       │   ├── Si el usuario está en `usuarios`:                         │
│       │   │   - Verificar password_hash (hash_pw)                       │
│       │   │   - Si necesita rehash, actualizar                          │
│       │   │                                                             │
│       │   ├── Si el usuario está en tabla legacy:                       │
│       │   │   - Verificar password (verificar_pw)                       │
│       │   │   - Si necesita rehash, actualizar                          │
│       │   │                                                             │
│       │   └── Si es alumno con PIN:                                     │
│       │       - Verificar PIN (texto plano)                             │
│       │                                                                  │
│       ├── Verificar contraseña ──── No coincide ────                    │
│       │   registrar_fallo(), audit_log('login_failed'), "Credenciales..."│
│       │                                                                  │
│       ├── (Éxito)                                                        │
│       │   ├── limpiar_intentos()                                        │
│       │   ├── audit_log('login_success')                                │
│       │   ├── Si está en tabla legacy y no en usuarios:                 │
│       │   │   └── Opcional: crear registro en usuarios + usuarios_roles │
│       │   ├── Crear sesión:                                             │
│       │   │   ├── session['user_id'] = usuario.id                       │
│       │   │   ├── session['slug'] = slug                                │
│       │   │   ├── session['auth_method'] = método usado                │
│       │   │   └── session.permanent = True (según "recordar sesión")   │
│       │   ├── Actualizar ultimo_acceso                                  │
│       │   └── Redirect a dashboard según rol                            │
│       │                                                                  │
│       └── Auditoría registra: IP, user-agent, método, éxito/fallo       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Pseudocódigo de la ruta de login

```python
@app.route('/<slug>/login', methods=['GET', 'POST'])
def login_unificado(slug):
    require_colegio(slug)
    
    # Obtener configuración de autenticación de la institución
    auth_config = config_get_auth(slug)
    
    if request.method == 'POST':
        if not validar_csrf():
            return 'Error de seguridad', 400
        
        identificador = request.form.get('identificador', '').strip()
        password = request.form.get('password', '')
        rol_seleccionado = request.form.get('rol', '')
        
        # Validar IP
        tiempo_bloqueo = ip_bloqueada(request.remote_addr, slug)
        if tiempo_bloqueo:
            return render_template('login.html', error=f'Demasiados intentos. Espere {tiempo_bloqueo}s.')
        
        # Buscar usuario
        tabla, usuario = buscar_usuario(slug, identificador)
        if not tabla or not usuario:
            registrar_fallo(request.remote_addr, slug)
            audit_log(slug, None, 'login_failed', 'auth', 
                     valor_nuevo={'identificador': identificador, 'motivo': 'not_found'})
            return render_template('login.html', error='Credenciales incorrectas.')
        
        # Verificar contraseña según el origen
        valido = False
        if tabla == 'usuarios':
            valido = verificar_pw(password, usuario['password_hash'])
            if valido and necesita_rehash(usuario['password_hash']):
                actualizar_password_hash(slug, usuario['id'], password)
        elif tabla in ('rectores', 'profesores', 'directoras'):
            valido = verificar_pw(password, usuario['password'])
            if valido and necesita_rehash(usuario['password']):
                actualizar_password_legacy(slug, tabla, usuario['id'], password)
        elif tabla == 'alumnos':
            valido = (password == usuario['pin'])  # PIN legacy en texto plano
        
        if not valido:
            registrar_fallo(request.remote_addr, slug)
            audit_log(slug, None, 'login_failed', 'auth',
                     valor_nuevo={'identificador': identificador, 'motivo': 'wrong_password'})
            return render_template('login.html', error='Credenciales incorrectas.')
        
        # Éxito
        limpiar_intentos(request.remote_addr, slug)
        
        # Crear sesión unificada
        session['slug'] = slug
        session['user_id'] = usuario['id']
        session['tabla_origen'] = tabla  # 'usuarios', 'rectores', etc.
        session['nombre'] = usuario['nombre']
        session['auth_method'] = 'password'
        session.permanent = True
        
        # Si el usuario está en legacy, también mantener sesión legacy
        # (para compatibilidad con rutas existentes)
        if tabla == 'profesores':
            session[f'profesor_id_{slug}'] = usuario['id']
            session[f'rol_{slug}'] = 'profesor'
        elif tabla == 'alumnos':
            session[f'alumno_id_{slug}'] = usuario['id']
            session[f'rol_{slug}'] = 'estudiante'
        elif tabla == 'rectores':
            session[f'rector_id_{slug}'] = usuario['id']
        elif tabla == 'directoras':
            session[f'directora_id_{slug}'] = usuario['id']
        
        # Determinar dashboard
        redirect_url = determinar_dashboard(slug, tabla, usuario)
        
        audit_log(slug, usuario['id'], 'login_success', 'auth',
                 valor_nuevo={'metodo': 'password', 'tabla_origen': tabla})
        
        return redirect(redirect_url)
    
    # GET: mostrar formulario
    return render_template('login_unificado.html',
                         slug=slug,
                         colegio=get_colegio(slug),
                         auth_config=auth_config)
```

### 4.3 Interfaz de login

El template `login_unificado.html` debe:

1. **Campo único de identificación** con placeholder dinámico: "Correo, usuario, documento o código"
2. **Campo de contraseña**
3. **Selector de rol** (opcional, colapsado por defecto) — si el usuario selecciona un rol, el placeholder del campo de identificación cambia según el método configurado para ese rol
4. **Botón "Ingresar"** con indicador de carga
5. **Link "¿Olvidó su contraseña?"**
6. **Selector de tema** (claro/oscuro)
7. **Mensajes de error** genéricos ("Credenciales incorrectas" — nunca revelar si el usuario existe)
8. **Indicador de bloqueo** por fuerza bruta

---

## 5. Recuperación de Cuenta

### 5.1 Flujo

```
1. Usuario hace clic en "¿Olvidó su contraseña?"
2. Ingresa su identificador (email, usuario, documento o código)
3. Sistema:
   a. Busca el identificador en usuarios + tablas legacy
   b. Si encuentra al usuario y tiene email:
      - Genera token único (secrets.token_urlsafe(32))
      - Almacena en password_resets (token, usuario_id, expira=30min)
      - Envía email con link: /{slug}/reset?token=XXX
      - Muestra: "Si el correo está registrado, recibirás un enlace."
   c. Si encuentra al usuario pero NO tiene email:
      - Muestra: "Contacta al administrador de tu institución."
   d. Si NO encuentra al usuario:
      - Misma respuesta genérica que (b): "Si el correo está registrado..."
4. Usuario abre el link:
   a. GET /{slug}/reset?token=XXX → mostrar formulario de nueva contraseña
   b. POST /{slug}/reset → validar token, expiración, nuevo password
   c. Actualizar password_hash en usuarios (o password en tabla legacy)
   d. Marcar token como usado
   e. audit_log('password_reset')
   f. Redirigir a login con mensaje "Contraseña actualizada correctamente"
```

### 5.2 Consideraciones

- **No revelar si el email existe o no** — siempre misma respuesta genérica.
- **Token de un solo uso** — una vez usado, invalidar.
- **Expiración de 30 minutos** — configurable por institución.
- **Si el usuario legacy no tiene email**, mostrar mensaje instructivo (no revelar datos).
- **Para estudiantes con PIN** (sin email), la recuperación debe ser gestionada por el rector/docente.

### 5.3 Tabla password_resets

```sql
CREATE TABLE password_resets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL,
    tabla_origen TEXT DEFAULT 'usuarios',  -- 'usuarios', 'rectores', 'profesores', etc.
    token       TEXT UNIQUE NOT NULL,
    expira      TEXT NOT NULL,
    usado       INTEGER DEFAULT 0,
    creado      TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 6. Cambio de Contraseña

### 6.1 Flujo (usuario autenticado)

```
1. Usuario va a su perfil / configuración
2. Ingresa: contraseña actual + nueva contraseña (x2)
3. Sistema:
   a. Verifica contraseña actual contra password_hash o tabla legacy
   b. Valida nueva contraseña (mínimo 6 caracteres)
   c. Actualiza password_hash (o password en tabla legacy)
   d. audit_log('password_change')
   e. Muestra: "Contraseña actualizada correctamente."
```

### 6.2 Ya implementado (P0.3)

La ruta `/<slug>/rector/configuracion` ya incluye cambio de contraseña para el rector. En P0.5 se extiende a todos los roles con el mismo patrón.

---

## 7. Gestión de Sesiones

### 7.1 Estructura de sesión unificada

```python
# Sesión unificada (nueva)
session['slug']           = 'mi-institucion'
session['user_id']        = 42           # ID en tabla usuarios (o tabla legacy)
session['tabla_origen']   = 'usuarios'   # 'usuarios', 'rectores', 'profesores', etc.
session['nombre']         = 'María López'
session['auth_method']    = 'password'
session['remember']       = True         # Si marcó "recordar sesión"

# Sesiones legacy (mantenidas para compatibilidad)
session[f'profesor_id_{slug}'] = 42      # si el usuario es profesor
session[f'rector_id_{slug}']    = 42     # si el usuario es rector
# ... etc
```

### 7.2 Duración

| Escenario | Duración | Configurable |
|-----------|----------|-------------|
| Sesión normal | 4 horas | `session.permanent_lifetime` |
| "Recordar sesión" | 30 días | `SESSION_COOKIE_REMEMBER_DAYS` en config |

### 7.3 Seguridad de sesión

- Cookies: HttpOnly, SameSite=Lax, Secure en producción
- Regenerar session ID después de login exitoso (`session.regenerate()`)
- Invalidar sesión al cambiar contraseña
- Cerrar sesión elimina todas las claves de sesión (nuevas y legacy)

---

## 8. Recordar Sesión

### 8.1 Implementación

```python
if request.form.get('remember'):
    # Extender duración de la sesión
    app.permanent_session_lifetime = timedelta(days=30)
    session['remember'] = True
else:
    app.permanent_session_lifetime = timedelta(hours=4)
    session['remember'] = False

session.permanent = True  # Activar expiración
```

### 8.2 Consideraciones

- No usar tokens de "remember me" persistentes en cookie (complejidad innecesaria para el alcance actual).
- La sesión Flask ya es una cookie firmada — extender su expiración es suficiente.
- Configurable por institución: `session_duracion_normal` y `session_duracion_recordar`.

---

## 9. Cierre de Sesión

### 9.1 Rutas

```python
@app.route('/<slug>/logout')
def logout(slug):
    """Cierre de sesión unificado."""
    usuario_id = session.get('user_id')
    if usuario_id:
        audit_log(slug, usuario_id, 'logout', 'auth')
    
    # Limpiar TODAS las claves de sesión
    claves = list(session.keys())
    for k in claves:
        if k != '_csrf_token':  # preservar CSRF por si acaso
            session.pop(k, None)
    
    return redirect(url_for('login_unificado', slug=slug))
```

### 9.2 Rutas legacy mantenidas

```python
# Redirigen al logout unificado
@app.route('/<slug>/rector/logout')
def rector_logout_redirect(slug):
    return redirect(url_for('logout', slug=slug))
```

---

## 10. Bloqueo por Intentos Fallidos

### 10.1 Sistema actual (heredado)

El sistema actual ya implementa bloqueo por IP con 5 intentos y 5 minutos de espera. Este sistema se mantiene y se extiende.

### 10.2 Mejoras para P0.5

| Mejora | Detalle |
|--------|---------|
| Bloqueo por usuario+IP | Además de por IP, bloquear combinación usuario+IP |
| Bloqueo progresivo | 5 intentos → 5 min, 10 intentos → 30 min, 15+ → 1 hora |
| Contador por institución | `login_intentos['{slug}_{ip}']` en lugar de solo `{ip}` |
| Notificación al rector | Si un mismo usuario acumula 10+ fallos, notificar al rector |
| Reset de contador | Al hacer login exitoso, limpiar contador de ese usuario+IP |

### 10.3 Estructura de datos (en memoria, no persiste)

```python
login_intentos = {}  # clave: '{slug}_{usuario_id}_{ip}' o '{slug}_{ip}'

# Cada entrada:
{
    'intentos': 3,
    'bloqueado_hasta': None,  # o timestamp
    'ultimo_fallo': '2026-06-27 22:30:00'
}
```

---

## 11. Doble Factor (Preparación)

### 11.1 Arquitectura preparada

El sistema de autenticación debe estar diseñado para que agregar 2FA en el futuro no requiera reescribir el flujo completo.

### 11.2 Puntos de extensión

```python
def verificar_2fa(slug, usuario_id, metodo):
    """
    Punto de extensión para 2FA.
    Por ahora siempre retorna True (sin 2FA).
    En el futuro:
    - Verificar si el usuario tiene 2FA habilitado
    - Verificar el código TOTP
    - Retornar (valido, error)
    """
    return (True, None)

@app.route('/<slug>/login', methods=['POST'])
def login_unificado(slug):
    # ... validación de contraseña ...
    
    if valido:
        valido_2fa, error_2fa = verificar_2fa(slug, usuario['id'], 
                                               auth_config.get('2fa_metodo', 'none'))
        if not valido_2fa:
            return render_template('login_2fa.html', error=error_2fa)
    
    # ... crear sesión ...
```

### 11.3 Tabla preparada (futuro)

```sql
-- No se crea en P0.5. Preparada para versión futura.
CREATE TABLE IF NOT EXISTS usuario_2fa (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id  INTEGER NOT NULL,
    metodo      TEXT NOT NULL DEFAULT 'totp',  -- 'totp', 'email', 'sms'
    secreto     TEXT NOT NULL,
    activo      INTEGER DEFAULT 1,
    creado      TEXT DEFAULT (datetime('now','localtime'))
);
```

---

## 12. Integración con Permisos (RBAC)

### 12.1 Después del login exitoso

Una vez que el usuario es autenticado, el sistema debe:

1. Determinar el rol del usuario (desde `usuarios_roles` o tabla legacy)
2. Cargar los permisos del rol en la sesión (o en `g` local)
3. Verificar acceso al dashboard correspondiente

```python
def determinar_rol_y_permisos(slug, tabla_origen, usuario_id):
    """
    Determina el rol y permisos de un usuario después del login.
    
    Si el usuario está en la tabla nueva 'usuarios':
      - Consulta usuarios_roles + roles_instancia + roles_base
      - Retorna (rol_codigo, rol_nombre, permisos)
    
    Si el usuario está en tabla legacy:
      - Mapea tabla → rol:
        'rectores' → 'rector'
        'profesores' → 'teacher'
        'alumnos' → 'student'
        'directoras' → 'authority'
      - Retorna (rol_codigo, nombre_default, permisos_por_defecto)
    """
    if tabla_origen == 'usuarios':
        roles = obtener_roles_usuario(slug, usuario_id)
        if roles:
            r = roles[0]
            return (r['codigo'], r['rol_nombre'], _permisos_para_rol(r['codigo']))
    
    # Mapeo legacy
    MAPA = {
        'rectores': ('rector', 'Rector'),
        'profesores': ('teacher', 'Docente'),
        'alumnos': ('student', 'Estudiante'),
        'directoras': ('authority', 'Coordinador'),
    }
    if tabla_origen in MAPA:
        codigo, nombre = MAPA[tabla_origen]
        return (codigo, nombre, _permisos_para_rol(codigo))
    
    return (None, None, [])
```

### 12.2 Middleware de permisos

```python
@app.before_request
def cargar_usuario_y_permisos():
    """Cargar usuario actual y permisos antes de cada request."""
    slug = getattr(g, 'slug', None)
    if not slug:
        return
    
    g.usuario = None
    g.rol = None
    g.permisos = []
    
    user_id = session.get('user_id')
    tabla_origen = session.get('tabla_origen')
    
    if user_id and tabla_origen:
        if tabla_origen == 'usuarios':
            g.usuario = obtener_usuario(slug, user_id)
        else:
            # Cargar desde tabla legacy
            g.usuario = cargar_usuario_legacy(slug, tabla_origen, user_id)
        
        codigo_rol, nombre_rol, permisos = determinar_rol_y_permisos(
            slug, tabla_origen, user_id)
        g.rol = codigo_rol
        g.nombre_rol = nombre_rol
        g.permisos = permisos
```

---

## 13. Integración con Auditoría

### 13.1 Eventos de autenticación auditados

| Evento | Datos registrados |
|--------|-------------------|
| `login_success` | usuario_id, método, IP, user-agent, tabla_origen |
| `login_failed` | identificador (nunca contraseña), IP, motivo (not_found / wrong_password) |
| `login_blocked` | IP, tiempo_bloqueo |
| `logout` | usuario_id |
| `password_change` | usuario_id |
| `password_reset_request` | identificador (email/username) |
| `password_reset_complete` | usuario_id |
| `session_expired` | usuario_id (si se puede detectar) |

### 13.2 Helper de auditoría

```python
def audit_auth(slug, usuario_id, evento, detalles=None):
    """Helper específico para eventos de autenticación."""
    audit_log(slug, usuario_id, evento, 'auth', 
             valor_nuevo=detalles)
```

---

## 14. Integración Multiinstitución

### 14.1 Aislamiento

Cada institución tiene:
- Su propia configuración de autenticación (`config_institucion.auth_config_json`)
- Su propia tabla de usuarios (en su `{slug}.db`)
- Su propio registro de intentos fallidos
- Su propio flujo de recovery

### 14.2 Admin global

El administrador global (`admins_globales` en master.db) se autentica por separado en `/admin/login` con su propio método fijo (email + contraseña). No pasa por el login institucional.

### 14.3 Slug en todas las URL

Toda ruta de autenticación incluye `/{slug}/` para mantener el aislamiento. El slug se valida al inicio de cada request.

---

## 15. Configuración por Institución

### 15.1 Estructura en config_institucion

Se agrega un campo `auth_config_json` a la tabla `config_institucion` (migración v11):

```sql
ALTER TABLE config_institucion ADD COLUMN auth_config_json TEXT;
```

Valor por defecto:

```json
{
  "admin": {
    "metodo": "email",
    "requiere_correo_institucional": true,
    "dominios_permitidos": []
  },
  "rector": {
    "metodo": "email_or_username",
    "largo_minimo_password": 8
  },
  "authority": {
    "metodo": "email_or_username",
    "largo_minimo_password": 6
  },
  "teacher": {
    "metodo": "email_or_username",
    "largo_minimo_password": 6,
    "permitir_documento": true
  },
  "student": {
    "metodo": "code",
    "metodos_alternativos": ["document", "username", "email", "pin"],
    "largo_minimo_pin": 4,
    "permitir_sin_email": true
  },
  "guardian": {
    "metodo": "email",
    "metodos_alternativos": ["document"]
  },
  "general": {
    "session_duracion_normal": 4,
    "session_duracion_recordar": 30,
    "max_intentos_fallidos": 5,
    "bloqueo_minutos": 5,
    "recuperacion_email": true,
    "recuperacion_preguntas": true,
    "2fa_obligatorio": false,
    "2fa_metodo": "none"
  }
}
```

### 15.2 Helper de configuración de auth

```python
def config_get_auth(slug):
    """Retorna la configuración de autenticación de la institución."""
    config = config_get(slug)
    auth_config = {}
    try:
        auth_config = json.loads(config.get('auth_config_json', '{}'))
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fusionar con defaults
    default = {
        'student': {'metodo': 'code', 'permitir_sin_email': True},
        'teacher': {'metodo': 'email_or_username'},
        'rector': {'metodo': 'email_or_username'},
        'authority': {'metodo': 'email_or_username'},
        'admin': {'metodo': 'email'},
        'guardian': {'metodo': 'email'},
        'general': {
            'session_duracion_normal': 4,
            'session_duracion_recordar': 30,
            'max_intentos_fallidos': 5,
            'bloqueo_minutos': 5,
            'recuperacion_email': True,
            '2fa_obligatorio': False
        }
    }
    
    for clave, valor_default in default.items():
        if clave not in auth_config:
            auth_config[clave] = valor_default
        elif isinstance(valor_default, dict):
            for subclave, subvalor in valor_default.items():
                if subclave not in auth_config[clave]:
                    auth_config[clave][subclave] = subvalor
    
    return auth_config
```

### 15.3 UI de configuración de auth (para el rector)

Se agrega una sección en `rector_configuracion.html` (o un template separado) donde el rector puede:

1. **Por rol**: seleccionar el método de autenticación de un menú desplegable
2. **Configuración general**: duración de sesión, intentos máximos, tiempo de bloqueo
3. **Estudiantes**: habilitar/deshabilitar PIN, requerir email, código institucional vs documento
4. **2FA**: opción "Preparar para 2FA" (aún no funcional, solo visible)

---

## Apéndice A: Migración de auth_config

```python
# migración v11
def _migrar_v11(conn, slug=None):
    try:
        conn.execute("ALTER TABLE config_institucion ADD COLUMN auth_config_json TEXT")
    except Exception:
        pass  # ya existe
```

## Apéndice B: Ejemplos de configuración

### Colegio pequeño (200 estudiantes)
```json
{
  "student": { "metodo": "pin", "permitir_sin_email": true },
  "teacher": { "metodo": "username" },
  "guardian": { "metodo": "document" },
  "general": { "session_duracion_normal": 8 }
}
```

### Universidad (5000+ estudiantes)
```json
{
  "student": { "metodo": "code", "metodos_alternativos": ["email"], "permitir_sin_email": false },
  "teacher": { "metodo": "email", "requiere_correo_institucional": true, "dominios_permitidos": ["@universidad.edu.co"] },
  "authority": { "metodo": "email" },
  "general": { "max_intentos_fallidos": 3, "bloqueo_minutos": 15, "2fa_obligatorio": false }
}
```

### Instituto técnico (300 estudiantes, instructores)
```json
{
  "student": { "metodo": "document", "permitir_sin_email": true },
  "teacher": { "metodo": "email_or_username", "permitir_documento": true },
  "guardian": { "metodo": "email" }
}
```

---

*Documento generado el 27 de junio de 2026.*
*Versión 1.0 — Pendiente de aprobación para inicio de implementación.*
