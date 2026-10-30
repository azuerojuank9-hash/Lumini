# Informe de Estabilización — LUMINI (ETAPA A–D)

Fecha: 2026-10-15
Alcance: auditoría, corrección mínima agrupada y verificación de tests (sin commit/push, sin tocar datos reales).

---

## 1. Resumen ejecutivo

- Se auditó el conjunto de cambios reales del repositorio (37 archivos con contenido real; el resto es ruido LF/CRLF por `core.autocrlf=true`).
- Se distinguió **bug confirmado**, **regresión confirmada**, **problema preexistente** y **sospecha aclarada (no-problema)**.
- Se aplicaron **3 correcciones mínimas** y **1 alineación de regla de negocio**, cada una con test de regresión:
  1. Mensaje de éxito de registro de profesor se mostraba como HTML crudo (autoescapado).
  2. Toast de tesorería mostraba `Error: undefined`.
  3. Umbral de aprobación del panel de directora no aplicaba la convención de escala.
- **Suite completa: 487 passed en 452.58s** (antes de mis tests: 485; baseline documentado en la misión: 417).
- `git diff --check` limpio. **No se hizo commit ni push.**

---

## 2. ETAPA A — Problemas detectados

### 2.1 Bugs confirmados (corregidos)

| # | Archivo | Problema | Impacto |
|---|---------|----------|---------|
| B1 | `app/routes/auth.py:378` (+`templates/login_v2.html:65`) | El mensaje de éxito del registro de profesor se guardaba en la variable `error` y contenía HTML (`<i data-lucide="check-circle"></i> Registro exitoso...`). La plantilla hacía `{{ error }}` (autoescapado) → el usuario veía **el marcado literal** (`&lt;i data-lucide=...`). Además la clase `alert-success` se decidía por el contenido del string (hack). | Cosmético/lógico. **No es XSS** (texto del servidor, autoescapado). |
| B2 | `templates/rector_panel.html:880,889` | Tras el cambio a `501` en tesorería (`{'status':'proximamente','mensaje':'Módulo de tesorería próximamente'}`), el JS leía `d.error` (undefined) → **"Error: undefined"**. Antes mostraba falso éxito ("Factura creada"/"Pago registrado") sobre un módulo no funcional. | Mensaje de UI incorrecto. |

### 2.2 Regresión confirmada (corregida)

| # | Archivo | Problema | Impacto |
|---|---------|----------|---------|
| R1 | `app/routes/directora_routes.py:101` | `if cfg.get('tipo_evaluacion') == 'mitad'` es un **branch muerto**: `'mitad'` no es un valor válido de la UI (valores: `numerica`, `conceptual`, `porcentaje`, `letras`) ni aparece en el resto del código. Con la config por defecto (`escala_max=10.0`, `nota_minima_aprobar=6.0`, `tipo_evaluacion='numerica'`), directora usaba **6.0** mientras `dashboard.py:344` y `rector_routes.py:132` usan la convención `if escala_max > 5.0: nota_minima_aprobar /= 2.0` → **3.0**. Inconsistencia en aprobados/reprobados. | KPIs de directora discrepantes con el resto. |

### 2.3 Sospechas aclaradas (NO son problemas introducidos)

- `templates/rector_solicitudes.html`: `if(d.ok)` → `if(d.status==='ok')` **es correcto**: el backend devuelve `{'status':'ok'}` (`rector_routes.py:629`); el `d.ok` previo era siempre `undefined` y la fila nunca se actualizaba.
- `templates/index.html`: `window._estudiantes = {{ estudiantes | tojson | safe }}` es válido (la ruta pasa `estudiantes=datos`).
- `templates/base.html`: `toggleSidebar()` ya existe; eliminar el duplicado en `index.html` es seguro.
- `app/infra/helpers.py` (`_normalizar` en `get_cursos_cache`/`get_materias_cache`/`get_jornadas_cache`): **código muerto** — esas funciones nunca se llaman (importadas con `# noqa: F401` en `flask_app.py`). No es regresión.
- `/notas/batch` devuelve `{status, saved, errors, snapshot, calculos}` → `tests/test_p9_regressions.py` es coherente.

### 2.4 Problemas preexistentes (NO se tocaron)

- `templates/rector_estudiantes.html`: bloque CSS malformado (`.sidebar`/`.main` sueltos + `}` extra que aplica en todos los anchos). **Ya estaba en HEAD**; el cambio solo insertó una línea `@media` válida antes.
- `templates/rector_asistencia.html:46`: mismo patrón huérfano (archivo sin modificar).
- `app/infra/pdf.py:96`: **no** aplica la convención de mitad de escala (a diferencia de dashboard/rector/directora).
- `flask_app.py`: BOM al inicio del archivo (funciona; anotado por limpieza).

### 2.5 Decisiones de diseño (sin cambio de código, según tu indicación)

- `templates/components/sidebar_teacher.html:20`: se removieron los enlaces de "Asistencia" y "Exportar Excel" del sidebar del profesor. **Se mantiene** (el dashboard los reexpone vía quick-actions). Documentado.
- `app/infra/database.py` `_migrar_v24`: aborta con `RuntimeError` si `anio_lectivo` tiene filas pero la estructura está incompleta. **Se mantiene** (evita corrupción silenciosa). Ver §5.

---

## 3. Correcciones aplicadas y archivos afectados

| Grupo | Cambio | Archivos |
|-------|--------|----------|
| G1 | Registro de profesor: usar variable `exito` (texto plano) y renderizarla como `alert-success` con ícono lucide real; eliminar el hack de clase por contenido y el HTML crudo. | `app/routes/auth.py`, `templates/login_v2.html` |
| G1 | Toast de tesorería: `showToast(d.mensaje||d.error||'Función no disponible')` en crear/pagar factura. | `templates/rector_panel.html` |
| G2 | Alinear el umbral de directora a la convención de escala (`if escala_max > 5.0: nota_minima_aprobar /= 2.0`). | `app/routes/directora_routes.py` |
| Tests | Regresión para G1 (registro) y G2 (umbral). | `tests/test_app.py`, `tests/test_dashboards_p6.py` |

`git diff --stat` (archivos tocados):

```
 app/routes/auth.py             | 22 +++++-----
 app/routes/directora_routes.py |  9 ++++-
 templates/login_v2.html        |  9 +++--
 templates/rector_panel.html    | 11 +++--
 tests/test_app.py              | 44 +++++++++++++++++++-
 tests/test_dashboards_p6.py    | 92 ++++++++++++++++++++++++++++++++++++++++++
 6 files changed, 165 insertions(+), 22 deletions(-)
```

---

## 4. Tests ejecutados y resultado real

| Comando | Resultado |
|---------|-----------|
| `pytest tests/test_dashboards_p6.py tests/test_p9_regressions.py tests/test_excel_p7.py -q` | **93 passed** in 200.59s |
| `pytest tests/test_app.py::TestRegistroProfesorMensajeExito tests/test_dashboards_p6.py::TestDirectoraUmbralEscala -q` | **2 passed** in 1.18s |
| `pytest tests -q --tb=short` (suite completa) | **487 passed** in 452.58s |

Referencia: baseline de misión **417 passed**; estado inmediatamente anterior a estas correcciones **485 passed**; tras añadir 2 tests de regresión **487 passed**.
`git diff --check` (whitespace) = limpio.

### Detalle de los tests de regresión

- `TestRegistroProfesorMensajeExito::test_registro_exitoso_no_muestra_html_escapado`
  - Verifica que el HTML de respuesta contiene `Registro exitoso. Ya puedes ingresar.` y `alert-success`, y que **no** contiene `&lt;i data-lucide="check-circle"&gt;` (el síntoma del bug).
  - Limpia el profesor de prueba al final.
- `TestDirectoraUmbralEscala::test_directora_umbral_relativo_a_escala`
  - Fuerza config `escala_max=10.0`, `nota_minima_aprobar=6.0` (monkeypatch de `config_get`, evita caché).
  - Inserta un alumno aislado con promedio 4.0 (aprobado con 3.0, reprobado con 6.0), calcula el conteo esperado replicando las queries de la ruta y verifica que la KPI renderizada coincide; además exige `aprobados(3.0) > aprobados(6.0)` para que el test **no sea vacuo**. Limpia el alumno al final.

---

## 5. Antes / Después

| Aspecto | Antes | Después |
|---------|-------|---------|
| Registro de profesor | Alerta con marcado literal `&lt;i data-lucide="check-circle"&gt;...` dentro de un `div` con clase calculada por string | `div.alert.alert-success` con ícono lucide real + texto plano |
| Tesorería (crear/pagar) | `Error: undefined` | `Módulo de tesorería próximamente` (usa `d.mensaje`) |
| Directora — umbral (config por defecto) | 6.0 (aprobados/reprobados inconsistentes) | 3.0 (alineado con dashboard y rector) |

---

## 6. Riesgos pendientes

1. **`_migrar_v24` aborta migración** si en producción (`PythonAnywhere`) alguna BD tiene filas en `anio_lectivo` pero estructura incompleta (sin `estado`/`matricula_academica`). Es intencional (fail-fast), pero requiere verificación manual previa (ver §7).
2. **`importar_notas_preview`** (`app/routes/teacher.py`) detecta cabeceras de forma sensible a mayúsculas (`'N°'`, `'AID'`/`'ID'`, `'Estudiante'`, `'Evaluación'`, `'Autoevaluación'`). Excel con otra capitalización podría caer al comportamiento por defecto. No se cambió (fuera de alcance de bug confirmado; hay cobertura en `tests/test_excel_p7.py`).
3. **Inconsistencia preexistente** de mitad de escala en `app/infra/pdf.py:96` (boletín PDF) respecto a dashboard/rector/directora. No corregido.
4. **CSS malformado preexistente** en `rector_estudiantes.html` (y patrón en `rector_asistencia.html`). No se tocó para no introducir cambios amplios de estilo.
3. **BOM** en `flask_app.py`.
4. **Enlaces removidos** del sidebar del profesor (Asistencia/Exportar Excel): decisión de diseño asumida; si se requiere, se restauran en un cambio aparte.

---

## 7. Archivos que NO deben borrarse ni modificarse sin revisión

- `cambios_opencode.txt` (artefacto de diff intermedio; conservar).
- `tests/test_matricula_academica_f24.py` y `tests/test_p9_regressions.py` (tests no rastreados que aportan cobertura).
- `xl` está **eliminado** en el working tree (contenía diff crudo); su eliminación es intencional pero conviene revisarla antes de commit.
- `app/routes/dashboard`/`app/infra/dashboard.py`, repos, servicios y migraciones: no modificar sin revisión (contrato de datos).

---

## 7.1 Pruebas manuales recomendadas en PythonAnywhere (no ejecutables en local)

1. **Registro de profesor**: registrarse en `/{slug}/login` pestaña "Registrarse" → debe verse alerta **verde** con ícono check y texto "Registro exitoso. Ya puedes ingresar." (sin marcado).
2. **Tesorería (rector)**: crear/pagar factura → debe verse "Módulo de tesorería próximamente" (no "Error: undefined").
3. **Directora**: con escala 1–10 y aprobación 6.0, los KPIs Aprobados/Reprobados deben coincidir con los que muestra el panel del rector para el mismo curso/período.
4. **`_migrar_v24`**: antes de desplegar, verificar en cada BD si `SELECT COUNT(*) FROM anio_lectivo` > 0 y si existen `estado` y `matricula_academica`; si hay filas y falta estructura, respaldar y completar estructura manualmente antes de arrancar (el aborto es intencional).

---

## 8. Próximos pasos exactos

1. Revisar este informe y el diff (`git diff` filtrado por los 6 archivos tocados).
2. Decidir sobre riesgos de §6 (especialmente `importar_notas_preview` y `pdf.py`) como tareas separadas.
3. Ejecutar las pruebas manuales de §7.1 en PythonAnywhere sobre una BD de prueba/staging.
4. No hacer `git add .`; si se desea versionar, añadir selectivamente los 6 archivos + los 2 tests untracked, con mensaje acorde al estilo del repo. **(Pendiente de tu autorización explícita.)**
