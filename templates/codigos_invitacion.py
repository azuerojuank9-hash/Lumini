"""
══════════════════════════════════════════════════════════════
  LUMINI — Lógica de códigos de invitación (backend)
  Pega estos fragmentos en tu archivo principal de Flask
══════════════════════════════════════════════════════════════
"""

import random
import string


# ── 1. GENERADOR DE CÓDIGO ─────────────────────────────────
def generar_codigo_registro():
    """Genera un código tipo  LUM-AB3X7K  (único por colegio)."""
    chars = string.ascii_uppercase + string.digits
    sufijo = ''.join(random.choices(chars, k=6))
    return f"LUM-{sufijo}"


# ── 2. CREAR COLEGIO ───────────────────────────────────────
# Dentro de tu bloque  accion == 'crear_colegio':
#
#   codigo = generar_codigo_registro()
#
#   # SQLite / PostgreSQL — agrega la columna al INSERT:
#   db.execute("""
#       INSERT INTO colegios
#           (nombre, slug, num_periodos, vencimiento, logo, activo, creado, codigo_registro)
#       VALUES (?, ?, ?, ?, ?, 1, DATE('now'), ?)
#   """, (nombre, slug, num_periodos, vencimiento, logo_filename, codigo))
#   db.commit()


# ── 3. REGENERAR CÓDIGO (acción desde el admin) ────────────
# @app.route('/admin', methods=['POST'])
# def admin_panel():
#     accion = request.form.get('accion')
#     ...
#     elif accion == 'regenerar_codigo':
#         slug = request.form.get('slug')
#         nuevo = generar_codigo_registro()
#         db.execute(
#             "UPDATE colegios SET codigo_registro = ? WHERE slug = ?",
#             (nuevo, slug)
#         )
#         db.commit()
#         return redirect(url_for('admin_panel', exito=f'Código regenerado: {nuevo}'))


# ── 4. MIGRACIÓN (si el colegio ya existe sin código) ──────
# Ejecuta esto UNA sola vez para rellenar registros viejos:
#
#   colegios_sin_codigo = db.execute(
#       "SELECT slug FROM colegios WHERE codigo_registro IS NULL OR codigo_registro = ''"
#   ).fetchall()
#   for c in colegios_sin_codigo:
#       db.execute(
#           "UPDATE colegios SET codigo_registro = ? WHERE slug = ?",
#           (generar_codigo_registro(), c['slug'])
#       )
#   db.commit()


# ── 5. VALIDAR AL REGISTRARSE (profesor) ──────────────────
# Dentro de  accion == 'profesor_registro':
#
#   codigo_enviado  = request.form.get('codigo_registro', '').strip().upper()
#   colegio = db.execute(
#       "SELECT * FROM colegios WHERE slug = ? AND activo = 1", (slug,)
#   ).fetchone()
#
#   if not colegio:
#       return render_template('login.html', error='Colegio no encontrado.', ...)
#
#   if codigo_enviado != (colegio['codigo_registro'] or '').upper():
#       return render_template('login.html',
#           error='⚠️ Código de invitación incorrecto. Solicítalo al administrador.',
#           ...)
#
#   # ... resto del registro normal


# ── 6. VALIDAR AL REGISTRARSE (directora) ─────────────────
# Dentro de la ruta  /{{ slug }}/directora/registrar_directo:
#
#   codigo_enviado = request.form.get('codigo_registro_dir', '').strip().upper()
#   colegio = db.execute(
#       "SELECT * FROM colegios WHERE slug = ? AND activo = 1", (slug,)
#   ).fetchone()
#
#   if codigo_enviado != (colegio['codigo_registro'] or '').upper():
#       return render_template('login.html',
#           error='⚠️ Código de invitación incorrecto.',
#           ...)
#
#   # ... resto del registro de directora


# ── 7. MIGRACIÓN SQL (si usas SQLite) ─────────────────────
# Si la columna aún no existe en tu tabla, ejecuta:
#
#   ALTER TABLE colegios ADD COLUMN codigo_registro TEXT DEFAULT '';
