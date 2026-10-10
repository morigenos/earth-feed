"""Station-level fuel prices: France, Spain, Italy, Mexico.

Fixtures in fixtures/stations/ are cut from the real feeds downloaded on 10 Oct 2026:
- fr_instant.json.gz: prix-carburants instant feed v2 (data.gouv.fr, Licence Ouverte 2.0), 50 stations
  including motorway stations, stations with month-old prices and LPG sellers; unused fields removed.
- es_stations.json: MITECO Geoportal Gasolineras REST response, 50 stations including the Canary Islands,
  Ceuta and Melilla, records unchanged.
- it_anagrafica.csv, it_prezzo_alle_8.csv: MIMIT registry and 8 a.m. prices (IODL 2.0), 50 stations
  including motorway, attended-only and names that contain '|'.
- mx_places.xml, mx_prices.xml: the Mexican regulator's daily lists (federal open data), 47 priced stations
  including three whose products are split over several <place> blocks, one selling only premium and one
  only diesel, plus two listed stations with no price. Records unchanged.
"""
import datetime, gzip, json, pathlib, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import feed_health as health
import fetch_fuel_stations as st

FIX = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'stations'
NOW = datetime.datetime(2026, 10, 10, 4, 37, tzinfo=datetime.UTC)
LOW = {'FRA': 20, 'ESP': 20, 'ITA': 20, 'MEX': 20}


def samples():
    return {'FRA': gzip.decompress((FIX / 'fr_instant.json.gz').read_bytes()),
            'ESP': (FIX / 'es_stations.json').read_bytes(),
            'ITA': ((FIX / 'it_anagrafica.csv').read_bytes(), (FIX / 'it_prezzo_alle_8.csv').read_bytes()),
            'MEX': ((FIX / 'mx_places.xml').read_bytes(), (FIX / 'mx_prices.xml').read_bytes()),
            'MXN_PER_EUR': 21.32, 'MXN_DATE': datetime.date(2026, 10, 9)}


class StationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = health.OUT
        health.OUT = pathlib.Path(self.tmp.name)
        self.low = patch.dict(st.MIN_STATIONS, LOW); self.low.start()

    def tearDown(self):
        self.low.stop()
        health.OUT = self.old
        self.tmp.cleanup()

    def data(self, name): return json.loads((health.OUT / (name + '.json')).read_text())
    def country(self, iso): return json.loads((health.OUT / 'fuel' / 'stations' / f'{iso}.json').read_text())
    def run_all(self, files=None):
        self.assertTrue(health.run('fuel_stations', lambda: st.main(files or samples(), NOW)))

    def test_four_countries_publish_with_index(self):
        self.run_all()
        idx = self.data('fuel_stations')
        self.assertEqual(set(idx['countries']), {'FRA', 'ESP', 'ITA', 'MEX'})
        for iso, c in idx['countries'].items():
            self.assertEqual(c['file'], f'fuel/stations/{iso}.json')
            self.assertEqual(c['count'], len(self.country(iso)['items']))
        self.assertEqual(idx['class'], 'reported')
        self.assertEqual(self.data('health')['datasets']['fuel_stations']['status'], 'ok')

    def test_france_columns_flags_and_local_time(self):
        self.run_all()
        j = self.country('FRA')
        self.assertEqual(j['fuels']['PETROL'], 'SP95-E10')
        rows = j['items']
        self.assertTrue(any(r[3] & st.MOTORWAY for r in rows))
        self.assertTrue(any(r[3] & st.H24 for r in rows))
        newest = datetime.datetime.fromisoformat(j['validTime'])
        self.assertLessEqual(newest, NOW)                          # stamps read as Paris time, not UTC
        self.assertTrue(all(NOW.timestamp() - r[7] <= st.MAX_AGE_DAYS * 86400 for r in rows))
        self.assertLess(len(rows), 50)                             # month-old prices left out

    def test_spain_decimal_commas_and_zones(self):
        self.run_all()
        j = self.country('ESP')
        zones = {r[3] >> 3 for r in j['items']}
        self.assertEqual(zones, {0, 1, 2})
        self.assertIn('1', j['stats']['PETROL'])                    # Canary Islands ranked on their own
        self.assertLess(j['stats']['PETROL']['1']['median'], j['stats']['PETROL']['0']['median'])
        self.assertTrue(all(isinstance(r[4], float) for r in j['items'] if r[4] is not None))

    def test_spain_old_file_is_refused(self):
        later = NOW + datetime.timedelta(days=5)
        with self.assertRaises(ValueError): st.parse_es(samples()['ESP'], later)

    def test_italy_self_service_attended_only_and_piped_names(self):
        self.run_all()
        j = self.country('ITA')
        self.assertTrue(any(r[3] & st.MOTORWAY for r in j['items']))
        self.assertTrue(any(r[3] & st.SERVED for r in j['items']))
        piped = next(r for r in j['items'] if r[8] == '40820')
        self.assertTrue(piped[10].startswith('STR. PROV.LE 82'))   # address, not part of the name
        reg, pr = samples()['ITA']
        both = st.parse_it(reg, pr, NOW)[0]
        sid = next(s for s in both if not s['flags'] & st.SERVED and 'PETROL' in s['slot'])['id']
        rows = [l.split('|') for l in pr.decode().splitlines()[2:] if l.startswith(sid + '|Benzina|')]
        self.assertEqual(next(s for s in both if s['id'] == sid)['slot']['PETROL'],
                         float(next(r for r in rows if r[3] == '1')[2]))

    def test_mexico_pesos_become_euros_that_round_trip_exactly(self):
        self.run_all()
        j = self.country('MEX')
        self.assertEqual(len(j['items']), 47)
        self.assertEqual((j['currency'], j['perEur'], j['rateDate']), ('MXN', 21.32, '2026-10-09'))
        self.assertFalse(j['stationTimes']); self.assertTrue(j['nationalFromStations'])
        self.assertEqual(j['zones'], ['Mexico']); self.assertEqual(j['extraFuels'], ['Gasolina premium (91 octanos)'])
        by_id = {r[8]: r for r in j['items']}
        r = by_id['11696']                          # regular and diesel in one block, premium in another
        self.assertEqual(round(r[4] * 21.32, 2), 21.99); self.assertEqual(round(r[5] * 21.32, 2), 25.39)
        self.assertEqual(round(r[11][0][1] * 21.32, 2), 27.41)
        self.assertIsNone(r[7]); self.assertTrue(r[10].startswith('Permiso PL/'))
        self.assertIsNone(by_id['2133'][4]); self.assertEqual(by_id['2133'][11][0][0], 0)    # premium only
        self.assertIsNone(by_id['10615'][4]); self.assertIsNotNone(by_id['10615'][5])       # diesel only
        idx = self.data('fuel_stations')['countries']['MEX']
        self.assertEqual(idx['currency'], 'MXN'); self.assertTrue(idx['nationalFromStations'])
        self.assertIn('0', idx['stats']['PETROL'])
        self.assertTrue(all(-118.6 <= r[0] <= -86.5 and 14.3 <= r[1] <= 32.8 for r in j['items']))

    def test_mexico_uses_cached_ecb_rate_and_refuses_a_stale_one(self):
        fx = health.OUT / 'fuel' / 'fx.json'; fx.parent.mkdir(parents=True, exist_ok=True)
        fx.write_text(json.dumps({'MXN': [[20261008, 20261009], [21.40, 21.28]]}))
        rate, day = st.mx_rate(NOW)
        self.assertEqual((rate, day), (21.28, datetime.date(2026, 10, 9)))
        files = samples(); del files['MXN_PER_EUR']
        self.run_all(files)
        self.assertEqual(self.country('MEX')['perEur'], 21.28)
        fx.write_text(json.dumps({'MXN': [[20260901], [21.0]]}))
        with self.assertRaises(ValueError): st.mx_rate(NOW)

    def test_implausible_column_value_is_dropped(self):
        files = samples()
        fr = json.loads(files['FRA']); fr[5]['gazole_prix'] = '9.999'; fr[6]['gplc_prix'] = '2.31'
        files['FRA'] = json.dumps(fr).encode()
        self.run_all(files)
        self.assertGreaterEqual(self.country('FRA')['rejected'], 1)

    def test_failed_country_keeps_previous_file(self):
        self.run_all()
        before = (health.OUT / 'fuel' / 'stations' / 'ITA.json').read_bytes()
        files = samples(); files['ITA'] = (b'not a registry\n', b'')
        self.run_all(files)
        self.assertEqual(before, (health.OUT / 'fuel' / 'stations' / 'ITA.json').read_bytes())
        self.assertIn('ITA (ValueError)', self.data('fuel_stations')['note'])

    def test_too_few_stations_refused(self):
        with patch.dict(st.MIN_STATIONS, {'ESP': 10000}):
            files = samples(); del files['FRA'], files['ITA'], files['MEX']
            self.assertFalse(health.run('fuel_stations', lambda: st.main(files, NOW)))

    def test_recent_country_not_downloaded_again(self):
        self.run_all()
        with patch.object(st.requests, 'get') as get:
            self.assertTrue(health.run('fuel_stations', st.main))
            get.assert_not_called()

    def test_manifest_lists_station_index(self):
        self.run_all(); health.manifest()
        self.assertIn('fuel_stations.json', self.data('index')['files'])


if __name__ == '__main__':
    unittest.main()
