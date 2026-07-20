import os, threading, shutil
from datetime import timedelta, datetime as _dt


def hacer_backup(MASTER_DB, DB_FOLDER, logger=None):
    try:
        hoy = _dt.now().strftime('%Y-%m-%d')
        backup_dir = os.path.join(os.path.dirname(MASTER_DB), '..', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(MASTER_DB, os.path.join(backup_dir, f'master_{hoy}.db'))
        for f in os.listdir(DB_FOLDER):
            if f.endswith('.db'):
                shutil.copy2(os.path.join(DB_FOLDER, f),
                             os.path.join(backup_dir, f'{f[:-3]}_{hoy}.db'))
        if logger:
            logger.info(f'Backup automático completado: {hoy}')
    except Exception as e:
        if logger:
            logger.error(f'Error en backup: {e}')


def programar_backup(MASTER_DB, DB_FOLDER, logger=None):
    hacer_backup(MASTER_DB, DB_FOLDER, logger)
    t = threading.Timer(86400, programar_backup, args=(MASTER_DB, DB_FOLDER, logger))
    t.daemon = True
    t.start()
