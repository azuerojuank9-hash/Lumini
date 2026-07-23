import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['FLASK_ENV'] = 'development'
os.environ['ENV'] = 'development'
import pytest

TEST_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'colegios_db', 'testcolegio.db')

def ensure_table():
    conn = sqlite3.connect(TEST_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS firmas_digitales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL,
        usuario_tipo TEXT NOT NULL,
        usuario_id INTEGER NOT NULL,
        nombre TEXT NOT NULL,
        documento_tipo TEXT NOT NULL,
        documento_id INTEGER NOT NULL,
        hash_documento TEXT NOT NULL,
        firma_hash TEXT NOT NULL,
        metodo TEXT DEFAULT 'hmac-sha256',
        ip TEXT DEFAULT '',
        user_agent TEXT DEFAULT '',
        creado TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.commit()
    conn.close()

ensure_table()

@pytest.fixture
def conn():
    c = sqlite3.connect(TEST_DB)
    c.row_factory = sqlite3.Row
    yield c
    c.close()

def test_sign_document(conn):
    from services.signatures import sign_document
    sig = sign_document(conn, 'testcolegio', 'rector', 1, 'Rector Test',
                        'boletin', 100, 'contenido_del_documento', 'secret-key')
    assert sig is not None
    assert sig.id is not None
    assert sig.usuario_tipo == 'rector'
    assert sig.documento_tipo == 'boletin'
    assert sig.firma_hash

def test_verify_signature_valid(conn):
    from services.signatures import sign_document, verify_signature
    sig = sign_document(conn, 'testcolegio', 'teacher', 2, 'Prof Test',
                        'acta', 50, 'contenido_acta', 'secret-key')
    assert verify_signature(conn, sig.firma_hash, 'secret-key') is True

def test_verify_signature_invalid(conn):
    from services.signatures import verify_signature
    assert verify_signature(conn, 'hash-inexistente', 'secret-key') is False

def test_verify_signature_wrong_secret(conn):
    from services.signatures import sign_document, verify_signature
    sig = sign_document(conn, 'testcolegio', 'rector', 1, 'Rector Test',
                        'boletin', 200, 'contenido', 'secret-a')
    assert verify_signature(conn, sig.firma_hash, 'secret-b') is False

def test_document_integrity_valid(conn):
    from services.signatures import sign_document, verify_document_integrity
    sign_document(conn, 'testcolegio', 'rector', 1, 'Rector Test',
                  'contrato', 300, 'contenido_original', 'secret-key')
    assert verify_document_integrity(conn, 'contrato', 300, 'contenido_original') is True

def test_document_integrity_tampered(conn):
    from services.signatures import sign_document, verify_document_integrity
    sign_document(conn, 'testcolegio', 'rector', 1, 'Rector Test',
                  'contrato', 301, 'contenido_original', 'secret-key')
    assert verify_document_integrity(conn, 'contrato', 301, 'contenido_modificado') is False

def test_document_integrity_no_sig(conn):
    from services.signatures import verify_document_integrity
    assert verify_document_integrity(conn, 'inexistente', 999, 'nada') is False

def test_get_signatures_for_document(conn):
    from services.signatures import get_signatures_for_document, sign_document
    conn.execute("DELETE FROM firmas_digitales WHERE documento_tipo='oficio' AND documento_id=400")
    conn.commit()
    sign_document(conn, 'testcolegio', 'rector', 1, 'Rector A',
                  'oficio', 400, 'contenido', 'secret-key')
    sign_document(conn, 'testcolegio', 'teacher', 2, 'Prof B',
                  'oficio', 400, 'contenido', 'secret-key')
    sigs = get_signatures_for_document(conn, 'oficio', 400)
    assert len(sigs) == 2
    assert sigs[0]['nombre'] == 'Rector A'
    assert sigs[1]['nombre'] == 'Prof B'

def test_get_signatures_for_document_empty(conn):
    from services.signatures import get_signatures_for_document
    sigs = get_signatures_for_document(conn, 'oficio', 9999)
    assert sigs == []

def test_make_document_hash_changes_with_content(conn):
    from services.signatures import sign_document, verify_document_integrity
    sign_document(conn, 'testcolegio', 'rector', 1, 'Rector',
                  'doc', 500, 'version_a', 'secret-key')
    assert verify_document_integrity(conn, 'doc', 500, 'version_a') is True
    assert verify_document_integrity(conn, 'doc', 500, 'version_b') is False
