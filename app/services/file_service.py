import os
import uuid
from app.models.schema import conectar
from app.repositories.file_repository import get_archivo as repo_get_archivo, eliminar_archivo as repo_eliminar_archivo, get_max_tamano_archivo

EXTENSIONES_PERMITIDAS = {
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentationml',
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp',
    '.svg': 'image/svg+xml',
    '.txt': 'text/plain',
    '.csv': 'text/csv',
    '.zip': 'application/zip',
}


def get_archivo(conn, fid):
    return repo_get_archivo(conn, fid)


def eliminar_archivo_db(conn, fid):
    repo_eliminar_archivo(conn, fid)


def max_tamano_archivo(slug):
    conn = conectar(slug)
    try:
        return get_max_tamano_archivo(conn, slug)
    finally:
        conn.close()


def guardar_archivo_mensaje(slug, canal_id, f, usuario_tipo, usuario_id, app_root_path):
    nombre_original = f.filename
    ext = os.path.splitext(nombre_original)[1].lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        return None, 'Extensión no permitida'
    tamano = len(f.read())
    f.seek(0)
    max_sz = max_tamano_archivo(slug)
    if tamano > max_sz:
        return None, f'Archivo muy grande (máx {max_sz // 1048576} MB)'
    es_img = ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp')
    if es_img:
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(f.read()))
            img.verify()
            f.seek(0)
        except Exception:
            return None, 'Archivo de imagen inválido o corrupto'
    nombre_archivo = f'{uuid.uuid4().hex}{ext}'
    upload_dir = os.path.join(app_root_path, 'static', 'uploads', slug)
    os.makedirs(upload_dir, exist_ok=True)
    ruta = os.path.join(upload_dir, nombre_archivo)
    f.save(ruta)
    ancho = alto = None
    if es_img:
        try:
            from PIL import Image
            img = Image.open(ruta)
            ancho, alto = img.size
        except Exception:
            pass
    conn = conectar(slug)
    try:
        fid = conn.execute(
            '''INSERT INTO mensajes_archivos
               (canal_id, usuario_tipo, usuario_id, nombre_original, nombre_archivo, tipo_mime, tamano, es_imagen, ancho, alto)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (canal_id, usuario_tipo, usuario_id, nombre_original, nombre_archivo,
             EXTENSIONES_PERMITIDAS[ext], tamano, 1 if es_img else 0, ancho, alto)).lastrowid
        conn.commit()
    finally:
        conn.close()
    return fid, None


def eliminar_archivo_fisico(ruta):
    try:
        os.remove(ruta)
    except Exception:
        pass
