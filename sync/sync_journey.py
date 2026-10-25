#!/usr/bin/env python3
"""Customer Journey: Tablero → Mapa de Procesos.

Lee sync/inputs/ajustes/journey.json (el documento `ajustes/journey` de la base del Tablero, bajado con
ArtifactData → get, collection "ajustes", doc_id "journey", out_dir "sync/inputs") y, si su contenido
(etapas, escenarios, ganchos) difiere del que lleva embebido index.html en <script id="cjData">, lo
reemplaza y sube DATA_VERSION (así los navegadores con copia guardada reciben el Journey nuevo).

Uso:  python3 sync/sync_journey.py            → imprime "journey: ACTUALIZADO <fecha>" o "journey: SIN CAMBIOS"
Solo toca el bloque cjData y la constante DATA_VERSION de index.html; nada más.
"""
import json, re, sys, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, 'index.html')
SRC = os.path.join(ROOT, 'sync', 'inputs', 'ajustes', 'journey.json')
KEYS = ('etapas', 'escenarios', 'ganchos')

def canon(d):
    return json.dumps({k: d.get(k, []) for k in KEYS}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def main():
    if not os.path.exists(SRC):
        print('journey: SIN ENTRADA (falta sync/inputs/ajustes/journey.json)'); return 2
    nuevo = json.load(open(SRC, encoding='utf-8'))
    if not isinstance(nuevo, dict) or not nuevo.get('etapas'):
        print('journey: ENTRADA INVÁLIDA (sin etapas)'); return 2
    html = open(IDX, encoding='utf-8').read()
    m = re.search(r'(<script id="cjData" type="application/json">)(.*?)(</script>)', html, re.S)
    if not m:
        print('journey: NO SE ENCONTRÓ cjData en index.html'); return 2
    try:
        actual = json.loads(m.group(2).replace('<\\/', '</') or '{}')
    except Exception:
        actual = {}
    if canon(actual) == canon(nuevo):
        print('journey: SIN CAMBIOS'); return 0
    js = json.dumps({k: nuevo.get(k, []) for k in KEYS}, ensure_ascii=False).replace('</', '<\\/')
    html = html[:m.start(2)] + js + html[m.end(2):]
    ver = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + '.000Z'
    html, n = re.subn(r'const DATA_VERSION = "[^"]+";', 'const DATA_VERSION = "%s";' % ver, html, count=1)
    if n != 1:
        print('journey: NO SE PUDO SUBIR DATA_VERSION'); return 2
    open(IDX, 'w', encoding='utf-8').write(html)
    print('journey: ACTUALIZADO', ver, '· etapas', len(nuevo.get('etapas', [])), '· escenarios', len(nuevo.get('escenarios', [])), '· ganchos', len(nuevo.get('ganchos', [])))
    return 0

if __name__ == '__main__':
    sys.exit(main())
