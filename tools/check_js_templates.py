"""Comprobación estática de sintaxis JS en plantillas Jinja2 (sin navegador).

Extrae los bloques <script> sin atributo src, sustituye las expresiones Jinja
por un literal neutro y valida cada bloque con `node --check`. No ejecuta el
código ni modifica archivos del proyecto.
"""

import glob
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_RE = re.compile(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', re.S | re.I)
JINJA_EXPR = re.compile(r'\{\{.*?\}\}', re.S)
JINJA_STMT = re.compile(r'\{%.*?%\}', re.S)
JINJA_COMMENT = re.compile(r'\{#.*?#\}', re.S)


def limpiar(js):
    js = JINJA_COMMENT.sub('', js)
    js = JINJA_EXPR.sub('null', js)
    js = JINJA_STMT.sub('', js)
    return js


def main():
    patron = sys.argv[1] if len(sys.argv) > 1 else 'templates/**/*.html'
    archivos = sorted(glob.glob(os.path.join(ROOT, patron), recursive=True))
    tmp = tempfile.mkdtemp(prefix='lumini_js_')
    errores = []
    revisados = 0
    for path in archivos:
        with open(path, encoding='utf-8') as fh:
            html = fh.read()
        for i, bloque in enumerate(SCRIPT_RE.findall(html)):
            if not bloque.strip():
                continue
            revisados += 1
            destino = os.path.join(tmp, f'blk_{revisados}.js')
            with open(destino, 'w', encoding='utf-8') as fh:
                fh.write(limpiar(bloque))
            r = subprocess.run(['node', '--check', destino],
                               capture_output=True, text=True)
            if r.returncode != 0:
                detalle = (r.stderr or '').strip().splitlines()
                errores.append((os.path.relpath(path, ROOT), i, detalle[:6]))
    print(f'bloques_revisados={revisados} con_error={len(errores)}')
    for path, i, detalle in errores:
        print(f'--- {path} (bloque {i})')
        for linea in detalle:
            print('   ', linea)
    print('ALL_OK' if not errores else 'PROBLEMS')


if __name__ == '__main__':
    main()
