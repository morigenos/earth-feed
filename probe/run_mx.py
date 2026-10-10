"""One-off live run of the station collector (now with Mexico) on GitHub's runners; output to probe/live."""
import json, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import feed_health as health
health.OUT = ROOT / 'probe' / 'live'
health.OUT.mkdir(parents=True, exist_ok=True)
import fetch_fuel_stations
t = time.time()
ok = health.run('fuel_stations', fetch_fuel_stations.main)
report = {'ok': ok, 'seconds': round(time.time() - t, 1), 'health': json.loads((health.OUT / 'health.json').read_text())}
(health.OUT / 'report.json').write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
