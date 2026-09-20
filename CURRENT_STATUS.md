# Current status

Last verified: 20 September 2026, against a live workflow run.

## Feed repository

| Dataset | Status | Records | Notes |
|---|---|---|---|
| quakes | ok | 110 | USGS M4.5+, 7 days |
| storms | ok | 2 | NHC basins only |
| alerts | ok | 100 | GDACS events4app collection |
| space | ok | 65,160 | Kp plus OVATION aurora grid |
| sats | ok | 639 | six CelesTrak groups, refreshed every 6 h |
| lightning | ok | 5,401 | GOES-19, reports partial coverage |
| flights | ok | 5,000 | OpenSky, anonymous access working |
| outages | ok | 0 | IODA reported nothing in the window |
| fires | not configured | — | needs `FIRMS_KEY` |
| ships | not configured | — | no collector: free AIS is websocket-only |
| fishing | not configured | — | needs `GFW_TOKEN` |

Stage 1 hardening (atomic writes, health reporting, regression tests, GDACS and Kp
parsing, GOES-19 lightning) came from ChatGPT and is documented in `STAGE1.md`.

## Globe

- 56 layers across Geography, Hazards, Weather, Ocean, Land and air, Infrastructure, Movement and Space.
- Three modes besides the main globe: solar system, Deep Time, cinematic.
- Reads this feed, reads `health.json`, and falls back to a snapshot on claude.ai where network access is blocked.
- Published page: https://claude.ai/artifact/HBtwLbZx8kKKbZ3c1RVzDh
- Roadmap: https://claude.ai/artifact/1zi4qa2CYpQqieQZNSDNB7

## Open items

1. Add `FIRMS_KEY` for fire detections; optionally `OPENSKY_ID`/`OPENSKY_SECRET` and `GFW_TOKEN`.
2. Ships need a separate collector, since free AIS streams over websockets.
3. `fetch_paleo.py` is not yet in the repository; it precomputes Deep Time reconstructions.
4. Pipelines and submarine cables remain blocked on licence and a dead data source.
5. Coral heat stress is still a proxy in the app; the real NOAA product needs a collector.
