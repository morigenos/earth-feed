"""Station-level fuel prices from four open government feeds.

  FRA  prix-carburants (Ministère de l'Économie), instant feed v2 on data.gouv.fr, Licence Ouverte 2.0.
       About 9,800 stations; each price carries its own update time. Motorway stations are flagged.
  ESP  Geoportal Gasolineras (MITECO) REST service. About 11,500 stations, one timestamp per file.
       Reuse allowed with the source cited (MITECO open data notice).
  ITA  Osservatorio prezzi carburanti (MIMIT), daily registry and 8 a.m. prices, IODL 2.0.
       About 22,000 stations; self-service prices are used where a station has them.
  MEX  Comisión Nacional de Energía (formerly CRE): prices registered by permit holders, published daily
       at 18:00 Mexico City time, plus the station list with coordinates. About 13,800 stations. The page
       names no licence; Mexico's federal open-data terms (Libre Uso MX, compatible with CC BY) apply to
       the dataset as catalogued on datos.gob.mx. Prices are pesos per litre, kept in pesos; the file
       carries the ECB euro rate so the globe can show both. The list has no per-station dates.

One file per country, fuel/stations/<ISO3>.json, plus a small index fuel_stations.json the globe
reads first. Each station is a compact array; prices are per litre with tax, as at the pump, in the
country's currency (`currency`, euros unless stated).

Three price columns line up with the globe's fuel choices: petrol, diesel, LPG. The petrol column
is the country's most common 95-octane petrol (France: SP95-E10, Spain: Gasolina 95 E5, Italy:
Benzina), so stations are compared like for like. Other fuels a station sells go into `extra`.

Prices older than MAX_AGE_DAYS are dropped rather than shown as current. Percentile colouring on
the globe happens per zone: the Canary Islands, Ceuta and Melilla pay different taxes from
mainland Spain, so each is compared with itself.

A country that fails keeps its previous file; the index is rebuilt from whatever is on disk.

Run against saved files:  python scripts/fetch_fuel_stations.py --dir path/to/samples
"""
import csv, datetime, gzip, io, json, math, pathlib, statistics, sys, time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
import requests
import feed_health as health

UA = {'User-Agent': 'earth-observatory-feed (personal, non-commercial)',
      'Accept': 'application/json, text/csv, */*', 'Accept-Language': 'en;q=0.9, es;q=0.8, fr;q=0.8, it;q=0.8'}
REFRESH_MINUTES = {'FRA': 50, 'ESP': 50, 'ITA': 360, 'MEX': 360}
MAX_AGE_DAYS = 30
RANGE = (0.3, 4.5)          # euros per litre; outside is rejected
SLOT_RANGE = {'PETROL': (0.8, 4.0), 'DIESEL': (0.8, 4.0), 'LPG': (0.3, 1.8)}   # tighter, per column
MIN_STATIONS = {'FRA': 5000, 'ESP': 6000, 'ITA': 10000, 'MEX': 8000}
ECB_DAILY = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'
SLOTS = ('PETROL', 'DIESEL', 'LPG')
# flags: bit 0 motorway, bit 1 attended service only (no self-service price), bit 2 open 24 hours,
# bits 3-4 zone index (see `zones`)
MOTORWAY, SERVED, H24 = 1, 2, 4

COUNTRIES = {
    'FRA': {'url': 'https://www.data.gouv.fr/api/1/datasets/r/b0561905-7b5e-4f38-be50-df05708acb80',
            'name': "Prix des carburants en France, flux instantané v2 (Ministère de l'Économie, data.gouv.fr)",
            'licence': 'Licence Ouverte / Open Licence 2.0',
            'attribution': "Source: Ministère de l'Économie, prix-carburants.gouv.fr, via data.gouv.fr (Licence Ouverte 2.0).",
            'page': 'https://www.data.gouv.fr/fr/datasets/prix-des-carburants-en-france-flux-instantane-v2-amelioree/',
            'fuels': {'PETROL': 'SP95-E10', 'DIESEL': 'Gazole', 'LPG': 'GPLc'},
            'zones': ['Metropolitan France'], 'level': 4, 'cadence': 'updated every 10 minutes at source'},
    'ESP': {'url': 'https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/',
            'name': 'Precios de carburantes en las gasolineras españolas (MITECO, Geoportal Gasolineras)',
            'licence': 'MITECO open data reuse conditions (attribution required)',
            'attribution': 'Source of data: Ministry for Ecological Transition and the Demographic Challenge (Geoportal Gasolineras).',
            'page': 'https://geoportalgasolineras.es/',
            'fuels': {'PETROL': 'Gasolina 95 E5', 'DIESEL': 'Gasóleo A', 'LPG': 'GLP'},
            'zones': ['Mainland Spain and the Balearic Islands', 'Canary Islands', 'Ceuta and Melilla'],
            'level': 4, 'cadence': 'updated several times a day at source'},
    'ITA': {'url': ('https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv',
                    'https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv'),
            'name': 'Osservatorio prezzi carburanti, prezzi praticati e anagrafica degli impianti (MIMIT)',
            'licence': 'IODL 2.0',
            'attribution': 'Fonte: Ministero delle Imprese e del Made in Italy, Osservatorio prezzi carburanti (IODL 2.0).',
            'page': 'https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-prezzi-praticati-e-anagrafica-degli-impianti',
            'fuels': {'PETROL': 'Benzina (self-service)', 'DIESEL': 'Gasolio (self-service)', 'LPG': 'GPL'},
            'zones': ['Italy'], 'level': 3, 'cadence': 'daily, prices in force at 8 a.m.'},
    'MEX': {'url': ('https://publicacionexterna.azurewebsites.net/publicaciones/places',
                    'https://publicacionexterna.azurewebsites.net/publicaciones/prices'),
            'name': 'Precios de gasolinas y diésel reportados por los permisionarios (Comisión Nacional de Energía, CNE)',
            'licence': 'Libre Uso MX (Mexican federal open-data terms; the source page itself names no licence)',
            'attribution': ('Fuente: Comisión Nacional de Energía (CNE), Precios de gasolinas y diésel reportados por los '
                            'permisionarios, https://www.cne.gob.mx/ConsultaPrecios/GasolinasyDiesel/GasolinasyDiesel.html, '
                            'consultado {date}.'),
            'page': 'https://www.cne.gob.mx/ConsultaPrecios/GasolinasyDiesel/GasolinasyDiesel.html',
            'fuels': {'PETROL': 'Gasolina regular (87 AKI)', 'DIESEL': 'Diésel'},
            'zones': ['Mexico'], 'level': 3, 'cadence': 'daily, published at 18:00 Mexico City time',
            'currency': 'MXN', 'slotRange': {'PETROL': (12.0, 45.0), 'DIESEL': (12.0, 45.0), 'LPG': (5.0, 30.0)},
            'note': ('Stations in the northern and southern border regions pay VAT at 8% instead of 16% (a federal stimulus '
                     'extended to 31 December 2026), so many rank cheaper than the rest of Mexico. The CNE list gives each '
                     "station's registered price, not the date it last changed.")},
}
BOUNDS = {'FRA': (-5.3, 41.2, 9.7, 51.2), 'ESP': (-18.5, 27.5, 4.5, 44.0), 'ITA': (6.5, 35.4, 18.6, 47.2),
          'MEX': (-118.5, 14.4, -86.6, 32.8)}


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=180)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last = e
            time.sleep(5 * (i + 1))
    raise last


def price(v):
    if v is None: return None
    try: p = float(str(v).strip().replace(',', '.'))
    except ValueError: return None
    return round(p, 3) if math.isfinite(p) and RANGE[0] <= p <= RANGE[1] else None


def coord(v):
    try: x = float(str(v).strip().replace(',', '.'))
    except ValueError: return None
    return x if math.isfinite(x) else None


def inside(iso, lon, lat):
    b = BOUNDS[iso]
    return lon is not None and lat is not None and b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


class Brands:
    def __init__(self): self.names, self.index = [], {}
    def __call__(self, name):
        name = (name or '').strip()
        if not name: return -1
        if name not in self.index:
            self.index[name] = len(self.names); self.names.append(name)
        return self.index[name]


# ---------------- France ----------------
FR_KEYS = {'e10': ('PETROL', None), 'gazole': ('DIESEL', None), 'gplc': ('LPG', None),
           'sp95': (None, 'SP95'), 'sp98': (None, 'SP98'), 'e85': (None, 'E85')}


def fr_time(v):
    """The feed's *_maj fields carry '+00:00', but the clock digits are French local time: a file
    downloaded at 04:35 UTC holds updates stamped 05:56. Read the digits as Europe/Paris."""
    if not v or v == 'None': return None
    try:
        t = datetime.datetime.fromisoformat(str(v).replace(' ', 'T')[:19])
    except ValueError:
        return None
    return t.replace(tzinfo=ZoneInfo('Europe/Paris'))


def parse_fr(blob, now):
    if blob[:2] == b'\x1f\x8b': blob = gzip.decompress(blob)
    rows = json.loads(blob)
    if not isinstance(rows, list): raise ValueError('France: expected a list of stations')
    extras = ['SP95', 'SP98', 'E85']
    out, newest = [], None
    for s in rows:
        lat, lon = coord(s.get('latitude')), coord(s.get('longitude'))
        if lat is not None and lon is not None and abs(lat) > 1000: lat, lon = lat / 1e5, lon / 1e5
        if not inside('FRA', lon, lat): continue
        slot, extra, upd = {}, [], None
        for key, (sl, ex) in FR_KEYS.items():
            p, t = price(s.get(key + '_prix')), fr_time(s.get(key + '_maj'))
            if p is None or t is None or (now - t).days > MAX_AGE_DAYS: continue
            upd = max(upd or t, t)
            if sl: slot[sl] = p
            else: extra.append([extras.index(ex), p])
        if not slot and not extra: continue
        flags = (MOTORWAY if s.get('pop') == 'A' else 0) | (H24 if str(s.get('horaires_automate_24_24')).lower() in ('oui', '1', 'true') else 0)
        out.append({'lon': lon, 'lat': lat, 'brand': '', 'flags': flags, 'slot': slot, 'extra': extra,
                    'updated': upd, 'id': str(s.get('id')), 'town': (s.get('ville') or '').strip().title(),
                    'address': (s.get('adresse') or '').strip()})
        newest = max(newest or upd, upd)
    return out, extras, newest


# ---------------- Spain ----------------
ES_SLOT = {'Precio Gasolina 95 E5': 'PETROL', 'Precio Gasoleo A': 'DIESEL', 'Precio Gases licuados del petróleo': 'LPG'}
ES_EXTRA = ['Gasolina 98 E5', 'Gasolina 95 E10', 'Gasóleo Premium', 'Gasolina 95 E5 Premium', 'Diésel renovable', 'GNC']
ES_EXTRA_KEYS = ['Precio Gasolina 98 E5', 'Precio Gasolina 95 E10', 'Precio Gasoleo Premium',
                 'Precio Gasolina 95 E5 Premium', 'Precio Diésel Renovable', 'Precio Gas Natural Comprimido']


def es_zone(prov):
    p = (prov or '').upper()
    if 'PALMAS' in p or 'TENERIFE' in p: return 1
    if 'CEUTA' in p or 'MELILLA' in p: return 2
    return 0


def parse_es(blob, now):
    j = json.loads(blob)
    rows = j.get('ListaEESSPrecio')
    if not isinstance(rows, list): raise ValueError('Spain: no ListaEESSPrecio')
    stamp = datetime.datetime.strptime(j['Fecha'].strip(), '%d/%m/%Y %H:%M:%S').replace(tzinfo=ZoneInfo('Europe/Madrid'))
    if (now - stamp).days > 3: raise ValueError('Spain: file is older than three days')
    out = []
    for s in rows:
        lat, lon = coord(s.get('Latitud')), coord(s.get('Longitud (WGS84)'))
        if not inside('ESP', lon, lat): continue
        slot = {sl: p for k, sl in ES_SLOT.items() if (p := price(s.get(k))) is not None}
        extra = [[i, p] for i, k in enumerate(ES_EXTRA_KEYS) if (p := price(s.get(k))) is not None][:4]
        if not slot and not extra: continue
        flags = (H24 if '24H' in (s.get('Horario') or '').upper() else 0) | (es_zone(s.get('Provincia')) << 3)
        out.append({'lon': lon, 'lat': lat, 'brand': s.get('Rótulo'), 'flags': flags, 'slot': slot, 'extra': extra,
                    'updated': stamp, 'id': str(s.get('IDEESS')), 'town': (s.get('Localidad') or '').strip().title(),
                    'address': (s.get('Dirección') or '').strip().title(), 'hours': (s.get('Horario') or '').strip()})
    return out, ES_EXTRA, stamp


# ---------------- Italy ----------------
IT_SLOT = {'Benzina': 'PETROL', 'Gasolio': 'DIESEL', 'GPL': 'LPG'}
IT_EXTRA = ['Metano', 'Blue Diesel', 'HVO', 'Benzina speciale']


def it_extra(desc):
    d = desc.lower()
    if d == 'metano': return 0
    if 'diesel' in d and 'blue' in d: return 1
    if 'hvo' in d: return 2
    if d in ('blue super', 'hi-q benzina', 'supreme benzina', 'benzina wr 100', 'benzina plus 98', 'v-power'): return 3
    return None


def parse_it(registry, prices, now):
    tz = ZoneInfo('Europe/Rome')
    reg = registry.decode('utf-8-sig', 'replace').splitlines()
    if not reg[0].startswith('Estrazione del') or not reg[1].startswith('idImpianto|'):
        raise ValueError('Italy: registry header changed')
    stations = {}
    for line in reg[2:]:
        r = line.split('|')
        if len(r) < 10: continue
        lat, lon = coord(r[-2]), coord(r[-1])
        if not inside('ITA', lon, lat): continue
        # A few names contain '|' (for example "STOIL SIMPLE | gestori.prezzibenzina.it"); count the
        # address, town, province and coordinates from the end, and give the rest to the name.
        name = '|'.join(r[4:-5]).split(' | ')[0].strip()
        stations[r[0]] = {'lon': lon, 'lat': lat, 'brand': r[2], 'motorway': r[3] == 'Autostradale',
                          'name': name, 'address': r[-5].strip(), 'town': r[-4].strip().title()}
    pr = prices.decode('utf-8-sig', 'replace').splitlines()
    if not pr[1].startswith('idImpianto|descCarburante|prezzo|isSelf|dtComu'):
        raise ValueError('Italy: price header changed')
    acc = {}
    for line in pr[2:]:
        r = line.split('|')
        if len(r) < 5 or r[0] not in stations: continue
        p = price(r[2])
        try: t = datetime.datetime.strptime(r[4].strip(), '%d/%m/%Y %H:%M:%S').replace(tzinfo=tz)
        except ValueError: continue
        if p is None or (now - t).days > MAX_AGE_DAYS: continue
        a = acc.setdefault(r[0], {'self': {}, 'served': {}, 'extra': {}, 'updated': None})
        a['updated'] = max(a['updated'] or t, t)
        sl = IT_SLOT.get(r[1])
        if sl: a['self' if r[3] == '1' else 'served'][sl] = p
        else:
            ex = it_extra(r[1])
            if ex is not None and (ex not in a['extra'] or r[3] == '1'): a['extra'][ex] = p
    out, newest = [], None
    for sid, a in acc.items():
        s = stations[sid]
        slot = dict(a['served']); slot.update(a['self'])           # self-service wins where both exist
        served_only = bool(slot) and not any(k in a['self'] for k in ('PETROL', 'DIESEL'))
        if 'LPG' in a['served'] and 'LPG' not in a['self']: slot['LPG'] = a['served']['LPG']   # LPG is nearly always attended
        flags = (MOTORWAY if s['motorway'] else 0) | (SERVED if served_only else 0)
        out.append({'lon': s['lon'], 'lat': s['lat'], 'brand': s['brand'], 'flags': flags, 'slot': slot,
                    'extra': [[k, v] for k, v in sorted(a['extra'].items())], 'updated': a['updated'], 'id': sid,
                    'town': s['town'], 'address': s['address'], 'name': s['name']})
        newest = max(newest or a['updated'], a['updated'])
    return out, IT_EXTRA, newest


# ---------------- Mexico ----------------
MX_EXTRA = ['Gasolina premium (91 AKI)']
MX_TZ = ZoneInfo('America/Mexico_City')


def mx_published(now):
    """The CNE files carry no timestamp; the list is refreshed daily at 18:00 Mexico City time."""
    local = now.astimezone(MX_TZ)
    t = local.replace(hour=18, minute=0, second=0, microsecond=0)
    return t if local >= t else t - datetime.timedelta(days=1)


def parse_mx(places_blob, prices_blob, now):
    places = {}
    for p in ET.fromstring(places_blob).iter('place'):
        loc = p.find('location')
        if loc is None: continue
        lon, lat = coord(loc.findtext('x')), coord(loc.findtext('y'))
        if not inside('MEX', lon, lat): continue
        places[p.get('place_id')] = {'lon': lon, 'lat': lat, 'name': (p.findtext('name') or '').strip(),
                                     'permit': (p.findtext('cre_id') or '').strip()}
    if len(places) < 1000 and len(places_blob) > 1_000_000: raise ValueError('Mexico: station list changed shape')
    stamp = mx_published(now)
    # A station can appear several times, one product per entry; gather its products first.
    got = {}
    for p in ET.fromstring(prices_blob).iter('place'):
        pid = p.get('place_id')
        if pid not in places: continue
        for g in p.findall('gas_price'):
            v = coord(g.text)
            if v is not None and v > 0: got.setdefault(pid, {})[(g.get('type') or '').lower()] = round(v, 2)
    out = []
    for pid, prod in got.items():
        s = places[pid]
        slot = {sl: prod[k] for k, sl in (('regular', 'PETROL'), ('diesel', 'DIESEL')) if k in prod}
        extra = [[0, prod['premium']]] if 'premium' in prod else []
        if not slot and not extra: continue
        out.append({'lon': s['lon'], 'lat': s['lat'], 'brand': s['name'], 'flags': 0, 'slot': slot, 'extra': extra,
                    'updated': None, 'id': s['permit'] or pid, 'town': '', 'address': ''})
    return out, MX_EXTRA, stamp


def eur_rate(ccy, files=None):
    """Euros per unit of `ccy` from the ECB's daily reference rates -> (rate, date) or (None, None)."""
    try:
        root = ET.fromstring((files or {}).get('ecb') or get(ECB_DAILY, tries=2))
        for day in root.iter():
            if not day.get('time'): continue
            for c in day:
                if c.get('currency') == ccy:
                    return round(1 / float(c.get('rate')), 8), day.get('time')
    except Exception as e:
        print('fuel_stations: ECB rate unavailable:', type(e).__name__, str(e)[:120])
    return None, None


# ---------------- output ----------------

def quantiles(vals):
    v = sorted(vals)
    if not v: return None
    q = lambda f: v[min(len(v) - 1, int(round(f * (len(v) - 1))))]
    return {'n': len(v), 'min': v[0], 'p10': q(.1), 'median': round(statistics.median(v), 3), 'p90': q(.9), 'max': v[-1]}


def build(iso, stations, extras, newest, fetched=None, fx=(None, None)):
    meta = COUNTRIES[iso]
    slot_range = meta.get('slotRange', SLOT_RANGE)
    if len(stations) < MIN_STATIONS[iso]:
        raise ValueError(f'{iso}: only {len(stations)} stations with a current price; refusing to publish')
    brands = Brands()
    items = []
    rejected = 0
    for s in sorted(stations, key=lambda x: (x['lat'], x['lon'])):
        row = [round(s['lon'], 5), round(s['lat'], 5), brands(s.get('brand')), s['flags']]
        for k in SLOTS:
            p = s['slot'].get(k)
            if p is not None and not (slot_range[k][0] <= p <= slot_range[k][1]):
                p = None; rejected += 1
            row.append(p)
        row += [int(s['updated'].timestamp()) if s['updated'] else None, s['id'], s['town'], s['address'],
                s['extra'] or None]
        items.append(row)
    stats = {}
    for i, k in enumerate(SLOTS):
        stats[k] = {}
        for z, name in enumerate(meta['zones']):
            q = quantiles([r[4 + i] for r in items if r[4 + i] is not None and (r[3] >> 3) == z])
            if q: stats[k][str(z)] = q
    lon = [r[0] for r in items]; lat = [r[1] for r in items]
    fetched = fetched or health.now()
    extra = {'currency': meta.get('currency', 'EUR')}
    if extra['currency'] != 'EUR': extra.update(eurPerUnit=fx[0], fxDate=fx[1])
    if meta.get('note'): extra['note'] = meta['note']
    return dict({
        'country': iso, 'source': meta['name'], 'licence': meta['licence'],
        'attribution': meta['attribution'].replace('{date}', fetched[:10]),
        'url': meta['page'], 'level': meta['level'], 'cadence': meta['cadence'],
        'validTime': newest.astimezone(datetime.UTC).isoformat(timespec='seconds') if newest else None,
        'fuels': meta['fuels'], 'extraFuels': extras, 'zones': meta['zones'], 'brands': brands.names,
        'fields': ['lon', 'lat', 'brand', 'flags', 'petrol', 'diesel', 'lpg', 'updated', 'id', 'town', 'address', 'extra'],
        'flagBits': {'motorway': MOTORWAY, 'servedOnly': SERVED, 'open24h': H24, 'zoneShift': 3},
        'maxAgeDays': MAX_AGE_DAYS, 'stats': stats, 'bbox': [min(lon), min(lat), max(lon), max(lat)], 'rejected': rejected,
        'items': items, 'fetched': fetched,
    }, **extra)


def collect(iso, now, files=None):
    f = files or {}
    if iso == 'FRA': return parse_fr(f.get('FRA') or get(COUNTRIES['FRA']['url']), now)
    if iso == 'ESP': return parse_es(f.get('ESP') or get(COUNTRIES['ESP']['url']), now)
    if iso == 'ITA':
        reg, pr = f.get('ITA') or (get(COUNTRIES['ITA']['url'][0]), get(COUNTRIES['ITA']['url'][1]))
        return parse_it(reg, pr, now)
    if iso == 'MEX':
        places, prices = f.get('MEX') or (get(COUNTRIES['MEX']['url'][0]), get(COUNTRIES['MEX']['url'][1]))
        return parse_mx(places, prices, now)
    raise KeyError(iso)


def fx_for(iso, files=None):
    """Today's ECB rate for a non-euro country, or the rate its previous file carried."""
    ccy = COUNTRIES[iso].get('currency', 'EUR')
    if ccy == 'EUR': return None, None
    rate, day = eur_rate(ccy, files)
    if rate: return rate, day
    try:
        old = json.loads((health.OUT / 'fuel' / 'stations' / f'{iso}.json').read_text(encoding='utf-8'))
        return old.get('eurPerUnit'), old.get('fxDate')
    except Exception:
        return None, None


def due(iso):
    path = health.OUT / 'fuel' / 'stations' / f'{iso}.json'
    try:
        got = datetime.datetime.fromisoformat(json.loads(path.read_text(encoding='utf-8'))['fetched'])
    except Exception:
        return True
    return (datetime.datetime.now(datetime.UTC) - got).total_seconds() > REFRESH_MINUTES[iso] * 60


def index():
    countries, newest = {}, None
    for iso in COUNTRIES:
        path = health.OUT / 'fuel' / 'stations' / f'{iso}.json'
        if not path.exists(): continue
        j = json.loads(path.read_text(encoding='utf-8'))
        countries[iso] = {k: j[k] for k in ('source', 'licence', 'attribution', 'url', 'level', 'cadence', 'validTime',
                                             'fuels', 'zones', 'stats', 'bbox', 'fetched', 'maxAgeDays')}
        countries[iso].update({k: j[k] for k in ('currency', 'eurPerUnit', 'fxDate', 'note') if j.get(k) is not None})
        countries[iso].update(file=f'fuel/stations/{iso}.json', count=len(j['items']), bytes=path.stat().st_size)
        newest = max(newest or j['validTime'], j['validTime'])
    return {'items': [[iso, c['count'], c['validTime']] for iso, c in countries.items()], 'countries': countries,
            'validTime': newest, 'unit': 'per litre, in each country\'s `currency`'}


def main(files=None, now=None):
    now = now or datetime.datetime.now(datetime.UTC)
    failed, done = [], []
    for iso in COUNTRIES:
        if files is None and not due(iso): continue
        if files is not None and iso not in files: continue
        try:
            stations, extras, newest = collect(iso, now, files)
            health.atomic_json(health.OUT / 'fuel' / 'stations' / f'{iso}.json',
                               build(iso, stations, extras, newest, fx=fx_for(iso, files)))
            done.append(f'{iso} {len(stations)}')
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            failed.append(f'{iso} ({"HTTP " + str(status) if status else type(e).__name__})')
            print('fuel_stations:', iso, 'failed:', type(e).__name__, str(e)[:200])
    payload = index()
    if not payload['countries']:
        raise ValueError('No station feed succeeded and none is cached')
    note = ('Pump prices with tax at individual stations, per litre in euros (Mexico: pesos). Prices older than '
            f'{MAX_AGE_DAYS} days are left out where the source dates them.')
    if failed: note += ' Kept previous data for: ' + ', '.join(failed) + '.'
    health.publish('fuel_stations', payload, 'Government fuel price feeds: France, Spain, Italy, Mexico', 'reported', note)
    print('fuel_stations: updated', done or 'none', '| failed', failed or 'none')


def files_from_dir(d):
    d = pathlib.Path(d)
    gz = lambda n: gzip.decompress((d / n).read_bytes())
    out = {'FRA': gz('fr_instant_json.gz'), 'ESP': gz('es_stations.json.gz'),
           'ITA': (gz('it_anagrafica.csv.gz'), gz('it_prezzo_alle_8.csv.gz'))}
    if (d / 'mx_places.xml.gz').exists(): out['MEX'] = (gz('mx_places.xml.gz'), gz('mx_prices.xml.gz'))
    if (d / 'ecb_daily.xml').exists(): out['ecb'] = (d / 'ecb_daily.xml').read_bytes()
    return out


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '--dir':
        samples = files_from_dir(sys.argv[2])
        when = datetime.datetime.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else None
        health.run('fuel_stations', lambda: main(samples, when))
    else:
        health.run('fuel_stations', main)
