"""
Digital Signature Service.

Handles creation, verification, and storage of digital signatures
for documents: report cards, certificates, attendance sheets, etc.

Stores signature metadata and hash-based verification.
"""

import hashlib
import json
import hmac
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

SIGNATURE_TYPES = {
    'rector': 'Rector',
    'teacher': 'Docente',
    'authority': 'Coordinador',
    'guardian': 'Padre de Familia',
    'student': 'Estudiante',
}


@dataclass
class DigitalSignature:
    id: Optional[int]
    usuario_tipo: str
    usuario_id: int
    nombre: str
    documento_tipo: str
    documento_id: int
    hash_documento: str
    firma_hash: str
    metodo: str
    ip: str
    user_agent: str
    creado: str


def _make_document_hash(documento_tipo: str, documento_id: int, contenido: str) -> str:
    """Create a SHA-256 hash of the document content for integrity verification."""
    raw = f'{documento_tipo}:{documento_id}:{contenido}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _make_signature_hash(usuario_tipo: str, usuario_id: int, doc_hash: str, secret: str, timestamp: Optional[str] = None) -> str:
    """Create an HMAC-SHA256 signature for authenticity."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    raw = f'{usuario_tipo}:{usuario_id}:{doc_hash}:{ts}'
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()


def sign_document(
    conn,
    slug: str,
    usuario_tipo: str,
    usuario_id: int,
    nombre: str,
    documento_tipo: str,
    documento_id: int,
    contenido: str,
    secret: str,
    ip: str = '',
    user_agent: str = '',
) -> DigitalSignature:
    """
    Sign a document. Creates hash of content, then HMAC signature.

    Args:
        conn: DB connection
        slug: School slug
        usuario_tipo: Role type (rector, teacher, etc.)
        usuario_id: User ID
        nombre: Display name
        documento_tipo: Document type (boletin, certificado, etc.)
        documento_id: Document record ID
        contenido: Document content string to hash
        secret: HMAC secret key
        ip: Signer IP address
        user_agent: Signer user agent

    Returns:
        DigitalSignature record
    """
    doc_hash = _make_document_hash(documento_tipo, documento_id, contenido)
    timestamp = datetime.now(timezone.utc).isoformat()
    firma_hash = _make_signature_hash(usuario_tipo, usuario_id, doc_hash, secret, timestamp=timestamp)

    conn.execute(
        '''INSERT INTO firmas_digitales
           (slug, usuario_tipo, usuario_id, nombre, documento_tipo, documento_id,
            hash_documento, firma_hash, metodo, ip, user_agent, creado)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (slug, usuario_tipo, usuario_id, nombre, documento_tipo, documento_id,
         doc_hash, firma_hash, 'hmac-sha256', ip, user_agent, timestamp)
    )
    conn.commit()

    sig_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    return DigitalSignature(
        id=sig_id, usuario_tipo=usuario_tipo, usuario_id=usuario_id,
        nombre=nombre, documento_tipo=documento_tipo, documento_id=documento_id,
        hash_documento=doc_hash, firma_hash=firma_hash, metodo='hmac-sha256',
        ip=ip, user_agent=user_agent, creado=timestamp,
    )


def verify_signature(conn, firma_hash: str, secret: str) -> bool:
    """
    Verify that a signature hash is authentic (was created by our system).

    Args:
        conn: DB connection
        firma_hash: The HMAC signature hash
        secret: HMAC secret key

    Returns:
        True if valid, False otherwise
    """
    row = conn.execute(
        'SELECT * FROM firmas_digitales WHERE firma_hash=?', (firma_hash,)
    ).fetchone()
    if not row:
        return False

    expected_hash = _make_signature_hash(
        row['usuario_tipo'], row['usuario_id'],
        row['hash_documento'], secret, timestamp=row['creado'],
    )
    return hmac.compare_digest(row['firma_hash'], expected_hash)


def verify_document_integrity(conn, documento_tipo: str, documento_id: int, contenido: str) -> bool:
    """
    Verify a document hasn't been tampered with since signing.

    Args:
        conn: DB connection
        documento_tipo: Document type
        documento_id: Document record ID
        contenido: Current document content

    Returns:
        True if document integrity is preserved, False otherwise
    """
    sig = conn.execute(
        'SELECT hash_documento FROM firmas_digitales '
        'WHERE documento_tipo=? AND documento_id=? ORDER BY id DESC LIMIT 1',
        (documento_tipo, documento_id)
    ).fetchone()
    if not sig:
        return False
    current_hash = _make_document_hash(documento_tipo, documento_id, contenido)
    return sig['hash_documento'] == current_hash


def get_signatures_for_document(conn, documento_tipo: str, documento_id: int) -> list:
    """Get all signatures for a document."""
    rows = conn.execute(
        'SELECT * FROM firmas_digitales WHERE documento_tipo=? AND documento_id=? ORDER BY id',
        (documento_tipo, documento_id)
    ).fetchall()
    return [dict(r) for r in rows]
