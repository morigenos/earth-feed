"""One-off source check for Stage 8, run on GitHub's runners. Saves raw samples to probe/src/."""
import csv, gzip, io, json, pathlib, re, time, traceback, zipfile
import requests
OUT = pathlib.Path(__file__).resolve().parent / 'src'
OUT.mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'earth-feed source check (github.com/morigenos/earth-feed)'}
rep = {}
def get(url, **kw):
    t = time.time()
    r = requests.get(url, headers=dict(UA, **kw.pop('headers', {})), timeout=120, **kw)
    return r, round(time.time() - t, 1)
def save(name, blob, gz=False):
    p = OUT / (name + ('.gz' if gz else ''))
    p.write_bytes(gzip.compress(blob) if gz else blob)
    return p.stat().st_size
def step(name, fn):
    try: rep[name] = fn()
    except Exception as e: rep[name] = {'error': type(e).__name__ + ': ' + str(e)[:300], 'trace': traceback.format_exc()[-800:]}

def eia():
    out = {}
    r, s = get('https://www.eia.gov/dnav/pet/xls/PET_PRI_GND_DCUS_NUS_W.xls')
    out['combined'] = {'status': r.status_code, 'bytes': len(r.content), 'sec': s, 'saved': save('eia_combined.xls', r.content) if r.ok else 0}
    if r.ok:
        import xlrd
        b = xlrd.open_workbook(file_contents=r.content)
        out['sheets'] = {}
        for sh in b.sheets():
            rows = [[str(sh.cell_value(i, j))[:90] for j in range(min(sh.ncols, 80))] for i in range(min(sh.nrows, 3))]
            out['sheets'][sh.name] = {'nrows': sh.nrows, 'ncols': sh.ncols, 'head': rows}
    for code in ('EMM_EPMR_PTE_Y05LA_DPG', 'EMM_EPMR_PTE_R1X_DPG', 'EMD_EPD2D_PTE_R5XCA_DPG', 'EMM_EPMR_PTE_SCA_DPG'):
        r, s = get(f'https://www.eia.gov/dnav/pet/hist_xls/{code}w.xls')
        out[code] = {'status': r.status_code, 'bytes': len(r.content)}
    return out

def statcan():
    r, s = get('https://www150.statcan.gc.ca/n1/tbl/csv/18100001-eng.zip')
    z = zipfile.ZipFile(io.BytesIO(r.content))
    name = [n for n in z.namelist() if re.fullmatch(r'\d+\.csv', n)][0]
    geos, fuels, latest, keep = {}, {}, {}, []
    rd = csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig'))
    head = rd.fieldnames
    for row in rd:
        g, f = row['GEO'], row['Type of fuel']
        geos[g] = geos.get(g, 0) + 1; fuels[f] = fuels.get(f, 0) + 1
        if row.get('VALUE'): latest[(g, f)] = max(latest.get((g, f), ''), row['REF_DATE'])
        if row['REF_DATE'] >= '2024-01': keep.append(row)
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=head); w.writeheader(); w.writerows(keep)
    save('statcan_since2024.csv', buf.getvalue().encode(), gz=True)
    return {'bytes': len(r.content), 'header': head, 'geos': geos, 'fuels': fuels,
            'latest': {f'{g} | {f}': d for (g, f), d in sorted(latest.items()) if d >= '2025'}}

def cre():
    out = {}
    for kind in ('places', 'prices'):
        r, s = get(f'https://publicacionexterna.azurewebsites.net/publicaciones/{kind}')
        out[kind] = {'status': r.status_code, 'bytes': len(r.content), 'sec': s, 'ctype': r.headers.get('content-type'),
                     'head': r.text[:1500], 'saved': save(f'cre_{kind}.xml', r.content, gz=True)}
    for url in ('https://historico.datos.gob.mx/busca/api/3/action/package_show?id=estaciones-de-servicio-gasolineras-y-precios-finales-de-gasolina-y-diesel',
                'https://www.datos.gob.mx/api/3/action/package_search?q=gasolineras%20precios'):
        try:
            r, s = get(url); out[url] = {'status': r.status_code, 'text': r.text[:6000]}
        except Exception as e: out[url] = {'error': str(e)[:200]}
    return out

def dgeg():
    out = {}
    base = 'https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/'
    for ep in ('GetTiposCombustiveis', 'GetMarcas', 'GetDistritos'):
        r, s = get(base + ep); out[ep] = {'status': r.status_code, 'text': r.text[:3000]}
    url = base + 'PesquisarPostos?idsTiposComb=&idMarca=&idTipoPosto=&idDistrito=&idsMunicipios=&qtdPorPagina=100000&pagina=1'
    r, s = get(url); out['PesquisarPostos'] = {'status': r.status_code, 'bytes': len(r.content), 'sec': s, 'head': r.text[:2500],
                                               'saved': save('dgeg_postos.json', r.content, gz=True)}
    for url in ('https://precoscombustiveis.dgeg.gov.pt/', 'https://precoscombustiveis.dgeg.gov.pt/termos-e-condicoes/',
                'https://precoscombustiveis.dgeg.gov.pt/api/', 'https://www.dgeg.gov.pt/pt/termos-e-condicoes/',
                'https://dados.gov.pt/api/1/datasets/?q=pre%C3%A7os%20combust%C3%ADveis&page_size=20',
                'https://dados.gov.pt/api/1/datasets/postos-de-abastecimento-de-combustiveis-para-veiculos-rodoviarios/'):
        try:
            r, s = get(url)
            t = r.text
            hits = [t[max(0, m.start() - 300): m.start() + 400] for m in re.finditer(r'(?i)licen|termos|reutiliza|condi[cç][oõ]es|copyright|direitos', t)][:12]
            out[url] = {'status': r.status_code, 'bytes': len(r.content), 'hits': hits, 'text': t[:4000] if 'api' in url else ''}
        except Exception as e: out[url] = {'error': str(e)[:200]}
    return out

for n, f in (('eia', eia), ('statcan', statcan), ('cre', cre), ('dgeg', dgeg)): step(n, f)
(OUT / 'report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False))
print(json.dumps({k: (list(v.keys()) if isinstance(v, dict) else v) for k, v in rep.items()}, indent=1))
