#!/usr/bin/env python3
"""grid2csv.py <salida.json> <fileId> "<título>" <archivo(s)>: convierte lecturas de Google Sheets (get_values por tramos
o get_spreadsheet con includeGridData) al JSON de download_file_content {content: base64(csv), id, mimeType, title}.
Se usa para CGO_EXPORT_CRM (demasiado grande para Drive) y los exports pequeños que Drive devuelve en línea.
Verificado byte a byte contra la exportación CSV de Drive (03/11/2026)."""
import json,sys,base64,csv,io
out,fid,title=sys.argv[1:4]; rows=[]
for f in sys.argv[4:]:
    d=json.load(open(f,encoding='utf-8'))
    if 'values' in d: rows+=[[str(c) for c in r] for r in d['values']]
    else:
        for rd in d['sheets'][0]['data'][0].get('rowData',[]): rows.append([c.get('formattedValue','') for c in rd.get('values',[])])
w=max((len(r) for r in rows),default=0)
while rows and not any(rows[-1]): rows.pop()
b=io.StringIO(); cw=csv.writer(b,lineterminator='\r\n')
for r in rows: cw.writerow(r+['']*(w-len(r)))
t=b.getvalue(); t=t[:-2] if t.endswith('\r\n') else t
json.dump({'content':base64.b64encode(t.encode('utf-8')).decode(),'id':fid,'mimeType':'text/csv','title':title},open(out,'w'))
print(title,len(rows),'filas',w,'col')
