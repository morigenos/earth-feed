"""National fuel prices outside the EU bulletin.

Fixtures in fixtures/world/ are cut from the real files downloaded on 10 Oct 2026:
- us_*.xls: EIA weekly retail price history workbooks (public domain), first 2005 rows and last 55 weeks.
- uk_*.csv, uk_content.json: DESNZ weekly road fuel prices (Open Government Licence v3.0).
- us_r1x_regular.xls, us_sca_*.xls, us_y05la_regular.xls: the national workbooks above with values scaled
  (x1.04, x1.38, x1.21, x1.41), standing in for EIA's New England, California and Los Angeles series.
- ca_18100001.zip: Statistics Canada table 18-10-0001-01 (Statistics Canada Open Licence), national rows since 2024
  and six cities (Toronto, Thunder Bay, Ottawa, Vancouver, Montréal, Calgary) since 2024, real rows.
- nz_weekly.csv: MBIE weekly fuel price monitoring (CC BY 4.0 NZ), last 60 weeks.
- my_fuelprice.json: data.gov.my fuelprice (CC BY 4.0), last 60 weekly rows.
- ecb_eurofxref_hist.csv: ECB euro reference rates for the dates above, five currencies plus JPY.
"""
import datetime, json, pathlib, sys, tempfile, unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import feed_health as health
import fetch_fuel_world as world

FIX = pathlib.Path(__file__).resolve().parent / 'fixtures' / 'world'


def samples():
    rd = lambda n: (FIX / n).read_bytes()
    return {'fx': rd('ecb_eurofxref_hist.csv'),
            'us_eia': {'EMM_EPMR_PTE_NUS_DPG': rd('us_regular.xls'), 'EMM_EPMP_PTE_NUS_DPG': rd('us_premium.xls'),
                       'EMD_EPD2D_PTE_NUS_DPG': rd('us_diesel.xls'),
                       'EMM_EPMR_PTE_R1X_DPG': rd('us_r1x_regular.xls'), 'EMM_EPMR_PTE_SCA_DPG': rd('us_sca_regular.xls'),
                       'EMD_EPD2D_PTE_SCA_DPG': rd('us_sca_diesel.xls'), 'EMM_EPMR_PTE_Y05LA_DPG': rd('us_y05la_regular.xls')},
            'uk_desnz': {'uk_csv': [rd('uk_weekly_2003_2017.csv'), rd('uk_weekly_2018.csv')]},
            'ca_statcan': {'ca_zip': rd('ca_18100001.zip')}, 'nz_mbie': {'nz_csv': rd('nz_weekly.csv')},
            'my_mof': {'my_json': rd('my_fuelprice.json')}}


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = health.OUT
        health.OUT = pathlib.Path(self.tmp.name)

    def tearDown(self):
        health.OUT = self.old
        self.tmp.cleanup()

    def data(self, name): return json.loads((health.OUT / (name + '.json')).read_text())
    def hist(self, area): return json.loads((health.OUT / 'fuel' / 'history' / (area + '.json')).read_text())
    def item(self, area, fuel):
        return next(i for i in self.data('fuel_world')['items'] if i[0] == area and i[1] == fuel)

    def run_all(self, files=None):
        self.assertTrue(health.run('fuel_world', lambda: world.main(files or samples())))

    def test_all_five_sources_publish(self):
        self.run_all()
        j = self.data('fuel_world')
        self.assertEqual({i[0] for i in j['items'] if i[0].count('-') == 0 or i[0] == 'MYS-E'},
                         {'USA', 'GBR', 'CAN', 'NZL', 'MYS', 'MYS-E'})
        self.assertEqual(set(j['sources']), set(world.SOURCES))
        self.assertEqual(j['class'], 'reported')
        self.assertEqual(j['standard']['USA'], 'GASOLINE_REGULAR')
        self.assertEqual(self.data('health')['datasets']['fuel_world']['status'], 'ok')

    def test_us_regions_states_and_cities_below_the_national_average(self):
        self.run_all()
        j = self.data('fuel_world')
        areas = {i[0] for i in j['items'] if i[0].startswith('USA-')}
        self.assertEqual(areas, {'USA-PADD1A', 'USA-CA', 'USA-LOSANGELES'})
        ca, us = self.item('USA-CA', 'GASOLINE_REGULAR'), self.item('USA', 'GASOLINE_REGULAR')
        self.assertAlmostEqual(ca[8] / us[8], 1.38, places=2)
        self.assertEqual(ca[10], 'Regular, 87 AKI (about 91 RON)')
        self.assertEqual(self.item('USA-CA', 'DIESEL')[10], 'No. 2 on-highway diesel')
        reg = j['regions']['USA']
        self.assertEqual(reg['fill'], 'specific')
        self.assertEqual(set(reg['areas']), areas)
        self.assertEqual(reg['areas']['USA-PADD1A']['st'], ['US-CT', 'US-ME', 'US-MA', 'US-NH', 'US-RI', 'US-VT'])
        self.assertEqual(reg['areas']['USA-CA']['kind'], 'state')
        self.assertEqual(reg['areas']['USA-LOSANGELES']['kind'], 'city')
        self.assertEqual(self.hist('USA-CA')['maxAgeDays'], 35)
        self.assertEqual(self.hist('USA-CA')['grades']['DIESEL'], 'No. 2 on-highway diesel')

    def test_missing_regional_series_is_skipped_not_fatal(self):
        files = samples(); files['us_eia']['EMM_EPMR_PTE_SCA_DPG'] = b'not a workbook'
        self.run_all(files)
        nat = json.loads((health.OUT / 'fuel' / 'national' / 'us_eia.json').read_text())
        self.assertIn('EMM_EPMR_PTE_SCA_DPG (XLRDError)', nat['skipped'])
        self.assertIn('DIESEL', nat['areas']['USA-CA'])
        self.assertNotIn('GASOLINE_REGULAR', nat['areas']['USA-CA'])

    def test_regions_are_not_downloaded_again_within_the_same_week(self):
        self.run_all()
        first = self.item('USA-CA', 'GASOLINE_REGULAR')
        files = samples()
        for code in [c for c in files['us_eia'] if '_NUS_' not in c]: del files['us_eia'][code]
        self.run_all(files)                                     # same national week: regions reused
        self.assertEqual(self.item('USA-CA', 'GASOLINE_REGULAR'), first)
        self.assertIn('USA-LOSANGELES', self.data('fuel_world')['regions']['USA']['areas'])

    def test_canadian_cities_have_diesel_and_premium_and_name_their_province(self):
        self.run_all()
        j = self.data('fuel_world')
        self.assertEqual({i[1] for i in j['items'] if i[0] == 'CAN'}, {'GASOLINE_REGULAR'})
        self.assertEqual({i[1] for i in j['items'] if i[0] == 'CAN-TORONTO'}, {'GASOLINE_REGULAR', 'GASOLINE_PREMIUM', 'DIESEL'})
        t = self.item('CAN-TORONTO', 'DIESEL')
        self.assertEqual(t[4], '2026-08-01'); self.assertEqual(t[7], 'CAD'); self.assertEqual(t[10], 'Diesel, self-service')
        reg = j['regions']['CAN']
        self.assertEqual(reg['fill'], 'mean')
        self.assertEqual({k for k, a in reg['areas'].items() if a['st'] == ['CA-ON']}, {'CAN-TORONTO', 'CAN-THUNDERBAY', 'CAN-OTTAWA'})
        self.assertEqual(len(reg['areas']), 6)
        self.assertEqual(self.hist('CAN-OTTAWA')['maxAgeDays'], 100)

    def test_us_gallons_and_dollars_become_euros_per_litre(self):
        self.run_all()
        it = self.item('USA', 'GASOLINE_REGULAR')
        self.assertEqual(it[4], '2026-10-05')
        self.assertEqual(it[7:10], ['USD', 4.157, 'gal'])
        self.assertAlmostEqual(it[2], 4.157 / 3.785411784 / 1.1213, delta=0.002)   # ECB USD rate around 5 Oct 2026
        self.assertIn('87 AKI', it[10])

    def test_uk_before_tax_price_from_duty_and_vat(self):
        self.run_all()
        it = self.item('GBR', 'GASOLINE_95')
        pump, duty, vat = 1.7488, 0.5295, 0.20
        self.assertAlmostEqual(it[8], pump, places=3)
        self.assertAlmostEqual(it[3] / it[2], (pump / (1 + vat) - duty) / pump, places=2)
        self.assertEqual(self.hist('GBR')['dates'][0], 20050103)    # older weeks come from the 2003-2017 file

    def test_canada_is_national_regular_only_with_month_average_rate(self):
        self.run_all()
        fuels = {i[1] for i in self.data('fuel_world')['items'] if i[0] == 'CAN'}
        self.assertEqual(fuels, {'GASOLINE_REGULAR'})          # diesel and premium exist only per city
        it = self.item('CAN', 'GASOLINE_REGULAR')
        self.assertEqual(it[4], '2026-08-01')
        fx = world.parse_fx((FIX / 'ecb_eurofxref_hist.csv').read_bytes())
        aug = world.rate_month(fx, 'CAD', datetime.date(2026, 8, 1))
        self.assertAlmostEqual(it[2], round(1.738 / aug, 3), places=3)
        self.assertEqual(self.data('fuel_world')['sources']['ca_statcan']['maxAgeDays'], 100)

    def test_new_zealand_standard_is_91_with_taxes(self):
        self.run_all()
        reg, prem = self.item('NZL', 'GASOLINE_91'), self.item('NZL', 'GASOLINE_95')
        self.assertEqual(self.data('fuel_world')['standard']['NZL'], 'GASOLINE_91')
        self.assertLess(reg[2], prem[2])
        self.assertTrue(0 < reg[3] < reg[2])                   # MBIE's price excluding tax
        self.assertIn('91 RON', reg[10])

    def test_malaysia_level_rows_subsidy_and_east_diesel(self):
        self.run_all()
        j = self.data('fuel_world')
        self.assertEqual(self.item('MYS', 'GASOLINE_95')[8], 4.67)
        self.assertEqual(self.item('MYS-E', 'DIESEL')[8], 2.15)
        self.assertEqual(j['extra']['MYS']['subsidised']['GASOLINE_95'], 1.99)
        local = json.loads((health.OUT / 'fuel' / 'national' / 'my_mof.json').read_text())['areas']['MYS']['GASOLINE_95']['local']
        self.assertGreater(min(local), 1.5)                    # weekly-change rows (cents) never enter the series

    def test_history_files_ascending_with_nulls_and_freshness(self):
        self.run_all()
        h = self.hist('USA')
        self.assertEqual(h['dates'], sorted(h['dates']))
        self.assertEqual(h['unit'], 'EUR/L'); self.assertEqual(h['maxAgeDays'], 35)
        self.assertTrue(all(v is None for v in h['series']['DIESEL']['net']))
        self.assertIn('Energy Information Administration', h['attribution'])

    def test_failed_source_keeps_last_good_file(self):
        self.run_all()
        before = self.item('NZL', 'GASOLINE_91')
        broken = samples(); broken['nz_mbie'] = {'nz_csv': b'"Week","Date","Fuel","Variable","Value","Unit","Status"\n'}
        self.run_all(broken)
        j = self.data('fuel_world')
        self.assertEqual(self.item('NZL', 'GASOLINE_91'), before)
        self.assertIn('nz_mbie (ValueError)', j['note'])

    def test_fx_outage_uses_cached_rates(self):
        self.run_all()
        files = samples(); files['fx'] = b'not a zip or csv'
        self.run_all(files)
        self.assertIn('cached rates', self.data('fuel_world')['note'])
        self.assertEqual(self.item('GBR', 'DIESEL')[4], '2026-10-05')

    def test_changed_uk_header_is_a_failure(self):
        bad = b'Date,Petrol,Diesel\n05/10/2026,170,190\n'
        with self.assertRaises(ValueError): world.parse_uk([bad])

    def test_implausible_value_is_rejected(self):
        areas, rejected = world.to_euro('nz_mbie', {'NZL': {'GASOLINE_91': [(datetime.date(2026, 10, 2), 99.0, None)]}},
                                        world.parse_fx((FIX / 'ecb_eurofxref_hist.csv').read_bytes()))
        self.assertEqual((areas, rejected), ({}, 1))

    def test_uk_csv_links_found_in_content_api(self):
        urls = world.uk_csv_urls(json.loads((FIX / 'uk_content.json').read_text()))
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(u.startswith('https://assets.publishing.service.gov.uk/') for u in urls))

    def test_recent_file_skips_download(self):
        self.run_all()
        with patch.object(world.requests, 'get') as get:
            self.assertTrue(health.run('fuel_world', world.main))
            get.assert_not_called()

    def test_recent_file_in_the_old_format_is_refreshed(self):
        self.run_all()
        fx = health.OUT / 'fuel' / 'fx.json'
        raw = json.loads(fx.read_text()); del raw['MYR']; fx.write_text(json.dumps(raw))
        self.assertFalse(world.fresh_enough())
        self.run_all()
        self.assertTrue(world.fresh_enough())
        j = self.data('fuel_world'); del j['regions']
        (health.OUT / 'fuel_world.json').write_text(json.dumps(j))
        self.assertFalse(world.fresh_enough())

    def test_manifest_lists_world_file(self):
        self.run_all(); health.manifest()
        self.assertIn('fuel_world.json', self.data('index')['files'])


if __name__ == '__main__':
    unittest.main()
