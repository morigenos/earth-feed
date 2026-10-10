"""One-off probe: fetch real samples and licence pages for candidate fuel sources.
Runs on GitHub's runners (open internet) and commits what it found to this branch."""
import gzip, io, json, pathlib, re, time, zipfile, requests
OUT = pathlib.Path(__file__).parent / 'out'; (OUT / 'licences').mkdir(parents=True, exist_ok=True)
UA = {'User-Agent': 'earth-observatory-feed probe (personal, non-commercial)'}
report = {}

def get(url, **kw):
    t = time.time()
    try:
        r = requests.get(url, headers=UA, timeout=120, **kw)
        return r, round(time.time() - t, 1), None
    except Exception as e:
        return None, round(time.time() - t, 1), f'{type(e).__name__}: {str(e)[:200]}'

def save(name, url, keep='full'):
    r, sec, err = get(url)
    rec = {'url': url, 'seconds': sec}
    if err: rec['error'] = err; report[name] = rec; return None
    rec.update(status=r.status_code, type=r.headers.get('content-type'), bytes=len(r.content), final=r.url)
    if r.ok:
        data = r.content
        if keep == 'gz': (OUT / (name + '.gz')).write_bytes(gzip.compress(data))
        elif keep == 'head':
            lines = data.decode('utf-8', 'replace').splitlines()
            (OUT / (name + '.txt')).write_text('\n'.join(lines[:400] + ['...'] + lines[-200:]), encoding='utf-8')
        else: (OUT / name).write_bytes(data)
    report[name] = rec
    return r

def text_of(html):
    html = re.sub(r'(?is)<(script|style).*?</\1>', ' ', html)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()

def licence(name, url):
    r, sec, err = get(url)
    if r is not None and r.ok:
        (OUT / 'licences' / (name + '.txt')).write_text(text_of(r.text)[:60000], encoding='utf-8')
    report['licence_' + name] = {'url': url, 'status': None if r is None else r.status_code, 'error': err}

# UK: gov.uk content API lists the current CSV attachment
r = save('uk_content.json', 'https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices')
try:
    j = r.json(); urls = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and re.search(r'\.(csv|ods|xlsx)(\?|$)', v): urls.append(v)
                walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(j); report['uk_attachments'] = urls
    for u in urls:
        if u.endswith('.csv'): save('uk_weekly.csv', u); break
except Exception as e: report['uk_parse'] = str(e)
licence('uk_gov_statistics', 'https://www.gov.uk/government/statistics/weekly-road-fuel-prices')
licence('uk_ogl', 'https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/')

# US EIA weekly retail prices (history spreadsheets)
for code, name in [('EMM_EPMRU_PTE_NUS_DPG', 'us_regular'), ('EMM_EPMPU_PTE_NUS_DPG', 'us_premium'), ('EMD_EPD2D_PTE_NUS_DPG', 'us_diesel')]:
    save(name + '.xls', f'https://www.eia.gov/dnav/pet/hist_xls/{code}w.xls')
save('us_leaf.html', 'https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=pet&s=emm_epmru_pte_nus_dpg&f=w', keep='head')
licence('us_eia_copyright', 'https://www.eia.gov/about/copyrights_reuse.php')

# Canada: Statistics Canada table 18-10-0001-01 (monthly retail prices)
save('ca_18100001.zip', 'https://www150.statcan.gc.ca/n1/tbl/csv/18100001-eng.zip')
licence('ca_statcan_licence', 'https://www.statcan.gc.ca/en/terms-conditions/open-licence')

# New Zealand: MBIE weekly fuel price monitoring
save('nz_weekly.csv', 'https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv')
licence('nz_mbie_page', 'https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring')
licence('nz_mbie_copyright', 'https://www.mbie.govt.nz/about/this-site/copyright')

# Malaysia: data.gov.my open API
save('my_fuelprice.json', 'https://api.data.gov.my/data-catalogue?id=fuelprice&limit=5000')
licence('my_terms', 'https://data.gov.my/terms-of-use')
licence('my_catalogue', 'https://data.gov.my/data-catalogue/fuelprice')

# Japan: ANRE weekly petroleum product price survey page
licence('jp_anre_page', 'https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html')

# Australia: AIP national average prices page
licence('au_aip_page', 'https://www.aip.com.au/pricing/national-retail-petrol-prices')

# FX: ECB reference rates, full history
save('ecb_eurofxref_hist.zip', 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip')
licence('ecb_copyright', 'https://www.ecb.europa.eu/services/disclaimer/html/index.en.html')

# Stations: France (data.gouv.fr ZIP, Licence Ouverte), Spain (MITECO REST), Italy (MIMIT CSV)
save('fr_instant.zip', 'https://www.data.gouv.fr/api/1/datasets/r/e4c436eb-0a7d-4b77-8a64-9ed898da0122')
save('fr_instant_json', 'https://www.data.gouv.fr/api/1/datasets/r/b0561905-7b5e-4f38-be50-df05708acb80', keep='gz')
save('es_stations.json', 'https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/', keep='gz')
licence('es_aviso_legal', 'https://geoportalgasolineras.es/geoportal-instalaciones/AvisoLegal')
save('it_prezzo_alle_8.csv', 'https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv', keep='gz')
save('it_anagrafica.csv', 'https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv', keep='gz')
licence('it_mimit_page', 'https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti')

(OUT / 'report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
print(json.dumps(report, indent=1))
