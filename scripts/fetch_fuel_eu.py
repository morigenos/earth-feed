"""EU Weekly Oil Bulletin: national consumer prices of Euro-super 95, diesel and LPG.

The European Commission publishes one workbook holding every weekly bulletin since
January 2005, with and without taxes, already converted to euros. This collector
rebuilds the whole history from that workbook on each run instead of keeping its
own archive: re-downloading is idempotent, so nothing is lost if gh-pages is ever
rebuilt from scratch.

Licence: "Reproduction is authorised provided the source is acknowledged."
(c) European Commission. The page shows that attribution.

Bulletins are weekly (data as of Monday, published later in the week), so the
workbook is downloaded at most every REFRESH_HOURS even though the feed runs every
30 minutes.

Run locally against a saved workbook:  python scripts/fetch_fuel_eu.py --file path.xlsx
"""
import datetime, io, json, math, re, sys
import requests
import feed_health as health

PAGE = 'https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en'
FALLBACK_URL = ('https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en'
                '?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx')
UA = {'User-Agent': 'earth-observatory-feed (personal, non-commercial)'}
REFRESH_HOURS = 12
SOURCE = 'European Commission, Weekly Oil Bulletin (prices history since 2005)'
SOURCE_ID = 'eu_wob'
ATTRIBUTION = 'Source: European Commission, Weekly Oil Bulletin. Reproduction authorised with acknowledgement.'
# A country whose newest value is older than this, relative to the newest bulletin,
# is history only (for example the United Kingdom after December 2020).
STALE_DAYS = 35
MIN_CURRENT_COUNTRIES = 20

# Bulletin column code -> ISO 3166-1 alpha-3. The workbook uses GR for Greece and UK
# for the United Kingdom; EL and GB are accepted in case the Commission switches.
ISO3 = {'AT': 'AUT', 'BE': 'BEL', 'BG': 'BGR', 'CY': 'CYP', 'CZ': 'CZE', 'DE': 'DEU', 'DK': 'DNK',
        'EE': 'EST', 'ES': 'ESP', 'FI': 'FIN', 'FR': 'FRA', 'GR': 'GRC', 'EL': 'GRC', 'HR': 'HRV',
        'HU': 'HUN', 'IE': 'IRL', 'IT': 'ITA', 'LT': 'LTU', 'LU': 'LUX', 'LV': 'LVA', 'MT': 'MLT',
        'NL': 'NLD', 'PL': 'POL', 'PT': 'PRT', 'RO': 'ROU', 'SE': 'SWE', 'SI': 'SVN', 'SK': 'SVK',
        'UK': 'GBR', 'GB': 'GBR'}
AGGREGATES = {'EU': 'EU', 'EUR': 'EUR'}   # EU weighted average and euro-area average
# Currencies of members still outside the euro, used only for the local-price line.
LOCAL_CCY = {'BG': 'BGN', 'CZ': 'CZK', 'DK': 'DKK', 'HU': 'HUF', 'PL': 'PLN', 'RO': 'RON',
             'SE': 'SEK', 'HR': 'HRK', 'UK': 'GBP', 'GB': 'GBP'}
FUELS = {'euro95': 'GASOLINE_95', 'diesel': 'DIESEL', 'LPG': 'LPG'}
SHEETS = (('Prices with taxes', 'price_with_tax', 'tax'), ('Prices wo taxes', 'price_wo_tax', 'net'))
# Plausible range in euros per 1,000 litres; anything outside is rejected, not clipped.
RANGE = {'tax': (300.0, 4500.0), 'net': (100.0, 3500.0)}


def find_history_url(html):
    """The Commission replaces document links when it re-uploads; look for the
    history workbook by its file name and fall back to the last known link."""
    for href in re.findall(r'href="([^"]+)"', html or ''):
        if 'Prices_History' in href:
            return requests.compat.urljoin(PAGE, href.replace('&amp;', '&'))
    return FALLBACK_URL


def download():
    url = FALLBACK_URL
    try:
        page = requests.get(PAGE, headers=UA, timeout=60)
        page.raise_for_status()
        url = find_history_url(page.text)
    except requests.RequestException:
        pass
    r = requests.get(url, headers=UA, timeout=180)
    r.raise_for_status()
    if not r.content.startswith(b'PK'):
        raise ValueError('History download is not an XLSX workbook')
    return r.content


def _day(v):
    if isinstance(v, datetime.datetime): return v.date()
    if isinstance(v, datetime.date): return v
    if isinstance(v, (int, float)) and 30000 < v < 80000:     # Excel serial date
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(v))
    return None


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def parse(blob):
    """Return {'dates': [date, ...] ascending, 'series': {code: {fuel: {'tax': [...], 'net': [...]}}},
    'rates': {code: latest EUR-per-local-unit}, 'rejected': n}. Values are EUR per 1,000 L."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(blob), read_only=True, data_only=True)
    series, rates, rejected, dates = {}, {}, 0, None
    for sheet, tag, kind in SHEETS:
        if sheet not in wb.sheetnames:
            raise ValueError(f'Workbook has no sheet {sheet!r}')
        rows = list(wb[sheet].iter_rows(values_only=True))
        header = rows[0]
        cols, rate_cols = {}, {}
        for i, h in enumerate(header):
            m = re.fullmatch(r'([A-Z]{2,3})_' + tag + r'_(euro95|diesel|LPG)', str(h or '').strip())
            if m: cols[(m.group(1), FUELS[m.group(2)])] = i
            m = re.fullmatch(r'([A-Z]{2})_exchange_rate', str(h or '').strip())
            if m: rate_cols[m.group(1)] = i
        if len({c for c, _ in cols}) < 20:
            raise ValueError(f'Unexpected header in {sheet!r}: found {len(cols)} price columns')
        data = [(d, r) for r in rows[1:] if (d := _day(r[0] if r else None))]
        data.sort(key=lambda x: x[0])
        these = [d for d, _ in data]
        if len(these) != len(set(these)):
            raise ValueError(f'Duplicate bulletin dates in {sheet!r}')
        if dates is None: dates = these
        elif these != dates: raise ValueError('Sheets disagree on bulletin dates')
        lo, hi = RANGE[kind]
        for (code, fuel), i in cols.items():
            vals = []
            for _, r in data:
                v = _num(r[i] if i < len(r) else None)
                if v is not None and not (lo <= v <= hi):
                    rejected += 1; v = None
                vals.append(v)
            series.setdefault(code, {}).setdefault(fuel, {})[kind] = vals
        if kind == 'tax':
            for code, i in rate_cols.items():
                for _, r in reversed(data):
                    v = _num(r[i] if i < len(r) else None)
                    if v and v > 0: rates[code] = v; break
    if not dates:
        raise ValueError('No bulletin dates found')
    if dates[-1] > datetime.date.today() + datetime.timedelta(days=7):
        raise ValueError('Newest bulletin date is in the future')
    return {'dates': dates, 'series': series, 'rates': rates, 'rejected': rejected}


def litre(v):
    return None if v is None else round(v / 1000.0, 3)


def latest(vals):
    for i in range(len(vals) - 1, -1, -1):
        if vals[i] is not None: return i
    return None


def build(parsed):
    """Turn parsed workbook data into the fuel.json payload and per-area history files."""
    dates, series, rates = parsed['dates'], parsed['series'], parsed['rates']
    newest = dates[-1]
    items, stale, unknown, history, ref = [], {}, [], {}, {}
    for code, fuels in sorted(series.items()):
        area = ISO3.get(code) or AGGREGATES.get(code)
        if not area:
            unknown.append(code); continue
        hist = {'dates': [int(d.strftime('%Y%m%d')) for d in dates], 'series': {}}
        for fuel, kinds in fuels.items():
            tax, net = kinds.get('tax', [None] * len(dates)), kinds.get('net', [None] * len(dates))
            if not any(v is not None for v in tax): continue
            hist['series'][fuel] = {'tax': [litre(v) for v in tax], 'net': [litre(v) for v in net]}
            i = latest(tax)
            age = (newest - dates[i]).days
            if code in AGGREGATES:
                ref.setdefault(code, {})[fuel] = [litre(tax[i]), litre(net[i]), dates[i].isoformat()]
                continue
            if age > STALE_DAYS:
                stale[area] = max(stale.get(area, ''), dates[i].isoformat()); continue
            eur = litre(tax[i]); ex = litre(net[i]) if net[i] is not None else None
            ccy, local = 'EUR', eur
            rate = rates.get(code)
            if code in LOCAL_CCY and rate and abs(rate - 1) > 1e-9:
                ccy, local = LOCAL_CCY[code], round(tax[i] / rate / 1000.0, 2)
            items.append([area, fuel, eur, ex, dates[i].isoformat(), SOURCE_ID, 1, ccy, local])
        if hist['series']:
            history[area] = hist
    current = {a for a, *_ in items}
    if len(current) < MIN_CURRENT_COUNTRIES:
        raise ValueError(f'Only {len(current)} countries have a current price; refusing to publish')
    payload = {
        'items': items,
        'validTime': newest.isoformat(),
        'asOf': {SOURCE_ID: newest.isoformat()},
        'fuels': ['GASOLINE_95', 'DIESEL', 'LPG'],
        'unit': 'EUR/L',
        'ref': ref,
        'stale': [[a, d] for a, d in sorted(stale.items())],
        'history': 'fuel/history/{iso3}.json',
        'staleAfterDays': 21,
        'attribution': ATTRIBUTION,
        'coverage': 'EU member states, national weighted averages of the most frequently charged prices.',
    }
    return payload, history, unknown


def fresh_enough():
    path = health.OUT / 'fuel.json'
    try:
        got = datetime.datetime.fromisoformat(json.loads(path.read_text())['fetched'])
    except Exception:
        return False
    return (datetime.datetime.now(datetime.UTC) - got).total_seconds() < REFRESH_HOURS * 3600


def write(payload, history, rejected=0):
    folder = health.OUT / 'fuel' / 'history'
    for area, hist in history.items():
        health.atomic_json(folder / f'{area}.json', dict(hist, area=area, unit='EUR/L', source=SOURCE,
                                                         attribution=ATTRIBUTION))
    note = ('National averages from the weekly bulletin, in euros per litre. Prices with and without '
            'taxes as reported by each member state; individual stations differ.')
    if rejected:
        note += f' {rejected} implausible values were dropped.'
    health.publish('fuel', payload, SOURCE, 'reported', note)


def main(blob=None):
    if blob is None:
        if fresh_enough():
            health.record('fuel', 'ok', f'Bulletin data is younger than {REFRESH_HOURS} hours; not downloaded again')
            return
        blob = download()
    parsed = parse(blob)
    payload, history, unknown = build(parsed)
    write(payload, history, parsed['rejected'])
    print(f"fuel: bulletin {payload['validTime']}, {len({i[0] for i in payload['items']})} countries, "
          f"{len(history)} history files, {parsed['rejected']} rejected, unknown codes {unknown or 'none'}")


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--file':
        with open(sys.argv[2], 'rb') as f:
            data = f.read()
        health.run('fuel', lambda: main(data))
    else:
        health.run('fuel', main)
