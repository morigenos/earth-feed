"""National fuel prices outside the EU Weekly Oil Bulletin.

Five open official sources, each with history back to at least 2005:

  us_eia      United States   U.S. Energy Information Administration, weekly retail prices (USD/gal)
  uk_desnz    United Kingdom  Department for Energy Security and Net Zero, weekly road fuel prices
  ca_statcan  Canada          Statistics Canada table 18-10-0001-01, monthly average retail prices
                              (national figure for regular petrol only; 18 cities have regular,
                              premium and diesel)
  nz_mbie     New Zealand     MBIE weekly fuel price monitoring (with taxes and margins)
  my_mof      Malaysia        Ministry of Finance via data.gov.my, weekly fuel prices

Prices are converted to euros per litre with the European Central Bank's reference rate for
the observation date (the month's average for Canada's monthly figures), so they sit on the
same scale as the EU bulletin. The local price is kept too.

Grades are not forced into one: US and Canadian "regular" is 87 AKI (about 91 RON) and New
Zealand's regular is 91 RON. Each country's standard petrol is named in `standard` and every
item carries its grade label, so the globe can show one petrol map and say what it compares.

Below the national level (Stage 8): EIA's PADD regions and sub-regions, nine states and ten cities,
and Statistics Canada's 18 cities. They are areas named COUNTRY-PART (USA-PADD1A, USA-CA,
CAN-TORONTO) with the same item and history shapes, plus a `regions` block that says which
states or provinces each one covers, so the globe can colour states and provinces when zoomed in.

Every source is fetched and parsed on its own. A source that fails keeps its last good file
(data/fuel/national/<source>.json); the merged fuel_world.json is rebuilt from whatever is on
disk, so one broken site never empties the others.

Licences: EIA public domain; UK Open Government Licence v3.0; Statistics Canada Open Licence;
MBIE CC BY 4.0 NZ; data.gov.my CC BY 4.0; ECB reference rates reusable with the source cited.

Run against saved files:  python scripts/fetch_fuel_world.py --dir path/to/samples
"""
import calendar, csv, datetime, io, json, math, pathlib, re, sys, zipfile
import requests
import feed_health as health

UA = {'User-Agent': 'earth-observatory-feed (personal, non-commercial)'}
REFRESH_HOURS = 12
START = datetime.date(2005, 1, 1)
L_PER_GAL = 3.785411784
FX_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip'
CURRENCIES = ('USD', 'GBP', 'CAD', 'NZD', 'MYR')
EIA = 'https://www.eia.gov/dnav/pet/hist_xls/{code}w.xls'
EIA_SERIES = {   # all formulations first; conventional-only as a fallback with the same layout
    'GASOLINE_REGULAR': ('EMM_EPMR_PTE_NUS_DPG', 'EMM_EPMRU_PTE_NUS_DPG'),
    'GASOLINE_PREMIUM': ('EMM_EPMP_PTE_NUS_DPG', 'EMM_EPMPU_PTE_NUS_DPG'),
    'DIESEL': ('EMD_EPD2D_PTE_NUS_DPG',),
}
# Below the national level. Codes are EIA's area codes; states use ISO 3166-2 codes.
P1A = ['US-CT', 'US-ME', 'US-MA', 'US-NH', 'US-RI', 'US-VT']
P1B = ['US-DE', 'US-DC', 'US-MD', 'US-NJ', 'US-NY', 'US-PA']
P1C = ['US-FL', 'US-GA', 'US-NC', 'US-SC', 'US-VA', 'US-WV']
P2 = ['US-IL', 'US-IN', 'US-IA', 'US-KS', 'US-KY', 'US-MI', 'US-MN', 'US-MO', 'US-NE', 'US-ND', 'US-SD', 'US-OH',
      'US-OK', 'US-TN', 'US-WI']
P3 = ['US-AL', 'US-AR', 'US-LA', 'US-MS', 'US-NM', 'US-TX']
P4 = ['US-CO', 'US-ID', 'US-MT', 'US-UT', 'US-WY']
P5X = ['US-AK', 'US-AZ', 'US-HI', 'US-NV', 'US-OR', 'US-WA']
# (area key, EIA code, name, kind, states covered); kind decides precedence when colouring a state:
# state > subregion > region. Cities are listed in the panel only.
EIA_AREAS = [
    ('USA-PADD1', 'R10', 'East Coast (PADD 1)', 'region', P1A + P1B + P1C),
    ('USA-PADD1A', 'R1X', 'New England (PADD 1A)', 'subregion', P1A),
    ('USA-PADD1B', 'R1Y', 'Central Atlantic (PADD 1B)', 'subregion', P1B),
    ('USA-PADD1C', 'R1Z', 'Lower Atlantic (PADD 1C)', 'subregion', P1C),
    ('USA-PADD2', 'R20', 'Midwest (PADD 2)', 'region', P2),
    ('USA-PADD3', 'R30', 'Gulf Coast (PADD 3)', 'region', P3),
    ('USA-PADD4', 'R40', 'Rocky Mountain (PADD 4)', 'region', P4),
    ('USA-PADD5', 'R50', 'West Coast (PADD 5)', 'region', P5X + ['US-CA']),
    ('USA-PADD5X', 'R5XCA', 'West Coast except California', 'subregion', P5X),
    ('USA-CA', 'SCA', 'California', 'state', ['US-CA']),
    ('USA-CO', 'SCO', 'Colorado', 'state', ['US-CO']),
    ('USA-FL', 'SFL', 'Florida', 'state', ['US-FL']),
    ('USA-MA', 'SMA', 'Massachusetts', 'state', ['US-MA']),
    ('USA-MN', 'SMN', 'Minnesota', 'state', ['US-MN']),
    ('USA-NY', 'SNY', 'New York', 'state', ['US-NY']),
    ('USA-OH', 'SOH', 'Ohio', 'state', ['US-OH']),
    ('USA-TX', 'STX', 'Texas', 'state', ['US-TX']),
    ('USA-WA', 'SWA', 'Washington', 'state', ['US-WA']),
    ('USA-BOSTON', 'YBOS', 'Boston', 'city', ['US-MA']),
    ('USA-CHICAGO', 'YORD', 'Chicago', 'city', ['US-IL']),
    ('USA-CLEVELAND', 'YCLE', 'Cleveland', 'city', ['US-OH']),
    ('USA-DENVER', 'YDEN', 'Denver', 'city', ['US-CO']),
    ('USA-HOUSTON', 'Y44HO', 'Houston', 'city', ['US-TX']),
    ('USA-LOSANGELES', 'Y05LA', 'Los Angeles', 'city', ['US-CA']),
    ('USA-MIAMI', 'YMIA', 'Miami', 'city', ['US-FL']),
    ('USA-NYC', 'Y35NY', 'New York City', 'city', ['US-NY']),
    ('USA-SANFRANCISCO', 'Y05SF', 'San Francisco', 'city', ['US-CA']),
    ('USA-SEATTLE', 'Y48SE', 'Seattle', 'city', ['US-WA']),
]
EIA_AREA_CODE = {'GASOLINE_REGULAR': 'EMM_EPMR_PTE_{a}_DPG', 'GASOLINE_PREMIUM': 'EMM_EPMP_PTE_{a}_DPG',
                 'DIESEL': 'EMD_EPD2D_PTE_{a}_DPG'}
EIA_DIESEL = {'R10', 'R1X', 'R1Y', 'R1Z', 'R20', 'R30', 'R40', 'R50', 'R5XCA', 'SCA'}   # EIA publishes no other diesel areas
# Statistics Canada cities: GEO -> (area key, short name, province)
CA_CITIES = {
    "St. John's, Newfoundland and Labrador": ('CAN-STJOHNS', "St. John's", 'CA-NL'),
    'Charlottetown and Summerside, Prince Edward Island': ('CAN-CHARLOTTETOWN', 'Charlottetown and Summerside', 'CA-PE'),
    'Halifax, Nova Scotia': ('CAN-HALIFAX', 'Halifax', 'CA-NS'),
    'Saint John, New Brunswick': ('CAN-SAINTJOHN', 'Saint John', 'CA-NB'),
    'Québec, Quebec': ('CAN-QUEBEC', 'Québec', 'CA-QC'),
    'Montréal, Quebec': ('CAN-MONTREAL', 'Montréal', 'CA-QC'),
    'Ottawa-Gatineau, Ontario part, Ontario/Quebec': ('CAN-OTTAWA', 'Ottawa (Ontario part of Ottawa–Gatineau)', 'CA-ON'),
    'Toronto, Ontario': ('CAN-TORONTO', 'Toronto', 'CA-ON'),
    'Thunder Bay, Ontario': ('CAN-THUNDERBAY', 'Thunder Bay', 'CA-ON'),
    'Winnipeg, Manitoba': ('CAN-WINNIPEG', 'Winnipeg', 'CA-MB'),
    'Regina, Saskatchewan': ('CAN-REGINA', 'Regina', 'CA-SK'),
    'Saskatoon, Saskatchewan': ('CAN-SASKATOON', 'Saskatoon', 'CA-SK'),
    'Edmonton, Alberta': ('CAN-EDMONTON', 'Edmonton', 'CA-AB'),
    'Calgary, Alberta': ('CAN-CALGARY', 'Calgary', 'CA-AB'),
    'Vancouver, British Columbia': ('CAN-VANCOUVER', 'Vancouver', 'CA-BC'),
    'Victoria, British Columbia': ('CAN-VICTORIA', 'Victoria', 'CA-BC'),
    'Whitehorse, Yukon': ('CAN-WHITEHORSE', 'Whitehorse', 'CA-YT'),
    'Yellowknife, Northwest Territories': ('CAN-YELLOWKNIFE', 'Yellowknife', 'CA-NT'),
}
# How the globe colours states and provinces from these areas: the US uses the most specific area
# covering a state; Canada averages the cities in a province (unweighted), since it has no
# provincial series.
REGION_RULES = {'USA': {'fill': 'specific', 'order': ['region', 'subregion', 'state'],
                        'note': 'Each state takes its own EIA series where one exists (nine states), otherwise its '
                                'sub-region or region. Cities are listed, not painted.'},
                'CAN': {'fill': 'mean', 'order': ['city'],
                        'note': 'Statistics Canada reports 18 cities, not provinces. Each province shows the plain '
                                'average of its cities; Nunavut has none and keeps the national colour where there is one.'}}
UK_CONTENT = 'https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices'
CA_ZIP = 'https://www150.statcan.gc.ca/n1/tbl/csv/18100001-eng.zip'
NZ_CSV = 'https://www.mbie.govt.nz/assets/Data-Files/Energy/Weekly-fuel-price-monitoring/weekly-table.csv'
MY_API = 'https://api.data.gov.my/data-catalogue?id=fuelprice&limit=5000'

# Euros per litre outside this range are rejected, not clipped.
RANGE = (0.05, 6.0)

SOURCES = {
    'us_eia': {'name': 'U.S. Energy Information Administration, weekly retail gasoline and diesel prices',
               'areas': ['USA'] + [a[0] for a in EIA_AREAS], 'licence': 'Public domain (U.S. government work)',
               'attribution': 'Source: U.S. Energy Information Administration.',
               'url': 'https://www.eia.gov/petroleum/gasdiesel/', 'cadence': 'weekly, Monday prices',
               'maxAgeDays': 35, 'currency': 'USD', 'unit': 'gal', 'level': 1},
    'uk_desnz': {'name': 'Department for Energy Security and Net Zero, weekly road fuel prices',
                 'areas': ['GBR'], 'licence': 'Open Government Licence v3.0',
                 'attribution': 'Contains public sector information licensed under the Open Government Licence v3.0 (DESNZ weekly road fuel prices).',
                 'url': 'https://www.gov.uk/government/statistics/weekly-road-fuel-prices', 'cadence': 'weekly, Monday prices',
                 'maxAgeDays': 35, 'currency': 'GBP', 'unit': 'L', 'level': 1},
    'ca_statcan': {'name': 'Statistics Canada, table 18-10-0001-01, monthly average retail prices',
                   'areas': ['CAN'] + [c[0] for c in CA_CITIES.values()], 'licence': 'Statistics Canada Open Licence',
                   'attribution': 'Source: Statistics Canada, Table 18-10-0001-01.',
                   'url': 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000101', 'cadence': 'monthly averages, about seven weeks behind',
                   'maxAgeDays': 100, 'currency': 'CAD', 'unit': 'L', 'level': 1},
    'nz_mbie': {'name': 'Ministry of Business, Innovation and Employment, weekly fuel price monitoring',
                'areas': ['NZL'], 'licence': 'CC BY 4.0 NZ',
                'attribution': 'Source: MBIE weekly fuel price monitoring, licensed under CC BY 4.0.',
                'url': 'https://www.mbie.govt.nz/building-and-energy/energy-and-natural-resources/energy-statistics-and-modelling/energy-statistics/weekly-fuel-price-monitoring',
                'cadence': 'weekly, Friday prices', 'maxAgeDays': 35, 'currency': 'NZD', 'unit': 'L', 'level': 1},
    'my_mof': {'name': 'Ministry of Finance Malaysia, weekly fuel prices (data.gov.my)',
               'areas': ['MYS', 'MYS-E'], 'licence': 'CC BY 4.0',
               'attribution': 'Source: data.gov.my (Ministry of Finance Malaysia), CC BY 4.0.',
               'url': 'https://data.gov.my/data-catalogue/fuelprice', 'cadence': 'weekly, Thursday prices',
               'maxAgeDays': 35, 'currency': 'MYR', 'unit': 'L', 'level': 1},
}
# Each country's standard petrol; the EU default is Euro-super 95.
STANDARD = {'USA': 'GASOLINE_REGULAR', 'CAN': 'GASOLINE_REGULAR', 'NZL': 'GASOLINE_91'}
GRADES = {
    ('USA', 'GASOLINE_REGULAR'): 'Regular, 87 AKI (about 91 RON)',
    ('USA', 'GASOLINE_PREMIUM'): 'Premium, 91 AKI or more',
    ('USA', 'DIESEL'): 'No. 2 on-highway diesel',
    ('GBR', 'GASOLINE_95'): 'Unleaded, 95 RON',
    ('GBR', 'DIESEL'): 'Diesel',
    ('CAN', 'GASOLINE_REGULAR'): 'Regular, 87 AKI (about 91 RON), self-service',
    ('CAN', 'GASOLINE_PREMIUM'): 'Premium, self-service',
    ('CAN', 'DIESEL'): 'Diesel, self-service',
    ('NZL', 'GASOLINE_91'): 'Regular, 91 RON',
    ('NZL', 'GASOLINE_95'): 'Premium, 95 RON',
    ('NZL', 'DIESEL'): 'Diesel (road user charges are paid separately)',
    ('MYS', 'GASOLINE_95'): 'RON95, unsubsidised price',
    ('MYS', 'GASOLINE_97'): 'RON97',
    ('MYS', 'DIESEL'): 'Diesel, Peninsular Malaysia',
    ('MYS-E', 'DIESEL'): 'Diesel, Sabah, Sarawak and Labuan',
}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=120, **kw)
    r.raise_for_status()
    return r


def num(v):
    if v is None: return None
    if isinstance(v, str):
        v = v.strip().replace(',', '')
        if v in ('', '..', 'x', 'F', 'N/A', 'NA'): return None
        try: v = float(v)
        except ValueError: return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v): return None
    return float(v)


# ---------------- exchange rates ----------------

def parse_fx(blob):
    """ECB history zip (or its CSV) -> {currency: (sorted dates, rates)}; rates are units per euro."""
    if blob[:2] == b'PK':
        z = zipfile.ZipFile(io.BytesIO(blob))
        blob = z.read([n for n in z.namelist() if n.endswith('.csv')][0])
    rows = list(csv.reader(io.StringIO(blob.decode('utf-8-sig'))))
    head = [h.strip() for h in rows[0]]
    out = {c: [] for c in CURRENCIES if c in head}
    if len(out) < len(CURRENCIES):
        raise ValueError('ECB table is missing a currency: ' + ', '.join(sorted(set(CURRENCIES) - set(out))))
    for r in rows[1:]:
        if not r or not r[0].strip(): continue
        d = datetime.date.fromisoformat(r[0].strip())
        if d < START - datetime.timedelta(days=40): continue
        for c in out:
            v = num(r[head.index(c)])
            if v and v > 0: out[c].append((d, v))
    fx = {}
    for c, pairs in out.items():
        pairs.sort()
        fx[c] = ([d for d, _ in pairs], [v for _, v in pairs])
    if not fx['USD'][0]:
        raise ValueError('ECB table has no rates')
    return fx


def rate_on(fx, ccy, day):
    """Reference rate on `day`, or the last one published before it (weekends, holidays)."""
    dates, vals = fx[ccy]
    lo, hi, i = 0, len(dates) - 1, -1
    while lo <= hi:
        m = (lo + hi) // 2
        if dates[m] <= day: i, lo = m, m + 1
        else: hi = m - 1
    if i < 0 or (day - dates[i]).days > 10: return None
    return vals[i]


def rate_month(fx, ccy, day):
    """Average reference rate over the calendar month that starts at `day`."""
    dates, vals = fx[ccy]
    end = day.replace(day=calendar.monthrange(day.year, day.month)[1])
    sel = [v for d, v in zip(dates, vals) if day <= d <= end]
    return sum(sel) / len(sel) if sel else rate_on(fx, ccy, end)


# ---------------- parsers: each returns {area: {fuel: [(date, local, local_net_or_None)]}} ----------------

def parse_eia(blob):
    """One EIA history workbook: sheet 'Data 1', dates in column A from row 4, USD/gal in column B."""
    import xlrd
    book = xlrd.open_workbook(file_contents=blob)
    sheet = book.sheet_by_name('Data 1')
    if 'Dollars per Gallon' not in str(sheet.cell_value(2, 1)):
        raise ValueError('EIA sheet header changed: ' + str(sheet.cell_value(2, 1))[:80])
    out = []
    for r in range(3, sheet.nrows):
        d, v = sheet.cell_value(r, 0), num(sheet.cell_value(r, 1))
        if not isinstance(d, float) or v is None: continue
        day = xlrd.xldate.xldate_as_datetime(d, book.datemode).date()
        if day >= START: out.append((day, v, None))
    if len(out) < 50:
        raise ValueError('EIA series too short')
    return out


def parse_uk(csv_blobs):
    """DESNZ weekly CSVs: pump price and duty in pence per litre, VAT in percent."""
    rows = {}
    for blob in csv_blobs:
        reader = csv.reader(io.StringIO(blob.decode('utf-8-sig', 'replace')))
        head = [h.strip() for h in next(reader)]
        def col(*words):
            for i, h in enumerate(head):
                if all(w.lower() in h.lower() for w in words): return i
            raise ValueError('UK CSV header changed: missing ' + ' '.join(words))
        c = {'pp': col('ULSP', 'Pump price'), 'pd': col('ULSD', 'Pump price'), 'dp': col('ULSP', 'Duty'),
             'dd': col('ULSD', 'Duty'), 'vp': col('ULSP', 'VAT'), 'vd': col('ULSD', 'VAT')}
        for r in reader:
            if not r or not r[0].strip(): continue
            try: day = datetime.datetime.strptime(r[0].strip(), '%d/%m/%Y').date()
            except ValueError: continue
            if day < START: continue
            rows[day] = {k: num(r[i]) if i < len(r) else None for k, i in c.items()}
    out = {'GASOLINE_95': [], 'DIESEL': []}
    for day in sorted(rows):
        v = rows[day]
        for fuel, p, d, t in (('GASOLINE_95', 'pp', 'dp', 'vp'), ('DIESEL', 'pd', 'dd', 'vd')):
            if v[p] is None: continue
            net = None
            if v[d] is not None and v[t] is not None:
                net = (v[p] / (1 + v[t] / 100.0) - v[d]) / 100.0
            out[fuel].append((day, v[p] / 100.0, net))
    if len(out['GASOLINE_95']) < 50:
        raise ValueError('UK series too short')
    return {'GBR': out}


def uk_csv_urls(content_json):
    """CSV attachment links from the GOV.UK content API for the weekly road fuel prices page."""
    urls = []
    def walk(x):
        if isinstance(x, dict):
            u = x.get('url')
            if isinstance(u, str) and u.lower().endswith('.csv') and u.startswith('https://'): urls.append(u)
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(content_json)
    seen = []
    for u in urls:
        if u not in seen: seen.append(u)
    if not seen:
        raise ValueError('No CSV attachments on the UK statistics page')
    return seen


CA_TYPES = {'Regular unleaded gasoline at self service filling stations': 'GASOLINE_REGULAR',
            'Premium unleaded gasoline at self service filling stations': 'GASOLINE_PREMIUM',
            'Diesel fuel at self service filling stations': 'DIESEL'}


def parse_ca(blob):
    """StatCan table zip: monthly cents per litre. The national row (GEO == 'Canada') has regular petrol
    only; the 18 cities have regular, premium and diesel."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = [n for n in z.namelist() if re.fullmatch(r'\d+\.csv', n)][0]
    res = {'CAN': {f: [] for f in CA_TYPES.values()}}
    for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig')):
        geo = r.get('GEO')
        if geo == 'Canada': out = res['CAN']
        elif geo in CA_CITIES: out = res.setdefault(CA_CITIES[geo][0], {f: [] for f in CA_TYPES.values()})
        else: continue
        fuel = CA_TYPES.get(r.get('Type of fuel'))
        if not fuel: continue
        if 'cents per litre' not in (r.get('UOM') or '').lower():
            raise ValueError('StatCan unit changed: ' + str(r.get('UOM')))
        v = num(r.get('VALUE'))
        if v is None: continue
        y, m = map(int, r['REF_DATE'].split('-')[:2])
        day = datetime.date(y, m, 1)
        if day >= START: out[fuel].append((day, v / 100.0, None))
    for area in res:
        for f in res[area]: res[area][f].sort()
        res[area] = {f: v for f, v in res[area].items() if v}
    if len(res['CAN'].get('GASOLINE_REGULAR', [])) < 24:
        raise ValueError('StatCan national series too short')
    return res


NZ_FUELS = {'Regular Petrol': 'GASOLINE_91', 'Premium Petrol 95R': 'GASOLINE_95', 'Diesel': 'DIESEL'}


def parse_nz(blob):
    """MBIE long table: one row per week, fuel and variable, NZD cents per litre."""
    vals = {}
    for r in csv.DictReader(io.StringIO(blob.decode('utf-8-sig', 'replace'))):
        fuel = NZ_FUELS.get(r.get('Fuel'))
        if not fuel or r.get('Variable') not in ('Adjusted retail price', 'Price excluding tax'): continue
        if r.get('Unit') != 'NZD c/L':
            raise ValueError('MBIE unit changed: ' + str(r.get('Unit')))
        day = datetime.date.fromisoformat(r['Date'])
        if day < START: continue
        vals.setdefault((fuel, day), {})[r['Variable']] = num(r['Value'])
    out = {f: [] for f in NZ_FUELS.values()}
    for (fuel, day), v in sorted(vals.items(), key=lambda x: (x[0][0], x[0][1])):
        p = v.get('Adjusted retail price')
        if p is None: continue
        n = v.get('Price excluding tax')
        out[fuel].append((day, p / 100.0, None if n is None else n / 100.0))
    if len(out['GASOLINE_91']) < 50:
        raise ValueError('MBIE series too short')
    return {'NZL': out}


def parse_my(blob):
    """data.gov.my fuelprice: weekly ringgit per litre; only 'level' rows (others are weekly changes).
    Since 30 Sep 2025 most Malaysians pay a subsidised RON95 price (BUDI95); the map uses the
    unsubsidised price that applies to everyone else and the panel shows the subsidised one."""
    rows = json.loads(blob)
    if isinstance(rows, dict): rows = rows.get('data', [])
    out = {'MYS': {'GASOLINE_95': [], 'GASOLINE_97': [], 'DIESEL': []}, 'MYS-E': {'DIESEL': []}}
    subsidy = {}
    for r in rows:
        if r.get('series_type') != 'level': continue
        day = datetime.date.fromisoformat(r['date'])
        if day < START: continue
        for key, area, fuel in (('ron95', 'MYS', 'GASOLINE_95'), ('ron97', 'MYS', 'GASOLINE_97'),
                                ('diesel', 'MYS', 'DIESEL'), ('diesel_eastmsia', 'MYS-E', 'DIESEL')):
            v = num(r.get(key))
            if v: out[area][fuel].append((day, v, None))
        b = num(r.get('ron95_budi95'))
        if b: subsidy = {'date': day.isoformat(), 'GASOLINE_95': b, 'label': 'BUDI95 subsidised RON95 for eligible Malaysian citizens'}
    for a in out:
        for f in out[a]: out[a][f].sort()
    if len(out['MYS']['GASOLINE_95']) < 50:
        raise ValueError('Malaysia series too short')
    return out, subsidy


# ---------------- conversion and output ----------------

def ymd(d): return int(d.strftime('%Y%m%d'))


def to_euro(src, parsed, fx, monthly=False):
    """Local series -> per-area structure with EUR/L history and the local latest value."""
    meta = SOURCES[src]
    ccy, per_gal = meta['currency'], meta['unit'] == 'gal'
    areas, rejected = {}, 0
    for area, fuels in parsed.items():
        for fuel, series in fuels.items():
            pts = []
            for day, local, net in series:
                rate = (rate_month if monthly else rate_on)(fx, ccy, day)
                if not rate: continue
                litre = local / L_PER_GAL if per_gal else local
                eur = litre / rate
                if not (RANGE[0] <= eur <= RANGE[1]):
                    rejected += 1; continue
                e_net = None
                if net is not None:
                    n = (net / L_PER_GAL if per_gal else net) / rate
                    e_net = round(n, 3) if 0 < n < eur else None
                pts.append((day, round(eur, 3), e_net, local))
            if pts:
                areas.setdefault(area, {})[fuel] = pts
    return areas, rejected


def regions_for(src, areas):
    """Which states or provinces each sub-national area covers, for the areas actually present."""
    if src == 'us_eia':
        defs = {k: {'n': n, 'kind': kind, 'eia': code, 'st': st} for k, code, n, kind, st in EIA_AREAS if k in areas}
        return {'USA': dict(REGION_RULES['USA'], areas=defs)} if defs else {}
    if src == 'ca_statcan':
        defs = {k: {'n': n, 'kind': 'city', 'st': [prov]} for k, n, prov in CA_CITIES.values() if k in areas}
        return {'CAN': dict(REGION_RULES['CAN'], areas=defs)} if defs else {}
    return {}


def national_file(src, areas, extra=None, rejected=0, skipped=None):
    out = {'source': src, 'fetched': health.now(), 'meta': SOURCES[src], 'rejected': rejected, 'areas': {}}
    regions = regions_for(src, areas)
    if regions: out['regions'] = regions
    if skipped: out['skipped'] = skipped
    for area, fuels in areas.items():
        out['areas'][area] = {fuel: {'dates': [ymd(d) for d, *_ in pts], 'tax': [p[1] for p in pts],
                                     'net': [p[2] for p in pts], 'local': [round(p[3], 3) for p in pts],
                                     'grade': GRADES.get((area, fuel)) or GRADES.get((area.split('-')[0], fuel), fuel)}
                              for fuel, pts in fuels.items()}
    if extra: out['extra'] = extra
    return out


def eia_fetch(codes, f, offline):
    """Workbooks -> [(series or None, error or None)] in the order given, six downloads at a time."""
    from concurrent.futures import ThreadPoolExecutor
    def one(c):
        try:
            blob = f.get(c) if offline else get(EIA.format(code=c)).content
            return (parse_eia(blob), None) if blob is not None else (None, None)
        except Exception as e:
            return None, e
    with ThreadPoolExecutor(6) as ex:
        return list(ex.map(one, codes))


def eia_reuse(national):
    """Regional series from the previous run when they already reach this week's national date."""
    try:
        old = json.loads((health.OUT / 'fuel' / 'national' / 'us_eia.json').read_text(encoding='utf-8'))
    except Exception:
        return None
    if not national: return None
    newest = ymd(national[-1][0])
    regional = {a: v for a, v in old.get('areas', {}).items() if a.startswith('USA-')}
    if not regional or max(max(s['dates']) for v in regional.values() for s in v.values()) < newest: return None
    day = lambda d: datetime.datetime.strptime(str(d), '%Y%m%d').date()
    return {a: {fuel: [(day(d), loc, None) for d, loc in zip(s['dates'], s['local'])] for fuel, s in v.items()}
            for a, v in regional.items()}


def fetch_source(src, fx, files=None):
    """Download (or read from `files`) and parse one source; returns the national file payload."""
    f = files or {}
    if src == 'us_eia':
        parsed = {'USA': {}}
        for fuel, codes in EIA_SERIES.items():
            last = None
            for code in codes:
                try:
                    blob = f.get(code) or get(EIA.format(code=code)).content
                    parsed['USA'][fuel] = parse_eia(blob); break
                except Exception as e:
                    last = e
            if fuel not in parsed['USA'] and fuel != 'GASOLINE_PREMIUM':
                raise last or ValueError('EIA ' + fuel)
        skipped, reused = [], eia_reuse(parsed['USA'].get('GASOLINE_REGULAR'))
        if reused:                     # EIA publishes weekly; the regions were fetched for this week already
            parsed.update(reused)
        else:                          # about 70 workbooks; EIA is slow per request, so six at a time
            jobs = [(key, fuel, pattern.format(a=code)) for key, code, *_ in EIA_AREAS for fuel, pattern in EIA_AREA_CODE.items()
                    if fuel != 'DIESEL' or code in EIA_DIESEL]
            for (key, fuel, c), (series, err) in zip(jobs, eia_fetch([c for *_, c in jobs], f, files is not None)):
                if series is not None: parsed.setdefault(key, {})[fuel] = series
                elif err is not None: skipped.append(f'{c} ({type(err).__name__})')
        areas, rej = to_euro(src, parsed, fx)
        return national_file(src, areas, rejected=rej, skipped=skipped)
    if src == 'uk_desnz':
        blobs = f.get('uk_csv') or [get(u).content for u in uk_csv_urls(get(UK_CONTENT).json())]
        areas, rej = to_euro(src, parse_uk(blobs), fx)
        return national_file(src, areas, rejected=rej)
    if src == 'ca_statcan':
        areas, rej = to_euro(src, parse_ca(f.get('ca_zip') or get(CA_ZIP).content), fx, monthly=True)
        return national_file(src, areas, rejected=rej)
    if src == 'nz_mbie':
        areas, rej = to_euro(src, parse_nz(f.get('nz_csv') or get(NZ_CSV).content), fx)
        return national_file(src, areas, rejected=rej)
    if src == 'my_mof':
        parsed, subsidy = parse_my(f.get('my_json') or get(MY_API).content)
        areas, rej = to_euro(src, parsed, fx)
        extra = {}
        if subsidy:
            rate = rate_on(fx, 'MYR', datetime.date.fromisoformat(subsidy['date']))
            extra['MYS'] = {'subsidised': dict(subsidy, eurPerL=round(subsidy['GASOLINE_95'] / rate, 3) if rate else None)}
        return national_file(src, areas, extra=extra, rejected=rej)
    raise KeyError(src)


def merge(folder):
    """All national files on disk -> fuel_world.json payload and per-area history files."""
    items, history, asof, extra, sources, regions = [], {}, {}, {}, {}, {}
    for path in sorted((folder / 'national').glob('*.json')):
        nat = json.loads(path.read_text(encoding='utf-8'))
        src, meta = nat['source'], nat['meta']
        sources[src] = dict({k: meta[k] for k in ('name', 'licence', 'attribution', 'url', 'cadence', 'maxAgeDays', 'level')},
                            fetched=nat['fetched'])
        newest = None
        for area, fuels in nat['areas'].items():
            dates = sorted({d for s in fuels.values() for d in s['dates']})
            idx = {d: i for i, d in enumerate(dates)}
            hist = {'dates': dates, 'series': {}, 'grades': {}}
            for fuel, s in fuels.items():
                tax, net = [None] * len(dates), [None] * len(dates)
                for d, t, n in zip(s['dates'], s['tax'], s['net']):
                    tax[idx[d]], net[idx[d]] = t, n
                hist['series'][fuel] = {'tax': tax, 'net': net}
                hist['grades'][fuel] = s['grade']
                i = len(s['dates']) - 1
                day = datetime.datetime.strptime(str(s['dates'][i]), '%Y%m%d').date().isoformat()
                items.append([area, fuel, s['tax'][i], s['net'][i], day, src, meta['level'],
                              meta['currency'], s['local'][i], meta['unit'], s['grade']])
                newest = max(newest or day, day)
            history[area] = dict(hist, area=area, unit='EUR/L', source=meta['name'], attribution=meta['attribution'],
                                 maxAgeDays=meta['maxAgeDays'])
        asof[src] = newest
        extra.update(nat.get('extra') or {})
        regions.update(nat.get('regions') or {})
    payload = {
        'items': items,
        'validTime': max(asof.values()) if asof else None,
        'asOf': asof,
        'standard': STANDARD,
        'sources': sources,
        'extra': extra,
        'regions': regions,
        'unit': 'EUR/L',
        'history': 'fuel/history/{iso3}.json',
        'fx': 'European Central Bank euro reference rates, on the observation date (monthly average for monthly data)',
        'coverage': 'National averages from official sources; grades differ by country and are named per item.',
    }
    return payload, history


def fx_table(files=None):
    """ECB rates: downloaded, or the cached copy from an earlier run when the ECB is unreachable."""
    cache = health.OUT / 'fuel' / 'fx.json'
    try:
        fx = parse_fx((files or {}).get('fx') or get(FX_URL).content)
        health.atomic_json(cache, {c: [[ymd(d) for d in ds], vs] for c, (ds, vs) in fx.items()})
        return fx, None
    except Exception as e:
        if not cache.exists(): raise
        raw = json.loads(cache.read_text(encoding='utf-8'))
        fx = {c: ([datetime.datetime.strptime(str(d), '%Y%m%d').date() for d in v[0]], v[1]) for c, v in raw.items()}
        return fx, f'ECB unreachable ({type(e).__name__}); used cached rates'


def fresh_enough():
    """Recent enough to skip downloading, unless the published files predate a format change
    (no `regions` block, or a currency missing from the cached rates)."""
    try:
        j = json.loads((health.OUT / 'fuel_world.json').read_text())
        got = datetime.datetime.fromisoformat(j['fetched'])
        fx = json.loads((health.OUT / 'fuel' / 'fx.json').read_text())
    except Exception:
        return False
    if 'regions' not in j or any(c not in fx for c in CURRENCIES): return False
    return (datetime.datetime.now(datetime.UTC) - got).total_seconds() < REFRESH_HOURS * 3600


def main(files=None):
    if files is None and fresh_enough():
        health.record('fuel_world', 'ok', f'National data is younger than {REFRESH_HOURS} hours; not downloaded again')
        return
    fx, fx_note = fx_table(files)
    folder = health.OUT / 'fuel'
    failed = []
    for src in SOURCES:
        try:
            nat = fetch_source(src, fx, (files or {}).get(src))
            if not nat['areas']:
                raise ValueError('no values after conversion')
            health.atomic_json(folder / 'national' / f'{src}.json', nat)
        except Exception as e:
            status = getattr(getattr(e, 'response', None), 'status_code', None)
            failed.append(f'{src} ({"HTTP " + str(status) if status else type(e).__name__})')
            print('fuel_world:', src, 'failed:', type(e).__name__, str(e)[:160])
    payload, history = merge(folder)
    if not payload['items']:
        raise ValueError('No national source succeeded and none is cached')
    for area, hist in history.items():
        health.atomic_json(folder / 'history' / f'{area}.json', hist)
    note = ('National averages, plus US regions, states and cities and Canadian cities, converted to euros per litre '
            'at ECB reference rates. Grades differ: see each item.')
    if failed: note += ' Kept last good data for: ' + ', '.join(failed) + '.'
    if fx_note: note += ' ' + fx_note + '.'
    health.publish('fuel_world', payload, 'Official national fuel price statistics (US, UK, Canada, New Zealand, Malaysia)',
                   'reported', note)
    print(f"fuel_world: {len({i[0] for i in payload['items']})} areas, {len(payload['items'])} prices, "
          f"newest {payload['validTime']}, failed: {failed or 'none'}")


def files_from_dir(d):
    """Map a folder of saved samples (probe names) to the `files` argument."""
    d = pathlib.Path(d)
    rd = lambda n: (d / n).read_bytes()
    us = {'EMM_EPMRU_PTE_NUS_DPG': rd('us_regular.xls'), 'EMM_EPMR_PTE_NUS_DPG': rd('us_regular.xls'),
          'EMM_EPMP_PTE_NUS_DPG': rd('us_premium.xls'), 'EMD_EPD2D_PTE_NUS_DPG': rd('us_diesel.xls')}
    return {'fx': rd('ecb_eurofxref_hist.zip'), 'us_eia': us,
            'uk_desnz': {'uk_csv': [rd('uk_weekly_2003_2017.csv'), rd('uk_weekly_2018.csv')]},
            'ca_statcan': {'ca_zip': rd('ca_18100001.zip')}, 'nz_mbie': {'nz_csv': rd('nz_weekly.csv')},
            'my_mof': {'my_json': rd('my_fuelprice.json')}}


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--dir':
        samples = files_from_dir(sys.argv[2])
        health.run('fuel_world', lambda: main(samples))
    else:
        health.run('fuel_world', main)
