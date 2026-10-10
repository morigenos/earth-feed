"""One-off live check of the new fuel collectors on GitHub's runners (open internet).
Writes into probe/live/ instead of data/, then the workflow commits the results to this branch."""
import json, pathlib, sys, time, traceback
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import feed_health as health
health.OUT = ROOT / 'probe' / 'live'
health.OUT.mkdir(parents=True, exist_ok=True)
import fetch_fuel_world, fetch_fuel_stations
report = {}
for name, mod in (('fuel_world', fetch_fuel_world), ('fuel_stations', fetch_fuel_stations)):
    t = time.time()
    ok = health.run(name, mod.main)
    report[name] = {'ok': ok, 'seconds': round(time.time() - t, 1)}
report['health'] = json.loads((health.OUT / 'health.json').read_text())
(health.OUT / 'report.json').write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
