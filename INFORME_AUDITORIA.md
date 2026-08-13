# Informe de Auditoría — Lumini (Etapa UX / UI / Funcionalidad / Rendimiento)

Auditoría realizada desde el punto de vista de un usuario no-técnico
(profesor, rector, estudiante, padre). Base verificada: **404 tests PASS, EXIT=0**.

---

## 1. Botones y acciones que NO funcionan (rotos)

### 1.1 "Nueva actividad" no crea nada (profesor)
- **Qué ve el usuario:** completa el formulario "Nueva actividad" y pulsa **Guardar**; no pasa nada (ni actividad nueva, ni mensaje claro; la consola muestra `TypeError`).
- **Causa raíz:** el modal HTML solo tiene los campos `actNombre`, `actTipo`, `actPeso` y los radio de estado (`templates/index.html:2875-2916`), pero la función `guardarActividad()` (`templates/index.html:3478-3499`) lee además `actCompetencia`, `actDescripcion`, `actEntregaDigital`, `actFechaLimite` y `actHoraLimite`, que **no existen en el DOM** → `TypeError: Cannot read properties of null` → el envío nunca ocurre.
- **El backend sí está completo** (`app/routes/teacher.py:388-448` acepta todos esos campos). El problema es solo del front-end.
- **Fix propuesto (FASE 1):** añadir los campos faltantes al modal (competencia, descripción, fecha/hora límite, entrega digital) o hacer la lectura tolerante a `null` y limpiar los campos de forma segura.

### 1.2 No se pueden agregar/inscribir estudiantes (rector)
- **Qué ve el usuario:** en el panel del rector, la sección "Matrículas" permite llenar un formulario de aspirante y pulsar **Registrar**; siempre termina en error ("Nombre y curso requeridos" o similar) y el estudiante nunca aparece.
- **Causa raíz:** `crearMatricula()` (`templates/rector_panel.html:805-813`) envía `{nombre, documento, email, curso_solicitado}`, pero el backend `rector_matriculas_crear` (`app/routes/rector_routes.py:1467-1489`) espera `{nombre, curso, jornada}`. Como `curso` llega vacío, la validación devuelve `400 "Nombre y curso requeridos"` **siempre**.
- **Además,** la página `templates/rector_estudiantes.html` es una lista de **solo lectura** (sin botón "Agregar", sin editar, sin desactivar). El backend ya tiene los endpoints necesarios: `POST /<slug>/matriculas/crear` (crea alumno) y `POST /<slug>/matriculas/<id>/estado` (activa/desactiva con `activo=0/1`).
- **Fix propuesto (FASE 2):** alinear campos del modal con el contrato del backend y/o añadir un botón "Agregar estudiante" en `rector_estudiantes.html` conectado a `POST /matriculas/crear`, más acciones de editar y desactivar.

### 1.3 Guardar nota en celdas de actividad recién creada falla (profesor)
- **Qué ve el usuario:** tras crear una actividad, si intenta digitar una nota en las celdas nuevas, el guardado falla silenciosamente.
- **Causa raíz:** las celdas inyectadas por JS (`templates/index.html:3526` y `4103`) usan `inp.onchange=function(){guardarNota(this);}`, pero la función `guardarNota` **no está definida en ningún archivo** → `ReferenceError`.
- **Nota:** el flujo principal de notas de la grilla sí funciona (usa `cambioNota` → `POST /<slug>/notas/batch`, `templates/index.html:3902-3939`). El bug afecta solo a celdas inyectadas dinámicamente.
- **Fix propuesto (FASE 1):** reemplazar por el mismo mecanismo `cambioNota(this)` que usa la grilla.

### 1.4 Barra de productividad (dashboard profesor) lanza error cada 5 segundos
- **Causa raíz:** `actualizarProdBar()` (`templates/index.html:4762`) accede a `document.getElementById('diProm')` sin comprobación de `null`, dentro de `setInterval(actualizarProdBar, 5000)` (`templates/index.html:4778`). Al no existir el elemento, se lanza `TypeError` en cada ciclo.
- **Fix propuesto (FASE 1):** null-guard (como ya se hizo en P8 para otras funciones).

### 1.5 Dashboard de inteligencia de curso: datos que nadie ve
- **Causa raíz:** `actualizarDashboard()` (`templates/index.html:4117-4139`) consulta `GET /<slug>/curso/analitica` (que sí funciona, `app/routes/teacher.py:1881`) pero escribe en `diProm`, `diMaxMin`, `diAprob`, `diPerd`, `diSinNotas`, `diRiesgoAlto`, `diRiesgoMedio`, `diActCalif`, `diActPend`, **ninguno de los cuales existe en el HTML**. Es código muerto que hace una petición innecesaria por nada visible.
- **Fix propuesto (FASE 1):** eliminar el fetch y la función, o renderizar los elementos; decidir junto a la pestaña "Estadísticas".

---

## 2. Por qué guardar notas es LENTO (causa raíz de rendimiento)

Flujo real al editar una nota en la grilla del profesor:

1. `cambioNota()` acumula el cambio y, tras 800 ms, llama `POST /<slug>/notas/batch` (`templates/index.html:3920-3939`).
2. En el servidor, **por cada nota**, `notas_batch` (`app/routes/teacher.py:654-707`) ejecuta:
   - `SELECT` de la actividad,
   - `periodo_cerrado(slug, periodo)` → **abre su propia conexión SQLite, consulta y la cierra** (`app/infra/audit.py:9-15`),
   - `SELECT` de la nota anterior,
   - `UPDATE`/`INSERT`,
   - `auditar_nota(...)` → **abre OTRA conexión SQLite, hace `INSERT` + `commit` y la cierra** (`app/infra/audit.py:40-59`).
   - Total: **~2 conexiones extra por nota, cada una con su propio `commit` (fsync)**.
3. Después del guardado, el front lanza **una petición `GET /<slug>/recalcular/<aid>` POR cada estudiante afectado** (`templates/index.html:3945`, `actualizarCelda`), cada una abriendo otra conexión y recalculando promedios/nota final.

Con 25 notas en una página (página completa): **~50 conexiones extra** dentro del batch + **25 peticiones HTTP adicionales** de recálculo. Sobre SQLite por archivo en Windows, abrir conexión y hacer commit es costoso; esa es la causa de la lentitud percibida.

**Fix propuesto (FASE 3):**
- Que `periodo_cerrado` y `auditar_nota` reutilicen la conexión ya abierta dentro del batch (o se consulten una sola vez fuera del bucle) y un **único commit**.
- Devolver promedios / nota final / notas pendientes en la **misma respuesta** del batch (ya existe `calcular_stats_estudiante`/`calcular_stats_curso` en `guardar_nota`, `teacher.py:799-801`) y actualizar el DOM con esos datos, eliminando los 25 `GET /recalcular`.
- Medir antes/después con un batch real (ver FASE 3).

---

## 2.1 FASE 3 implementada y medida (Rendimiento guardar notas)

Cambios aplicados (FASE 3, backend + front-end):

- `app/infra/audit.py`: `audit_log()` y `auditar_nota()` aceptan `conn=None`. Si se pasa una conexión la **reutilizan** (el `commit`/`close` queda a cargo del llamador); si no, mantienen el comportamiento anterior (abrir → commit → cerrar). Sin cambios de firma para llamadores existentes.
- `notas_batch` (`app/routes/teacher.py:654-717`): los períodos cerrados se consultan **una sola vez** fuera del bucle (`cerrados`); pasa `conn=conn` a `auditar_nota`; **un único `conn.commit()`** al final del lote. Después del commit calcula `calculos` (promedio y nota final por alumno) con la **misma** conexión y los devuelve en la respuesta JSON.
- `guardar_nota_batch` (`app/routes/teacher.py:948`): misma optimización (períodos cerrados pre-cargados + `conn=conn` en auditoría + un solo commit).
- `guardar_nota` (individual, `app/routes/teacher.py:752`): reutiliza la conexión para `audit_log` y `auditar_nota` antes de un único commit.
- `templates/index.html`: `ejecutarBatchSave()` consume `resp.calculos` y actualiza las celdas de Prom./N.Final directamente desde el servidor; `actualizarCelda(aid, calculo)` usa el valor pre-calculado y solo cae al `GET /recalcular/<aid>` como fallback. **Se eliminan las N peticiones de recálculo por estudiante.**

Resultado medido (`tests/bench_notas.py`, 30 alumnos):

| Flujo | Tiempo |
|-------|--------|
| NUEVO — 1× `POST /notas/batch` (con cálculos) | **22.4 ms** |
| VIEJO — 30× `POST /guardar_nota` + 30× `GET /recalcular` | **1007.4 ms** |
| **Mejora** | **~97.8 % más rápido** |

Suite tras FASE 3: **417 tests PASS, EXIT=0** (404 base + 8 FASE 2 + 5 nuevos de FASE 3 en `tests/test_fase3_rendimiento.py`).

---

## 3.1 FASE 4 y 5/6 implementadas (Estadísticas · limpieza · stubs)

- **Pestaña "Estadísticas" del profesor** (media/mediana/moda/desviación/Q1/Q3/P10/P90): **eliminada de la UI** (`templates/dashboard.html` — botón de pestaña, bloque `tabStats` y funciones `renderStats`). El backend `/dashboard_data` y `_estadisticas_desc` se **conservan intactos** (los tests `test_app.py:1849-1904` los requieren).
- **"Peso %"**: se mantiene el campo en el modal "Nueva actividad" con etiqueta clara **"(informativo)"** y nota al pie: *"No cambia la fórmula de calificación (65% actividades · 25% evaluación · 10% autoevaluación)"* (`templates/index.html`). La fórmula 65/25/10 no se toca.
- **CSS muerto eliminado** (solo reglas sin uso; los archivos se conservan porque los tests verifican su existencia):
  - `layout.css` — `.container-narrow`, `.container-wide`, `.grid-4`.
  - `dashboard.css` — `.dashboard-grid`, `.chart-container`, `.chart-container-sm`, `.chart-legend*`.
  - `sidebar.css` — `.sidebar-submenu*`. (`.sidebar-section-label` se **conserva**: sí se usa en `components/sidebar.html`.)
- **Stubs ocultados**: eliminados los enlaces **Calendario** y **Mensajes** del sidebar del rector (`templates/components/sidebar_rector.html`). Las **rutas se mantienen** (`/rector/calendario`, `/rector/mensajes`) para compatibilidad; los tests `test_expediente.py:69-74` y `functional_audit.py:188-189` siguen pasando.
- **Responsive**: verificado el cimiento responsive en `base.html` (viewport, hamburguesa, overlay, media queries de `sidebar.css` a 768 px).

Suite tras FASE 4/5: **417 tests PASS, EXIT=0**.

---

## 3. Textos técnicos sin explicación (usuario no-técnico)

- **Pestaña "Estadísticas" del profesor** (`templates/dashboard.html:297-301` pestaña; render `475-497`): muestra Media, Mediana, Moda, Desviación estándar, Máximo, Mínimo, **Q1/Q3/P10/P90** sin ninguna explicación. Es jerga estadística que un profesor típico no entiende y que además duplica datos ya visibles (Promedio, N.Final). Backend: `/dashboard_data` (`teacher.py:2711`) → `_estadisticas_desc` (`app/infra/dashboard.py:7-40`).
- **Decisión propuesta (FASE 4):** eliminar la pestaña/visualización (conservando el backend para no romper API existente), o simplificarla a 2-3 métricas con descripción en lenguaje claro.
- Los tooltips de "Prom." y "N.Final" (`templates/index.html:1146-1147`) **ya están bien explicados** → mantener.

---

## 4. "Peso %" es cosmético (confirmado)

- El campo **Peso %** por actividad se guarda pero **nunca se usa** en los cálculos: `_promedio_ponderado` (`app/infra/grades.py:15-31`) combina solo pesos por categoría fija **65% actividades / 25% evaluación / 10% autoevaluación**.
- **Decisión propuesta:** mantener la fórmula 65/25/10 (regla del usuario). Opciones: quitar el campo "Peso %" del modal "Nueva actividad" para no confundir, o dejarlo con una etiqueta clara "Informativo" (no cambia la fórmula).

---

## 5. Páginas / secciones sin implementar (stubs)

- **Calendario** → `app/routes/rector_routes.py:1262` renderiza `templates/rector/calendario.html`, cuyo contenido es "Módulo en construcción" (línea 14). Enlace en sidebar (línea 32).
- **Mensajes** → `app/routes/rector_routes.py:1274` renderiza `templates/rector/mensajes.html`, "Módulo en construcción" (línea 14). Enlace en sidebar (línea 33).
- **Tesorería** → devuelve listas/facturas vacías (`rector_routes.py:1512-1518`, `1521`); la UI está en `rector_panel.html` (modal `tesModal`, líneas ~822-883) con mensajes como "Función de recibo próximamente".
- **Decisión propuesta (FASE 5/6):** ocultar del sidebar los enlaces a módulos "en construcción" (Calendario, Mensajes) o mostrar un estado claro, sin romper rutas existentes (dejar las rutas para compatibilidad).

---

## 6. Listas de solo lectura (sin gestión)

- `rector_estudiantes.html` — solo listado y búsqueda (sin agregar/editar/desactivar).
- `rector_cursos.html` — solo listado de tarjetas (sin crear curso).
- `rector_profesores.html` — verificar cobertura de alta/edición en FASE 2.

---

## 7. Espacios vacíos (estados sin datos)

- Los estados vacíos de `rector_estudiantes.html` y `rector_cursos.html` **ya están bien** (mensaje + acción sugerida).
- Revisar en FASE 1/5: portal padre, tablero del estudiante, listas del profesor sin actividades y grilla sin estudiantes (`templates/index.html:1186-1188` ya tiene un mensaje básico) — unificar el estilo de "estado vacío" con el componente existente.

---

## 8. CSS muerto (limpieza propuesta FASE 4/5)

- `static/css/attendance.css` — sin plantillas que lo usen.
- `layout.css:5-6` — `.container-narrow`, `.container-wide`, `.grid-4` sin uso.
- `dashboard.css:2-9` — `.dashboard-grid`, `.chart-container*` sin uso.
- `sidebar.css:23-25` — `.sidebar-submenu*` sin uso; `.sidebar-section-label` definido sin uso.

---

## 9. Resumen de propuestas por fase

| Fase | Alcance | Cambios principales |
|------|---------|---------------------|
| 0 | Línea base | 404 tests PASS EXIT=0 (~183s) |
| 1 | Navegación / textos / botones rotos | Arreglar "Nueva actividad" (modal), `guardarNota`→`cambioNota`, null-guard `actualizarProdBar`, quitar fetch muerto a `/curso/analitica`, botones Volver, estados vacíos |
| 2 | Sección estudiantes | Alinear/arreglar alta de estudiantes y añadir Agregar/Editar/Desactivar en `rector_estudiantes.html` |
| 3 | Rendimiento guardar notas | **HECHO** — `audit.py` reutiliza conexión; `notas_batch`/`guardar_nota_batch`/`guardar_nota` con un solo commit; batch devuelve `calculos`; front actualiza desde `resp.calculos` sin recálculos por alumno. Medido: 22.4 ms vs 1007.4 ms (~97.8%). Suite 417 PASS EXIT=0 |
| 4 | Estadísticas y limpieza | **HECHO** — pestaña Estadísticas eliminada de la UI (backend conservado); CSS muerto removido (layout/dashboard/sidebar); "Peso %" con etiqueta "(informativo)" + nota de la fórmula 65/25/10 |
| 5/6 | Vistas globales / responsive / tests | **HECHO** — stubs Calendario/Mensajes ocultos del sidebar rector (rutas intactas); responsive verificado; suite completa **417 PASS EXIT=0** |

**Archivos clave afectados:** `templates/index.html`, `templates/dashboard.html`, `templates/rector_panel.html`, `templates/rector_estudiantes.html`, `app/routes/teacher.py`, `app/routes/rector_routes.py`, `app/infra/audit.py`, `app/infra/grades.py`, `static/css/*`.
