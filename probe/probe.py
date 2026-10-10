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

# Round 2: UK CSVs by absolute URL, Spain with browser-like headers
for name, u in [('uk_weekly_2018.csv', 'https://assets.publishing.service.gov.uk/media/6ac3b5951ef3e896de979385/CSV__2018_-__.csv'),
                ('uk_weekly_2003_2017.csv', 'https://assets.publishing.service.gov.uk/media/68a3326b32d2c63f869343a3/weekly_road_fuel_prices_2003_to_2017.csv')]:
    save(name, u)
UA.update({'Accept': 'application/json', 'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'})
save('es_stations.json', 'https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/', keep='gz')
(OUT / 'report2.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
print(json.dumps(report, indent=1))
