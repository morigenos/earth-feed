import sys, pathlib, tempfile, json, unittest
from unittest.mock import patch, Mock
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import feed_health as health
import fetch_feeds as feeds
import fetch_lightning as lightning
import fetch_movement as movement

class FeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=health.OUT
        health.OUT=pathlib.Path(self.tmp.name)
    def tearDown(self):
        health.OUT=self.old
        self.tmp.cleanup()
    def data(self,name): return json.loads((health.OUT/(name+'.json')).read_text())
    def test_current_kp_shape(self):
        self.assertEqual(feeds.latest_kp([{'Kp':1.67,'time_tag':'time'}]),(1.67,'time'))
    def test_legacy_kp_shape(self):
        self.assertEqual(feeds.latest_kp([['time','Kp'],['time2','3']]),(3,'time2'))
    def test_bad_kp_rejected(self):
        with self.assertRaises(ValueError): feeds.latest_kp([{'Kp':float('nan')}])
    def test_failure_preserves_cache_and_reports(self):
        health.publish('quakes',{'items':[[1,2]]},'test','observed')
        before=(health.OUT/'quakes.json').read_bytes()
        def fail(): raise ValueError('SECRET_IN_URL')
        self.assertFalse(health.run('quakes',fail))
        self.assertEqual(before,(health.OUT/'quakes.json').read_bytes())
        report=self.data('health')['datasets']['quakes']
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['recordCount'],1)
        self.assertNotIn('SECRET',json.dumps(report))
    def test_empty_success_clears_old_items(self):
        health.publish('alerts',{'items':[1]},'test','reported')
        health.publish('alerts',{'items':[]},'test','reported')
        self.assertEqual(self.data('alerts')['items'],[])
        self.assertEqual(self.data('health')['datasets']['alerts']['status'],'ok')
    def test_missing_credentials_visible(self):
        with patch.dict('os.environ',{'FIRMS_KEY':''}):health.run('fires',feeds.fires)
        self.assertEqual(self.data('health')['datasets']['fires']['status'],'not_configured')
    def test_manifest_excludes_health_as_dataset(self):
        health.publish('alerts',{'items':[]},'test','reported');health.manifest()
        self.assertEqual(self.data('index')['files'],['alerts.json'])
        self.assertEqual(self.data('health')['datasets']['ships']['status'],'not_configured')
    def test_fire_acquisition_time_retained(self):
        response=Mock(text='latitude,longitude,frp,acq_date,acq_time\n46,14,0,2026-09-19,0930\n')
        with patch.dict('os.environ',{'FIRMS_KEY':'test'}),patch.object(feeds,'get',return_value=response):feeds.fires()
        item=self.data('fires')['items'][0]
        self.assertEqual(item[:3],[46,14,0])
        self.assertEqual(item[3],1789810200)
    def test_invalid_fire_response_not_empty_success(self):
        with patch.dict('os.environ',{'FIRMS_KEY':'test'}),patch.object(feeds,'get',return_value=Mock(text='Invalid key')):
            self.assertFalse(health.run('fires',feeds.fires))
        self.assertFalse((health.OUT/'fires.json').exists())
    def test_gdacs_wildfire_and_empty_collection(self):
        feature={'geometry':{'type':'Point','coordinates':[14,46]},'properties':{'eventtype':'WF','eventid':1,'iscurrent':'true'}}
        response=Mock();response.json.return_value={'features':[feature]}
        with patch.object(feeds,'get',return_value=response):feeds.alerts()
        self.assertEqual(self.data('alerts')['items'][0]['t'],'fire')
        response.json.return_value={'features':[]}
        with patch.object(feeds,'get',return_value=response):feeds.alerts()
        self.assertEqual(self.data('alerts')['items'],[])
    def test_lightning_no_files_is_failure(self):
        # No dependency or network is required to test the missing-file branch.
        with patch.dict(sys.modules,{'netCDF4':Mock()}),patch.object(lightning,'list_keys',return_value=[]):
            self.assertFalse(health.run('lightning',lightning.main))
        self.assertEqual(self.data('health')['datasets']['lightning']['status'],'failed')
        self.assertFalse((health.OUT/'lightning.json').exists())
    def test_malformed_movement_response_preserves_cache(self):
        health.publish('outages',{'items':[{'n':'previous'}]},'test','reported')
        response=Mock();response.json.return_value={}
        with patch.object(movement.requests,'get',return_value=response):
            self.assertFalse(health.run('outages',movement.outages))
        self.assertEqual(self.data('outages')['items'][0]['n'],'previous')

if __name__=='__main__':unittest.main()
