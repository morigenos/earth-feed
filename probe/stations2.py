"""One-off check, run on GitHub's runners: can the candidate station-price sources be reached, what do they
return, and what licence do their catalogues state? Results go to probe/out/ and are committed to this branch."""
import json, pathlib, re, socket, time, traceback
import requests
OUT = pathlib.Path(__file__).resolve().parent / 'out'
OUT.mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'earth-feed/1.0 (+https://github.com/morigenos/earth-feed)'}
BROWSER = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'}
report = {}

def grab(name, url, keep=0, headers=UA, timeout=90, stream_cap=None):
    t = time.time(); rec = {'url': url}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        rec.update(status=r.status_code, final=r.url, ctype=r.headers.get('content-type'), clen=r.headers.get('content-length'))
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf += chunk
            if stream_cap and len(buf) >= stream_cap: rec['capped'] = True; break
        rec['bytes'] = len(buf); rec['head'] = bytes(buf[:1500]).decode('utf-8', 'replace')
        if keep and len(buf) <= keep: (OUT / name).write_bytes(bytes(buf)); rec['saved'] = name
        elif keep: (OUT / name).write_bytes(bytes(buf[:keep])); rec['saved'] = name + ' (truncated)'
        if 'html' in (rec['ctype'] or ''):
            links = sorted(set(re.findall(r'(?:href|src)="([^"]+)"', bytes(buf).decode('utf-8', 'replace'))))
            rec['links'] = [l for l in links if re.search(r'csv|xls|xml|json|zip|download|descarg|licen|terms|api', l, re.I)][:80]
    except Exception as e:
        rec['error'] = f'{type(e).__name__}: {str(e)[:400]}'
    rec['seconds'] = round(time.time() - t, 1)
    report[name] = rec; print(name, {k: v for k, v in rec.items() if k not in ('head', 'links')})

# Spain: the REST service refused the runners twice on 10 Oct. Try it again, plain and with a browser agent,
# resolve its addresses, and look for the geoportal's bulk download as a second route.
ES = 'https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/'
try: report['es_dns'] = sorted({a[4][0] for a in socket.getaddrinfo('sedeaplicaciones.minetur.gob.es', 443)})
except Exception as e: report['es_dns'] = str(e)
for i in range(3):
    grab(f'es_rest_{i}', ES, stream_cap=200000); time.sleep(10)
grab('es_rest_browser', ES, headers=BROWSER, stream_cap=200000)
grab('es_rest_http', ES.replace('https://', 'http://'), stream_cap=200000)
grab('es_geoportal', 'https://geoportalgasolineras.es/geoportal-instalaciones/Inicio', headers=BROWSER)
grab('es_geoportal_desc', 'https://geoportalgasolineras.es/geoportal-instalaciones/DescargarFicheros', headers=BROWSER)
grab('es_geoportal_root', 'https://geoportalgasolineras.es/', headers=BROWSER)

# United Kingdom: Fuel Finder (statutory scheme since 2026); the CSV is said to need no registration.
grab('uk_ff_page', 'https://www.developer.fuel-finder.service.gov.uk/access-latest-fuelprices', headers=BROWSER)
grab('uk_ff_page2', 'https://www.developer.fuel-finder.service.gov.uk/fuel-finder/access-latest-fuelprices', headers=BROWSER)
grab('uk_ff_root', 'https://www.developer.fuel-finder.service.gov.uk/', headers=BROWSER)
grab('uk_ff_terms', 'https://www.developer.fuel-finder.service.gov.uk/terms-and-conditions', headers=BROWSER)

# Mexico: CNE (formerly CRE) daily XML of permit-holder prices, and the station list with coordinates.
grab('mx_prices.xml', 'https://publicacionexterna.azurewebsites.net/publicaciones/prices', keep=8_000_000, timeout=180)
grab('mx_places.xml', 'https://publicacionexterna.azurewebsites.net/publicaciones/places', keep=8_000_000, timeout=180)
grab('mx_ckan', 'https://historico.datos.gob.mx/busca/api/3/action/package_show?id=estaciones-de-servicio-gasolineras-y-precios-finales-de-gasolina-y-diesel', keep=200000)
grab('mx_ckan2', 'https://www.datos.gob.mx/api/3/action/package_search?q=gasolineras%20precios', keep=300000)

# Argentina: Secretaría de Energía, prices reported under Resolución 314/2016.
grab('ar_ckan', 'http://datos.energia.gob.ar/api/3/action/package_show?id=precios-en-surtidor', keep=300000)
grab('ar_page', 'http://datos.energia.gob.ar/dataset/precios-en-surtidor', headers=BROWSER)

# Germany (needs a key, but read the terms) and Portugal (terms unknown).
grab('de_tk', 'https://creativecommons.tankerkoenig.de/', headers=BROWSER)
grab('de_tk_terms', 'https://creativecommons.tankerkoenig.de/terms', headers=BROWSER)
grab('pt_dgeg', 'https://precoscombustiveis.dgeg.gov.pt/', headers=BROWSER)
grab('pt_api', 'https://precoscombustiveis.dgeg.gov.pt/api/PrecoComb/PesquisarPostos?idsTiposComb=3201&qtdPorPagina=5&pagina=1', keep=100000)

(OUT / 'report.json').write_text(json.dumps(report, indent=1, ensure_ascii=False))
