# Current status

Last verified: 20 September 2026, against a live workflow run. Fuel row and globe section updated 10 October 2026 (fuel verified locally, not yet by a scheduled run).

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
| fuel | pending first scheduled run | 73 | 27 EU states, bulletin of 5 Oct 2026; verified locally against the Commission workbook, 10 Oct 2026 |
| fires | not configured | — | needs `FIRMS_KEY` |
| ships | not configured | — | no collector: free AIS is websocket-only |
| fishing | not configured | — | needs `GFW_TOKEN` |

Stage 1 hardening (atomic writes, health reporting, regression tests, GDACS and Kp
parsing, GOES-19 lightning) came from ChatGPT and is documented in `STAGE1.md`.

## Globe

- One build since 10 Oct 2026: the Stage 1–3 build (portable snapshots, health-driven status, comparison picker)
  with the published builds' coral layer and Pages feed address ported in, plus the EU fuel layer. `index.html`
  here is that build; the offline copy in the project folder is the same file.
- 57 layers across Geography, Hazards, Weather, Ocean, Land and air, Infrastructure, Movement, Space and Economy.
- Three modes besides the main globe: solar system, Deep Time, cinematic.
- Reads this feed (on Pages from `data/`, elsewhere from https://morigenos.github.io/earth-feed/data/), reads
  `health.json`, and falls back to embedded snapshots where network access is blocked. The fuel layer carries its
  own snapshot (bulletin of 5 Oct 2026, history since 2005).
- Fuel timeline (10 Oct 2026): scrub or play the fuel map through the bulletins (2 years, 5 years, since 2005),
  1-year change metric, 1/3/5-year changes in the country panel. Selecting a country flies to it and pauses
  auto-rotation until the selection is cleared.
- Published page: https://claude.ai/artifact/HBtwLbZx8kKKbZ3c1RVzDh
- Roadmap: https://claude.ai/artifact/1zi4qa2CYpQqieQZNSDNB7

## Open items

1. Add `FIRMS_KEY` for fire detections; optionally `OPENSKY_ID`/`OPENSKY_SECRET` and `GFW_TOKEN`.
2. Ships need a separate collector, since free AIS streams over websockets.
3. Pipelines and submarine cables remain blocked on licence and a dead data source.
4. Fuel: Phase 1b (GlobalPetrolPrices, private channel) waits on written licence terms; see the fuel plan in the project folder.
