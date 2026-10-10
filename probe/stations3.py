"""Second one-off check: Spain's geoportal download routes, Argentina's current CSV, Mexico's and Portugal's terms."""
import json, pathlib, re, time
import requests
OUT = pathlib.Path(__file__).resolve().parent / 'out3'
OUT.mkdir(parents=True, exist_ok=True)
BROWSER = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'}
report = {}
def grab(name, url, keep=2_000_000, timeout=120, method='GET', **kw):
    t = time.time(); rec = {'url': url}
    try:
        r = requests.request(method, url, headers=BROWSER, timeout=timeout, **kw)
        rec.update(status=r.status_code, final=r.url, ctype=r.headers.get('content-type'), bytes=len(r.content),
                   disp=r.headers.get('content-disposition'))
        (OUT / name).write_bytes(r.content[:keep]); rec['saved'] = name + (' (truncated)' if len(r.content) > keep else '')
    except Exception as e:
        rec['error'] = f'{type(e).__name__}: {str(e)[:300]}'
    rec['seconds'] = round(time.time() - t, 1); report[name] = rec
    print(name, rec)
G = 'https://geoportalgasolineras.es/'
for js in ('resources/app/modules/downloads/DownloadsService.js?v=1.0.0', 'resources/app/modules/downloads/DownloadsCtrl.js?v=1.0.0',
           'resources/app/modules/downloadsPrices/DownloadPricesDirective.js?v=1.0.2',
           'resources/app/modules/downloadsRestServices/RestServiceDirective.js?v=1.0.0'):
    grab('es_' + js.split('/')[-1].split('?')[0], G + js, keep=200000)
# endpoints mentioned in those scripts, tried directly
txt = ''.join((OUT / n).read_text('utf-8', 'replace') for n in list(report) if (OUT / n).exists())
cands = sorted(set(re.findall(r"['\"](/?geoportal[-\w/]*|[-\w]+/[-\w/]*(?:Descarg|descarg|Export|export|Precio|precio|xls|csv)[-\w/]*)['\"]", txt)))
report['es_candidates'] = cands
for i, c in enumerate(cands[:12]):
    grab(f'es_try_{i}', G + c.lstrip('/'), keep=300000, timeout=180)
# Argentina: current prices CSV (CC BY 4.0)
grab('ar_vigentes.csv', 'http://datos.energia.gob.ar/dataset/1c181390-5045-475e-94dc-410429be4b17/resource/80ac25de-a44a-4445-9215-090cf55cfda5/download/precios-en-surtidor-resolucin-3142016.csv', keep=12_000_000, timeout=300)
# Mexico: dataset pages that should state the licence
grab('mx_hist_page', 'https://historico.datos.gob.mx/busca/dataset/estaciones-de-servicio-gasolineras-y-precios-finales-de-gasolina-y-diesel', keep=400000)
grab('mx_cne_page', 'https://www.cne.gob.mx/ConsultaPrecios/GasolinasyDiesel/GasolinasyDiesel.html', keep=400000)
grab('mx_terms', 'https://historico.datos.gob.mx/libreusomx', keep=400000)
# Portugal: site page, fuel types, a full page of stations for one fuel
grab('pt_page', 'https://precoscombustiveis.dgeg.gov.pt/', keep=400000)
grab('pt_tipos', 'https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/GetTiposCombustiveis', keep=100000)
grab('pt_95_all', 'https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/PesquisarPostos?idsTiposComb=3201&qtdPorPagina=4000&pagina=1', keep=3_000_000, timeout=180)
for p in ('termos-e-condicoes', 'termos', 'sobre', 'faq', 'api'):
    grab(f'pt_{p}', f'https://precoscombustiveis.dgeg.gov.pt/{p}/', keep=200000)
(OUT / 'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
