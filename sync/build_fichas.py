#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_fichas.py — Ficha de evaluación de cada asesor para el Mapa de Procesos (GitHub Pages).

Toma la "vista compartida" que el Tablero DIV-PRE guarda en su base de datos cada vez que el
supervisor lo abre (colección `snap`/`snapparts`, ya sin datos personales de clientes) y arma
una página independiente por asesor con el MISMO HTML y el MISMO CSS del tablero, de modo que
la ficha se vea en el Mapa tal cual se ve en el tablero.

Entradas (las deja la tarea programada en sync/inputs/):
  sync/inputs/snap/meta.json              ← ArtifactData get  snap/meta   (out_dir=sync/inputs)
  sync/inputs/snapparts/ase2-<i>.json     ← ArtifactData list snapparts   (out_dir=sync/inputs)
  sync/inputs/tablero/index.html          ← Artifact read   path=index.html (out_dir=sync/inputs/tablero)
                                            (opcional: si falta, se conserva fichas/ficha.css)
Salidas (se publican en el repo):
  fichas/ficha.css          CSS del tablero + ajustes para la ficha sola
  fichas/<slug>.html        una página por asesor
  fichas/index.json         versión (savedAt del corte), corte y lista de asesores

Uso:  python3 sync/build_fichas.py            (desde la raíz del repo)
Sale con código 0 si generó o si no hubo cambios; imprime "fichas: ACTUALIZADO" o "fichas: SIN CAMBIOS".
"""
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = os.path.join(ROOT, 'sync', 'inputs')
OUT = os.path.join(ROOT, 'fichas')
META_PATH = os.path.join(INP, 'snap', 'meta.json')
PARTS_DIR = os.path.join(INP, 'snapparts')
TABLERO_PATHS = [os.path.join(INP, 'tablero', 'index.html'), os.path.join(INP, 'tablero.html')]
LIMA = timezone(timedelta(hours=-5))


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def doc_data(obj):
    """ArtifactData guarda {id,data,version,...}; también acepto el documento pelado."""
    if isinstance(obj, dict) and 'data' in obj and isinstance(obj['data'], dict):
        return obj['data']
    return obj


def slug(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'[^A-Za-z0-9]+', '-', s).strip('-').lower()
    return s or 'asesor'


def remove_elements(html, open_re):
    """Quita cada elemento cuya etiqueta de apertura cumple open_re (regex), con todo su contenido."""
    out = html
    pat = re.compile(open_re)
    while True:
        m = pat.search(out)
        if not m:
            return out
        start = m.start()
        tag = re.match(r'<([A-Za-z][A-Za-z0-9]*)', out[start:]).group(1)
        tok = re.compile(r'<(/?)(' + re.escape(tag) + r')(?=[\s>/])', re.I)
        depth = 0
        end = None
        for mm in tok.finditer(out, start):
            if mm.group(1):
                depth -= 1
            else:
                # etiqueta autocerrada <tag .../> no cuenta
                close = out.find('>', mm.start())
                if close > 0 and out[close - 1] == '/':
                    continue
                depth += 1
            if depth == 0:
                end = out.find('>', mm.start()) + 1
                break
        if end is None:
            # sin cierre: quito solo la apertura para no ciclar
            end = out.find('>', start) + 1
        out = out[:start] + out[end:]


def extract_style(tablero_html):
    """El <style> propio del tablero (el que define --bg); el archivo publicado trae antes un reset chico."""
    for m in re.finditer(r'<style>', tablero_html):
        i = m.end()
        j = tablero_html.find('</style>', i)
        if j < 0:
            break
        chunk = tablero_html[i:j]
        if '--bg:#ffffff' in chunk[:600] or '--bg:' in chunk[:400]:
            return chunk
    raise SystemExit('No encontré el <style> del tablero en el archivo de entrada')


EXTRA_CSS = r"""
/* ===== Ajustes para la ficha sola (fuera del tablero) ===== */
html,body{min-height:0}
body.ficha-solo{padding:0;margin:0;display:block}
body.ficha-solo main{max-width:1180px;margin:0 auto;padding:12px 12px 20px}
body.ficha-solo .view{display:block}
body.ficha-solo .ase-card2[hidden]{display:block}
body.ficha-solo .blk{margin-bottom:0}
body.ficha-solo .fb,body.ficha-solo .ctrl,body.ficha-solo [data-send],body.ficha-solo [data-cal],body.ficha-solo [data-drive],body.ficha-solo details.ckf,body.ficha-solo .nosnap,body.ficha-solo .mvb,body.ficha-solo .kord{display:none!important}
body.ficha-solo.en-marco main{padding:0 0 6px}
body.ficha-solo.en-marco .blk{border-radius:14px}
/* Barra propia cuando la ficha se abre en su propia pestaña */
.fx-bar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;background:var(--surface);border-bottom:1px solid var(--line);font-size:13px}
.fx-bar b{font-size:14px;color:var(--ink)}
.fx-bar .mut{color:var(--muted)}
.fx-bar .sp{flex:1}
.fx-bar a,.fx-bar button{font:inherit;font-weight:600;font-size:12.5px;border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:999px;padding:6px 12px;cursor:pointer;text-decoration:none;white-space:nowrap}
.fx-bar a:hover,.fx-bar button:hover{border-color:var(--ink)}
body.en-marco .fx-bar{display:none}
@media (max-width:640px){body.ficha-solo main{padding:8px 6px 16px}.fx-bar{padding:8px 10px;gap:6px}}
/* Celular: cada indicador en 2 líneas (nombre + valor arriba, barra completa abajo) para que la barra no tape
   los números, y la leyenda de siglas con el texto completo (sin "…") */
@media (max-width:560px){
  body.ficha-solo .v2a.v2m{grid-template-columns:34px minmax(0,1fr) auto;grid-template-areas:"k n v" "b b b";row-gap:4px;column-gap:6px;padding:4px 0 6px;border-bottom:1px solid var(--line)}
  body.ficha-solo .v2a.v2m:last-child{border-bottom:0}
  body.ficha-solo .v2a.v2m>.fak{grid-area:k}
  body.ficha-solo .v2a.v2m>b:nth-child(2){grid-area:n;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  body.ficha-solo .v2a.v2m>.cb{grid-area:b;height:7px}
  body.ficha-solo .v2a.v2m>.v2lv{grid-area:v;justify-content:flex-end}
  body.ficha-solo .v2att{gap:2px}
  body.ficha-solo .v2gl>div{white-space:normal;overflow:visible;text-overflow:clip;display:grid;grid-template-columns:34px minmax(0,1fr);gap:6px;padding:2px 0}
  body.ficha-solo .v2gl{font-size:.74rem;line-height:1.35}
  body.ficha-solo .v2gl small{font-size:.74rem}
}
"""

# El script de la ficha: alto para el marco, tema, cajas del plan, copiar como imagen.
FICHA_JS = r"""
(function(){
  'use strict';
  var $=function(s,r){return (r||document).querySelector(s);};
  var enMarco=false; try{ enMarco=window.self!==window.top; }catch(e){ enMarco=true; }
  if(enMarco) document.body.classList.add('en-marco');
  var INFO=window.__FICHA||{};
  function temaGuardado(){ try{ return localStorage.getItem('cgo_ficha_tema'); }catch(e){ return null; } }
  function aplicarTema(t,guardar){ t=(t==='light'||t==='claro')?'light':'dark'; document.documentElement.setAttribute('data-theme',t);
    if(guardar){ try{ localStorage.setItem('cgo_ficha_tema',t); }catch(e){} }
    var b=$('#fxTema'); if(b) b.textContent=t==='dark'?'☀️ Modo claro':'🌙 Modo oscuro';
    avisarAlto(); }
  var q=new URLSearchParams(location.search); aplicarTema(q.get('tema')||temaGuardado()||'dark',false);
  // Las 3 cajas del plan (bien / foco / siguiente nivel) con la misma altura, igual que en el tablero
  function fitPlan(pl){ if(!pl||!pl.offsetHeight) return; var bx=[].slice.call(pl.children); if(bx.length<3) return;
    pl.querySelectorAll('.fxh').forEach(function(e){e.classList.remove('fxh');});
    if(window.innerWidth<900||bx[0].getBoundingClientRect().top!==bx[2].getBoundingClientRect().top) return;   // en celular/tablet se ve todo el texto
    bx.forEach(function(b){b.style.alignSelf='start';}); var H=bx[2].offsetHeight;
    [bx[0],bx[1]].forEach(function(b){ var L=[].slice.call(b.querySelectorAll('[data-fx]')).sort(function(x,y){return (+y.dataset.fx)-(+x.dataset.fx);}); var i=0; while(b.offsetHeight>H&&i<L.length) L[i++].classList.add('fxh'); });
    bx.forEach(function(b){b.style.alignSelf='';}); }
  function ajustar(){ requestAnimationFrame(function(){ document.querySelectorAll('.v2plan').forEach(fitPlan); avisarAlto(); }); }
  var altoT; function avisarAlto(){ if(!enMarco) return; clearTimeout(altoT); altoT=setTimeout(function(){ var h=Math.ceil(document.documentElement.scrollHeight); try{ window.parent.postMessage({type:'cgo-ficha-alto',alto:h,slug:INFO.slug||''},'*'); }catch(e){} },30); }
  window.addEventListener('resize',function(){ clearTimeout(window.__fpT); window.__fpT=setTimeout(ajustar,150); });
  if(window.ResizeObserver){ try{ new ResizeObserver(function(){ avisarAlto(); }).observe(document.body); }catch(e){} }
  window.addEventListener('message',function(ev){ var d=ev&&ev.data||{}; if(d.type==='cgo-ficha-tema') aplicarTema(d.tema,true); if(d.type==='cgo-ficha-copiar') copiar(); if(d.type==='cgo-ficha-alto?') avisarAlto(); });
  // ---- Copiar como imagen (mismo cuadro que manda el tablero por WhatsApp)
  function loadH2C(){ return new Promise(function(res,rej){ if(window.html2canvas) return res(); var s=document.createElement('script'); s.src='https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js'; s.onload=res; s.onerror=function(){rej(new Error('html2canvas'));}; document.head.appendChild(s); }); }
  var esMovil=function(){ return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)||(navigator.maxTouchPoints>1&&window.matchMedia&&matchMedia('(pointer:coarse)').matches); };
  function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];}); }
  async function renderSnap(sec){
    await loadH2C(); var oscuro=document.documentElement.getAttribute('data-theme')!=='light';
    var card=document.createElement('div'); card.className='snapcard';
    var title=sec.querySelector('.bh h2')?sec.querySelector('.bh h2').innerHTML:''; var q=sec.querySelector('.bh .desc > p')?sec.querySelector('.bh .desc > p').textContent:'';
    card.innerHTML='<div class="snaphead"><div><div class="snapbrand">Dashboard CGO Distancia Nacional · By: Christopher Huaman</div><div class="snaptitle">'+title+'</div>'+(q?'<div class="snapq">'+esc(q)+'</div>':'')+'</div><div class="snapdate">'+esc(INFO.fecha||'')+'</div></div>';
    var body=sec.querySelector('.bb').cloneNode(true); body.querySelectorAll('details.more,details.mini,details.alerta').forEach(function(d){d.remove();}); body.querySelectorAll('details').forEach(function(d){ d.setAttribute('open',''); });
    body.querySelectorAll('.ctrl,select,input,button,.expbar').forEach(function(el){el.remove();}); card.appendChild(body);
    var host=document.createElement('div'); host.className='snaphost'+(oscuro?'':' light'); host.setAttribute('data-theme',oscuro?'dark':'light'); host.appendChild(card); document.body.appendChild(host);
    var need=Math.max(1180,...[].slice.call(card.querySelectorAll('table')).map(function(t){return t.scrollWidth+80;})); host.style.width=need+'px';   // la ficha está pensada para ~1180 px: así la imagen sale igual que en pantalla
    try{ card.querySelectorAll('.v2plan').forEach(fitPlan); }catch(e){}
    var over=Math.max(card.scrollWidth,...[].slice.call(card.querySelectorAll('.fifa,.fgrid,.fbody,.cal,.tw,.grid2')).map(function(e){return e.scrollWidth+60;})); if(over>need){ need=Math.min(1600,over+20); host.style.width=need+'px'; }
    try{
      var W0=card.offsetWidth||1100,H0=card.offsetHeight||800,wantS=Math.min(3,Math.max(2,(window.devicePixelRatio||1)*2));
      var maxS=Math.min(4,Math.max(wantS,3),Math.sqrt((esMovil()?14e6:60e6)/(W0*H0)),16000/H0,16000/W0);
      var shot=function(sc){ return window.html2canvas(card,{backgroundColor:oscuro?'#0f1626':'#ffffff',scale:Math.max(1,sc),useCORS:true,logging:false,windowWidth:need}); };
      var canvas; try{ canvas=await shot(maxS); }catch(e1){ canvas=await shot(Math.min(1.5,maxS)); }
      var blob=await new Promise(function(r){canvas.toBlob(r,'image/png');}); if(!blob){ canvas=await shot(1.5); blob=await new Promise(function(r){canvas.toBlob(r,'image/png');}); }
      return {blob:blob,url:canvas.toDataURL('image/png')};
    } finally { host.remove(); }
  }
  function showShare(r,nombre){
    var m=$('#imgModal'); if(!m){ m=document.createElement('div'); m.id='imgModal'; m.className='modal'; document.body.appendChild(m); m.addEventListener('click',function(ev){ if(ev.target===m||ev.target.dataset.close) m.remove(); }); }
    var file=function(){ return new File([r.blob],nombre,{type:'image/png'}); }; var puedeShare=false; try{ puedeShare=!!(navigator.share&&navigator.canShare&&navigator.canShare({files:[file()]})); }catch(e){}
    m.innerHTML='<div class="mbox shbox"><div class="mhead"><b>📷 Imagen lista</b><button class="btn" data-close="1">Cerrar</button></div>'
      +'<div class="expbar shbar">'+(puedeShare?'<button class="btn pri" id="shShare">📲 Enviar por WhatsApp…</button>':'')+'<button class="btn '+(puedeShare?'':'pri')+'" id="shSave">⬇ Guardar</button><button class="btn" id="shCopy">📋 Copiar</button></div>'
      +'<p class="note" id="shMsg">'+(puedeShare?'«Enviar» abre el menú de compartir: elige WhatsApp y el chat.':'Guárdala y adjúntala desde WhatsApp.')+' También puedes mantener presionada la imagen → Compartir o Guardar.</p>'
      +'<img src="'+r.url+'" alt="Imagen de la ficha" style="width:100%;height:auto;border-radius:8px"></div>';
    var msg=function(t){ var el=$('#shMsg'); if(el) el.textContent=t; };
    var sh=$('#shShare'); if(sh) sh.onclick=async function(){ try{ await navigator.share({files:[file()],title:nombre.replace(/_/g,' ').replace(/\.png$/,'')}); msg('Enviada ✅'); }catch(e){ if(e&&e.name==='AbortError') return; msg('Aquí no se puede abrir el menú de compartir: usa «Guardar» o mantén presionada la imagen → Compartir.'); } };
    $('#shSave').onclick=function(){ try{ var a=document.createElement('a'); a.href=r.url; a.download=nombre; document.body.appendChild(a); a.click(); a.remove(); msg('Descargada: búscala en Descargas y adjúntala desde WhatsApp.'); }catch(e){ msg('No se pudo guardar: mantén presionada la imagen → Guardar imagen.'); } };
    $('#shCopy').onclick=async function(){ try{ if(!navigator.clipboard||!window.ClipboardItem) throw new Error('sin portapapeles'); await navigator.clipboard.write([new ClipboardItem({'image/png':r.blob})]); msg('Copiada ✅ Pégala en el chat. Si tu WhatsApp no deja pegar imágenes, usa «Enviar» o «Guardar».'); }catch(e){ msg('Este dispositivo no permite copiar imágenes desde el navegador: usa «Enviar» o «Guardar».'); } };
    avisarAlto();
  }
  var copiando=false;
  async function copiar(){ if(copiando) return; copiando=true; var b=$('#fxCopiar'); var old=b?b.textContent:''; if(b){ b.textContent='Generando…'; b.disabled=true; }
    try{ var sec=$('.ase-card2 section.blk'); var r=await renderSnap(sec); var nombre='Ficha_'+(INFO.corto||'asesor')+'.png';
      // Dentro del Mapa de Procesos la vista previa la muestra la página de afuera (en su propia ventana)
      var enviado=false; if(enMarco){ try{ window.parent.postMessage({type:'cgo-ficha-imagen',url:r.url,nombre:nombre},'*'); enviado=true; }catch(e){} }
      if(!enviado) showShare(r,nombre); }
    catch(e){ console.error('Captura',e); var avisado=false; if(enMarco){ try{ window.parent.postMessage({type:'cgo-ficha-error',msg:'No se pudo generar la imagen'},'*'); avisado=true; }catch(e2){} } if(!avisado) alert('No se pudo generar la imagen'); }
    if(b){ b.disabled=false; b.textContent=old; } copiando=false; }
  window.cgoFicha={copiar:copiar,tema:function(t){aplicarTema(t,true);},alto:avisarAlto};
  document.addEventListener('click',function(e){ var t=e.target.closest&&e.target.closest('[data-fx-accion]'); if(!t) return; var a=t.dataset.fxAccion; if(a==='copiar') copiar(); if(a==='tema') aplicarTema(document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark',true); });
  document.addEventListener('toggle',function(){ avisarAlto(); },true);
  window.addEventListener('load',function(){ ajustar(); setTimeout(avisarAlto,400); setTimeout(avisarAlto,1500); });
  ajustar();
})();
"""


def ficha_html(card_html, a, meta, css_v):
    nombre_corto = a['d']
    titulo = 'Ficha de %s · CGO Distancia' % nombre_corto
    corte = meta.get('corte', '')
    corte_corto = re.sub(r'\s*·\s*By:.*$', '', corte).strip()
    info = {'slug': a['s'], 'corto': nombre_corto, 'nombre': a['n'], 'sede': a.get('sede', ''), 'corte': corte_corto, 'fecha': meta.get('fecha', ''), 'version': meta.get('savedAt', '')}
    bar = ('<div class="fx-bar"><b>📋 Ficha de evaluación · %s</b><span class="mut">%s</span><span class="sp"></span>'
           '<button type="button" id="fxTema" data-fx-accion="tema">☀️ Modo claro</button>'
           '<button type="button" id="fxCopiar" data-fx-accion="copiar">📷 Copiar como imagen</button>'
           '<a href="../#ficha">← Volver al Mapa de Procesos</a></div>') % (esc(nombre_corto + (' · ' + a['sede'] if a.get('sede') else '')), esc(corte_corto))
    return ('<!DOCTYPE html>\n<html lang="es" data-theme="dark">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="robots" content="noindex, nofollow">\n'
            '<title>%s</title>\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;800&display=swap" rel="stylesheet">\n'
            '<link rel="stylesheet" href="ficha.css?v=%s">\n'
            '</head>\n<body class="shared ficha-solo">\n%s\n<main><div class="view on" id="v-ase2"><div id="ase2">%s</div></div></main>\n'
            '<script>window.__FICHA=%s;</script>\n<script>%s</script>\n</body>\n</html>\n'
            ) % (esc(titulo), css_v, bar, card_html, json.dumps(info, ensure_ascii=False), FICHA_JS)


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def main():
    if not os.path.exists(META_PATH):
        raise SystemExit('Falta %s (ArtifactData get snap/meta con out_dir=sync/inputs)' % META_PATH)
    meta = doc_data(read_json(META_PATH))
    n_parts = int((meta.get('parts') or {}).get('ase2') or 0)
    if n_parts <= 0:
        raise SystemExit('snap/meta no trae parts.ase2: el tablero aún no guardó la vista de Asesor')
    html = ''
    pre = (meta.get('key') + '-') if meta.get('key') else ''   # desde v228 del Tablero las partes llevan la clave del corte
    for i in range(n_parts):
        p = os.path.join(PARTS_DIR, '%sase2-%d.json' % (pre, i))
        if not os.path.exists(p):
            raise SystemExit('Falta la parte %s' % p)
        html += doc_data(read_json(p)).get('h', '')

    # ---- asesores (orden alfabético del selector del tablero)
    sel = {}
    for m in re.finditer(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', html):
        full = unescape_html(m.group(1)); label = unescape_html(m.group(2))
        d, _, sede = label.partition(' · ')
        sel[full] = {'d': d.strip(), 'sede': sede.strip()}
    pieces = html.split('<div class="ase-card2" ')
    cards = []
    for piece in pieces[1:]:
        card = '<div class="ase-card2" ' + piece
        m = re.match(r'<div class="ase-card2" data-ase="([^"]*)"', card)
        if not m:
            continue
        full = unescape_html(m.group(1))
        card = re.sub(r'^(<div class="ase-card2" data-ase="[^"]*")\s*hidden(?:="")?', r'\1', card)
        card = remove_elements(card, r'<div[^>]*\bclass="fb"[^>]*>')
        card = remove_elements(card, r'<details[^>]*\bclass="[^"]*\bckf\b[^"]*"[^>]*>')
        card = remove_elements(card, r'<[a-z]+[^>]*\bclass="[^"]*\bnosnap\b[^"]*"[^>]*>')
        card = remove_elements(card, r'<button[^>]*\bdata-(?:send|cal|drive|snap|snapdl|fb)=[^>]*>')
        info = sel.get(full) or {'d': full.split(' ')[0].title(), 'sede': ''}
        cards.append({'n': full, 's': slug(full), 'd': info['d'], 'sede': info['sede'], 'html': card})
    if not cards:
        raise SystemExit('La vista de Asesor no trae fichas')
    cards.sort(key=lambda c: (c['d'].lower(), c['n']))

    # ---- CSS
    os.makedirs(OUT, exist_ok=True)
    css_path = os.path.join(OUT, 'ficha.css')
    tablero = next((p for p in TABLERO_PATHS if os.path.exists(p)), None)
    if tablero:
        with open(tablero, encoding='utf-8') as f:
            css = extract_style(f.read().replace('\r\n', '\n')) + '\n' + EXTRA_CSS
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(css)
    elif os.path.exists(css_path):
        print('⚠️ Sin sync/inputs/tablero/index.html: se conserva el CSS del tablero de fichas/ficha.css (con los ajustes propios al día)')
        with open(css_path, encoding='utf-8') as f:
            base = f.read().split('/* ===== Ajustes para la ficha sola')[0].rstrip('\n')
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(base + '\n' + EXTRA_CSS)
    else:
        raise SystemExit('Falta el CSS: no hay sync/inputs/tablero/index.html ni fichas/ficha.css')
    with open(css_path, 'rb') as f:
        css_v = hashlib.sha1(f.read()).hexdigest()[:10]

    # ---- páginas
    wanted = set()
    for a in cards:
        fn = a['s'] + '.html'
        wanted.add(fn)
        with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
            f.write(ficha_html(a['html'], a, meta, css_v))
    # fichas de asesores que ya no están
    for fn in os.listdir(OUT):
        if fn.endswith('.html') and fn not in wanted and fn != 'index.html':
            os.remove(os.path.join(OUT, fn))

    # ---- índice
    idx_path = os.path.join(OUT, 'index.json')
    prev = read_json(idx_path) if os.path.exists(idx_path) else {}
    corte = meta.get('corte', '')
    index = {
        'version': meta.get('savedAt', ''),
        'corte': re.sub(r'\s*·\s*By:.*$', '', corte).strip(),
        'fecha': meta.get('fecha', ''),
        'css': css_v,
        'generado': datetime.now(LIMA).strftime('%Y-%m-%dT%H:%M:%S%z'),
        'asesores': [{'n': a['n'], 's': a['s'], 'd': a['d'], 'sede': a['sede']} for a in cards],
    }
    same = prev.get('version') == index['version'] and prev.get('css') == css_v and prev.get('asesores') == index['asesores']
    if same:
        index['generado'] = prev.get('generado', index['generado'])
    with open(idx_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print('fichas: %s · corte "%s" · %d asesores · css %s' % ('SIN CAMBIOS' if same else 'ACTUALIZADO', index['corte'], len(cards), css_v))


def unescape_html(s):
    import html as _h
    return _h.unescape(s)


if __name__ == '__main__':
    main()
