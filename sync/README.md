# Ficha de evaluación de cada asesor (pestaña «Ficha de asesor»)

La pestaña **Ficha de asesor** del Mapa de Procesos muestra, para cada asesor, la misma ficha que
arma el Tablero DIV-PRE del supervisor (gestión comercial, calidad de llamada, metas, foco de la
semana…). No se calcula aquí: se **publica** desde el último corte del tablero.

## Cómo fluye

1. Cada vez que el supervisor abre el Tablero (artefacto `A6ZRmsZQJsjgBsE6wKNSXk`), este guarda su
   «vista compartida» en su base de datos: `snap/meta` (corte, fecha, `savedAt`, partes) y
   `snapparts/ase2-<i>` (el HTML de la pestaña Asesor, ya sin datos personales de clientes).
2. La tarea programada **«📋 Ficha de asesor → Mapa de Procesos»** (cada 2 horas, 8:10–20:10 Lima)
   lee ese snapshot con `ArtifactData`, baja el `index.html` del tablero (para su CSS) y corre:

   ```bash
   python3 sync/build_fichas.py
   ```

   que genera `fichas/ficha.css`, `fichas/<asesor>.html` (una página por asesor) y
   `fichas/index.json` (versión = `savedAt` del corte, corte, lista de asesores). Si la versión
   ya estaba publicada, no hay commit.
3. `index.html` (pestaña Ficha) lee `fichas/index.json`, recuerda quién eres
   (`localStorage.cgo_ficha_asesor`; si no, intenta con `cgo_advisor_name` de Propuesta de Valor),
   muestra la ficha en un `<iframe>` de altura automática y la revisa cada 5 minutos: si hay un
   corte nuevo, aparece la ventana «¡Tu ficha se actualizó!».

## Entradas que espera el script (`sync/inputs/`, no se versionan)

| Archivo | Cómo se obtiene |
|---|---|
| `sync/inputs/snap/meta.json` | `ArtifactData` → action `get`, collection `snap`, doc_id `meta`, `out_dir` = `sync/inputs` |
| `sync/inputs/snapparts/<key>-ase2-<i>.json` | `ArtifactData` → action `list`, collection `snapparts`, `query.limit` 1000 (desde v228 cada parte lleva la clave `meta.key`; si `meta.key` falta, los ids son `ase2-<i>`), `out_dir` = `sync/inputs` (trae todas las vistas; el script usa solo `ase2-0…ase2-(parts.ase2-1)`) |
| `sync/inputs/tablero/index.html` | `Artifact` → action `read`, `path` `index.html`, `out_dir` = `sync/inputs/tablero` (si falta, se conserva `fichas/ficha.css`) |

## Reglas

- La tarea solo toca `fichas/*`. Nunca `index.html` ni `sync/build_fichas.py`.
- Los nombres de archivo salen del nombre completo del asesor (`ana-maria-padilla-parra.html`).
  Si un asesor deja de estar en el tablero, su archivo se borra en la siguiente corrida.
- El archivo descargado del Mapa (abierto desde el disco) no incluye las fichas: la pestaña muestra
  un enlace a la versión en línea.
