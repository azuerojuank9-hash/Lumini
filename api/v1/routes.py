from flask import g, jsonify, request

from .auth import bp, token_required


@bp.route('/students', methods=['GET'])
@token_required
def api_students():
    from flask_app import conectar
    slug = g.api_slug
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    curso = request.args.get('curso')
    activo = request.args.get('activo')

    conn = conectar(slug)
    if not conn:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    try:
        where = []
        params = []
        if curso:
            where.append('curso=?')
            params.append(curso)
        if activo is not None:
            where.append('activo=?')
            params.append(1 if activo in ('1', 'true') else 0)

        where_sql = ' AND '.join(where) if where else '1'
        total = conn.execute(f'SELECT COUNT(*) FROM alumnos WHERE {where_sql}', params).fetchone()[0]

        offset = (page - 1) * per_page
        rows = conn.execute(
            f'SELECT id, nombre, curso, jornada, num_curso, activo, email_acudiente '
            f'FROM alumnos WHERE {where_sql} ORDER BY nombre LIMIT ? OFFSET ?',
            params + [per_page, offset]
        ).fetchall()

        return jsonify({
            'data': [dict(r) for r in rows],
            'page': page,
            'per_page': per_page,
            'total': total,
        })
    finally:
        conn.close()


@bp.route('/students/<int:student_id>', methods=['GET'])
@token_required
def api_student_detail(student_id):
    from flask_app import conectar
    slug = g.api_slug
    conn = conectar(slug)
    if not conn:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    try:
        row = conn.execute(
            'SELECT id, nombre, curso, jornada, num_curso, activo, email_acudiente '
            'FROM alumnos WHERE id=?', (student_id,)
        ).fetchone()
        if not row:
            return jsonify({'error': 'Estudiante no encontrado', 'code': 'NOT_FOUND'}), 404

        grades = conn.execute('''
            SELECT a.nombre as actividad, n.val, a.materia, a.periodo
            FROM notas n JOIN actividades a ON a.id=n.actividad_id
            WHERE n.aid=? ORDER BY a.materia, a.periodo
        ''', (student_id,)).fetchall()

        attendance = conn.execute('''
            SELECT fecha, estado, observacion FROM asistencia WHERE aid=?
            ORDER BY fecha DESC LIMIT 60
        ''', (student_id,)).fetchall()

        result = dict(row)
        result['notas'] = [dict(r) for r in grades]
        result['asistencia'] = [dict(r) for r in attendance]
        return jsonify(result)
    finally:
        conn.close()


@bp.route('/courses', methods=['GET'])
@token_required
def api_courses():
    from flask_app import conectar
    slug = g.api_slug
    conn = conectar(slug)
    if not conn:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    try:
        rows = conn.execute(
            'SELECT DISTINCT curso, jornada FROM alumnos WHERE activo=1 ORDER BY curso'
        ).fetchall()
        return jsonify({'data': [{'curso': r['curso'], 'jornada': r['jornada']} for r in rows]})
    finally:
        conn.close()


@bp.route('/teachers', methods=['GET'])
@token_required
def api_teachers():
    from flask_app import conectar
    slug = g.api_slug
    conn = conectar(slug)
    if not conn:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    try:
        rows = conn.execute(
            'SELECT id, nombre, email, activo FROM profesores ORDER BY nombre'
        ).fetchall()
        return jsonify({'data': [dict(r) for r in rows]})
    finally:
        conn.close()


@bp.route('/attendance', methods=['GET'])
@token_required
def api_attendance():
    from flask_app import conectar
    slug = g.api_slug
    curso = request.args.get('curso', '')
    fecha = request.args.get('fecha', '')
    if not curso or not fecha:
        return jsonify({'error': 'curso y fecha requeridos', 'code': 'MISSING_FIELDS'}), 400

    conn = conectar(slug)
    if not conn:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    try:
        rows = conn.execute('''
            SELECT a.nombre, a.id, COALESCE(asst.estado,'') as estado,
                   COALESCE(asst.observacion,'') as observacion
            FROM alumnos a
            LEFT JOIN asistencia asst ON asst.aid=a.id AND asst.fecha=?
            WHERE a.curso=? AND a.activo=1
            ORDER BY a.num_curso
        ''', (fecha, curso)).fetchall()
        return jsonify({'data': [dict(r) for r in rows], 'fecha': fecha, 'curso': curso})
    finally:
        conn.close()


@bp.route('/grades', methods=['GET'])
@token_required
def api_grades():
    from flask_app import conectar
    slug = g.api_slug
    curso = request.args.get('curso', '')
    materia = request.args.get('materia', '')
    periodo = request.args.get('periodo', 1, type=int)
    if not curso or not materia:
        return jsonify({'error': 'curso y materia requeridos', 'code': 'MISSING_FIELDS'}), 400

    conn = conectar(slug)
    if not conn:
        return jsonify({'error': 'Not found', 'code': 'NOT_FOUND'}), 404
    try:
        rows = conn.execute('''
            SELECT a.id, a.nombre, n.val, ac.nombre as actividad, ac.id as actividad_id
            FROM alumnos a
            JOIN actividades ac ON ac.curso=? AND ac.materia=? AND ac.periodo=?
            LEFT JOIN notas n ON n.aid=a.id AND n.actividad_id=ac.id
            WHERE a.curso=? AND a.activo=1
            ORDER BY a.num_curso, ac.orden
        ''', (curso, materia, periodo, curso)).fetchall()

        grouped = {}
        for r in rows:
            key = r['id']
            if key not in grouped:
                grouped[key] = {'id': key, 'nombre': r['nombre'], 'notas': []}
            grouped[key]['notas'].append({
                'actividad': r['actividad'],
                'actividad_id': r['actividad_id'],
                'val': r['val'],
            })
        return jsonify({'data': list(grouped.values())})
    finally:
        conn.close()
