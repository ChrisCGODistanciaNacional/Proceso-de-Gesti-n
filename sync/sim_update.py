#!/usr/bin/env python3
"""Actualiza sim/datos.json (Simulador de llamadas del Mapa de Procesos).

Uso (en cada corte de ACTUALIZAR MANUAL):
  python3 sync/sim_update.py --corte "19/11/2026 12:08" --llamadas llamadas.json [--pre pre.json]
    llamadas.json = {"<nombre CRM o Genesys>": total_llamadas_de_hoy, ...}   (Genesys «Rendimiento del agente»: Manejo)
    pre.json      = {"<usuario de preinscripción CRM>": {"DD": n, ...}, ...} (vista A00, fecha APEC del mes; reemplaza el mes)
Solo escribe el día del corte para las llamadas; los preinscritos se reemplazan por el conteo del mes que trae pre.json.
Meta del mes y días a trabajar: campos "meta" y "dias" del archivo (por defecto 26 y 26).
"""
import argparse, json, os, re, unicodedata
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = os.path.join(R, 'sim', 'datos.json')
def nn(s): return re.sub(r'\s+', ' ', ''.join(c for c in unicodedata.normalize('NFD', str(s or '').lower()) if unicodedata.category(c) != 'Mn')).strip()
def slugs():
    idx = json.load(open(os.path.join(R, 'fichas', 'index.json'), encoding='utf-8'))
    return [(set(nn(a['n']).split()), a['s']) for a in idx['asesores']]
def slug_de(nombre, S):
    w = set(nn(nombre).split()); best = (1, None)
    for ws, s in S:
        k = len(w & ws)
        if k > best[0]: best = (k, s)
    return best[1]
ap = argparse.ArgumentParser(); ap.add_argument('--corte', required=True); ap.add_argument('--llamadas'); ap.add_argument('--pre')
a = ap.parse_args()
d, m, y = re.match(r'(\d\d)/(\d\d)/(\d{4})', a.corte).groups(); mes = f'{y}-{m}'
D = json.load(open(F, encoding='utf-8')) if os.path.exists(F) else {}
if D.get('mes') != mes: D = {'mes': mes, 'meta': D.get('meta', 26), 'dias': D.get('dias', 26), 'a': {}}
S = slugs(); A = D.setdefault('a', {})
if a.llamadas:
    for n, v in json.load(open(a.llamadas, encoding='utf-8')).items():
        s = slug_de(n, S)
        if s and int(v) > 0: A.setdefault(s, {}).setdefault('ll', {})[d] = int(v)
if a.pre:
    P = json.load(open(a.pre, encoding='utf-8'))
    for s in A: A[s]['pre'] = {}
    for n, dias in P.items():
        s = slug_de(n, S)
        if s: A.setdefault(s, {})['pre'] = {k: int(v) for k, v in dias.items()}
D['corte'] = a.corte
json.dump(D, open(F, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
print('sim:', mes, 'corte', a.corte, '·', len(A), 'asesores')
