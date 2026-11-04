#!/usr/bin/env python3
"""db_extract.py <salida_dir> [coleccion ...]

Reconstruye en archivos los documentos de la base del Tablero que la tarea programada leyó con
ArtifactData (get/list SIN out_dir). Desde nov-2026 ArtifactData ya no guarda en archivo los documentos
escritos por otras personas, así que la tarea los lee en la conversación y este script los toma del
registro de la sesión (~/.claude/projects/*/<sesion>.jsonl y sus tool-results/*.txt).

Salida: <salida_dir>/<coleccion>/<id>.json con los datos del documento (sin envoltura id/version),
el mismo formato que aceptan kit/dbprep.py.txt, sync/build_fichas.py y sync/sync_journey.py.
Si un documento aparece varias veces, gana la lectura más reciente. Imprime cuántos documentos
escribió por colección. Autorizado por Christopher el 04/11/2026 para la tarea «Vista compartida».
"""
import glob, json, os, re, sys

out = sys.argv[1]
want = set(sys.argv[2:])
HEAD = re.compile(r'(\d+) documents? from collection "([^"]+)":')
BEGIN = re.compile(r'^=== BEGIN ARTIFACT DB [^\n]*===$', re.M)
END = re.compile(r'^=== END ARTIFACT DB [^\n]*===$', re.M)


def textos():
    """Devuelve (orden, texto) de cada resultado de herramienta de la sesión más reciente."""
    js = sorted(glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl')), key=os.path.getmtime)
    if not js:
        return []
    ses = js[-1]
    res = []
    n = 0
    for line in open(ses, encoding='utf-8'):
        if 'ARTIFACT DB' not in line and 'tool-results' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        c = (o.get('message') or {}).get('content')
        if not isinstance(c, list):
            continue
        for b in c:
            if not isinstance(b, dict) or b.get('type') != 'tool_result':
                continue
            cc = b.get('content')
            t = cc if isinstance(cc, str) else ''.join(x.get('text', '') for x in (cc or []) if isinstance(x, dict))
            n += 1
            res.append((n, t))
            for p in re.findall(r'(/[^\s"\']+/tool-results/[^\s"\']+\.txt)', t):
                if os.path.exists(p):
                    try:
                        res.append((n + 0.5, open(p, encoding='utf-8').read()))
                    except Exception:
                        pass
    return res


docs = {}
for _, t in textos():
    for h in HEAD.finditer(t):
        col = h.group(2)
        if want and col not in want:
            continue
        b = BEGIN.search(t, h.end())
        if not b:
            continue
        e = END.search(t, b.end())
        if not e:
            continue
        for ln in t[b.end():e.start()].splitlines():
            ln = ln.strip()
            if not ln.startswith('{'):
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if isinstance(d, dict) and 'id' in d and isinstance(d.get('data'), dict):
                docs.setdefault(col, {})[d['id']] = d['data']

cnt = {}
for col, m in docs.items():
    dd = os.path.join(out, *col.split('/'))
    os.makedirs(dd, exist_ok=True)
    for i, data in m.items():
        json.dump(data, open(os.path.join(dd, i + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    cnt[col] = len(m)
print('db_extract:', json.dumps(cnt, ensure_ascii=False) if cnt else 'NADA (no se encontraron lecturas de ArtifactData en la sesión)')
sys.exit(0 if cnt else 1)
