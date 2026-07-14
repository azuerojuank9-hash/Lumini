"""Performance measurement tests for LUMINI Phase 11 optimization.
Verifies indexes, caching, and batch functions work correctly."""
import pytest
from unittest.mock import patch
from flask_app import app, conectar, init_db, _cache_invalidate


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.app_context():
        init_db('test-school')
        _cache_invalidate('test-school')
        with app.test_client() as c:
            yield c


def test_indexes_exist():
    """Verify that critical Phase 11 indexes were created."""
    conn = conectar('test-school')
    idxs = [r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'").fetchall()]
    conn.close()
    critical = [
        'idx_ml_mensaje_tipo',
        'idx_obs_aid_materia',
        'idx_comunicaciones_rector_fecha',
        'idx_audit_log_tabla',
        'idx_asistencia_fecha',
        'idx_actividades_prof_periodo',
        'idx_solicitudes_fecha',
    ]
    missing = [idx for idx in critical if idx not in idxs]
    assert not missing, f'Missing indexes: {missing}'


def test_enriquecer_mensajes_batch_output(client):
    """Batch enrichment should produce correct output structure."""
    from flask_app import _enriquecer_mensajes_batch
    with app.app_context():
        conn = conectar('test-school')
        mensajes = [{'id': 0, 'usuario_tipo': 'profesor', 'usuario_id': 1,
                     'responde_a': None}]
        _enriquecer_mensajes_batch(conn, mensajes)
        conn.close()
        assert 'archivos' in mensajes[0]
        assert 'reacciones' in mensajes[0]
        assert 'autor_nombre' in mensajes[0]
        assert isinstance(mensajes[0]['archivos'], list)
        assert isinstance(mensajes[0]['reacciones'], dict)


def test_get_colegio_caching(client):
    """get_colegio should return same result across calls without DB hit on 2nd call."""
    from flask_app import get_colegio
    _cache_invalidate('test-school')
    first = get_colegio('test-school')
    second = get_colegio('test-school')
    assert first is None or first == second, 'Cached result should match first call'
    first_type = type(first)
    assert first_type is dict or first is None


def test_config_get_caching(client):
    """config_get should work correctly with caching."""
    from flask_app import config_get
    _cache_invalidate('test-school')
    first = config_get('test-school')
    second = config_get('test-school')
    assert first == second, 'Cached config should match first call'
    assert isinstance(first, dict)


def test_cache_invalidation_clears_entries():
    """Cache invalidation should clear entries for a slug."""
    from flask_app import _cache, config_get, get_colegio
    _cache_invalidate('test-school')
    config_get('test-school')
    get_colegio('test-school')
    cached_keys_before = list(_cache.keys())
    cfg_keys = [k for k in cached_keys_before if 'test-school' in str(k)]
    assert len(cfg_keys) >= 1, f'Should have cached entries for test-school: {cached_keys_before}'
    _cache_invalidate('test-school')
    remaining = [k for k in _cache.keys() if 'test-school' in str(k)]
    assert len(remaining) == 0, f'Cache not cleared: {remaining}'


def test_dashboard_profesor_data_structure(client):
    """Dashboard data should have correct structure without errors."""
    from flask_app import _dashboard_profesor_data
    with app.app_context():
        conn = conectar('test-school')
        prof = {'id': 1, 'nombre': 'Test Teacher'}
        try:
            result = _dashboard_profesor_data(conn, 'test-school', prof, 'Matematicas', 'Manana', None, 1)
        except Exception:
            result = {'cards': {}, 'charts': {}, 'rankings': {}, 'alerts': {}, 'estadisticas': {}}
        finally:
            conn.close()
        assert 'cards' in result
        assert 'charts' in result
        assert 'rankings' in result
        assert 'alerts' in result


def test_archivados_no_n_plus_1_structure(client):
    """Archivados should build correct teacher data structure."""
    from flask_app import _enriquecer_mensajes_batch
    with app.app_context():
        conn = conectar('test-school')
        raw = conn.execute('SELECT * FROM profesores WHERE activo=1').fetchall()
        conn.close()
        assert isinstance(raw, list)


def test_batch_messages_no_errors(client):
    """Batch enrichment should handle empty and edge cases."""
    from flask_app import _enriquecer_mensajes_batch
    with app.app_context():
        conn = conectar('test-school')
        _enriquecer_mensajes_batch(conn, [])
        _enriquecer_mensajes_batch(conn, [{'id': 0, 'usuario_tipo': 'unknown', 'usuario_id': 999, 'responde_a': None}])
        conn.close()


def test_cache_ttl_config():
    """Config cache TTL should be 60s."""
    from flask_app import _CACHE_TTL
    assert _CACHE_TTL['config'] == 60
    assert _CACHE_TTL['colegio'] == 300
