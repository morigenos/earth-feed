# Current status

Last verified: 20 September 2026, against a live workflow run. Fuel rows and globe section updated 10 October 2026 (the national and station collectors ran against the live sources on GitHub's runners from a test branch; not yet by a scheduled run).

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
| fuel_world | ok; regions pending merge | 132 | US, UK, Canada, New Zealand, Malaysia (plus East Malaysia diesel); with Stage 9 also 28 US regions, states and cities and 18 Canadian cities, verified on a runner 10 Oct 2026 (2.4 minutes, EIA downloads in parallel) |
| fuel_stations | ok, Spain pending | 30,775 | First run from main, 10 Oct 2026: France 9,174 and Italy 21,601 published; Spain's server refused the runner's connection, so the globe shows Spain from its embedded snapshot until a run gets through. Mexico (13,848) verified on a runner; publishes once merged |
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
  auto-rotation until the selection is cleared. A Fuel ranking window in the dock ranks the EU countries for the
  fuel, metric and date on the map and re-sorts as the timeline plays.
- Fuel beyond the EU (10 Oct 2026): national averages for the US, UK, Canada, New Zealand and Malaysia on the same
  map, each country's standard petrol named (° in the ranking where it is about 91 RON), East Malaysia's diesel
  painted separately, local currency in the country panel. Selecting France, Spain or Italy, or zooming close,
  shows its stations as dots ranked cheap to dear within their area; click one for its prices. The page embeds a
  station snapshot (10 Oct 2026) for when the feed is out of reach.
- Mexico's stations (10 Oct 2026): 13,848 stations from the Comisión Nacional de Energía, ranked across the
  country, prices in pesos with the euro equivalent. Mexico has no national average in the layer, so it stays
  unshaded; the panel says so and notes the border regions' lower VAT.
- US and Canadian regions (Stage 9, 10 Oct 2026): selecting the United States or Canada, or zooming close, colours
  states and provinces against the national figure (blue cheaper, red dearer, ±20%) from EIA's regions, sub-regions
  and nine states and from the average of Statistics Canada's cities in each province. The fills follow the fuel
  timeline; the panel lists regions, states and cities with their 1-year change.
- Published page: https://claude.ai/artifact/HBtwLbZx8kKKbZ3c1RVzDh
- Roadmap: https://claude.ai/artifact/1zi4qa2CYpQqieQZNSDNB7

## Open items

1. Add `FIRMS_KEY` for fire detections; optionally `OPENSKY_ID`/`OPENSKY_SECRET` and `GFW_TOKEN`.
2. Ships need a separate collector, since free AIS streams over websockets.
3. Pipelines and submarine cables remain blocked on licence and a dead data source.
4. Fuel: Phase 1b (GlobalPetrolPrices, private channel) waits on written licence terms; see the fuel plan in the project folder.
5. Fuel: Statistics Canada publishes only regular petrol nationally; Canada's diesel and premium now show by city and province (Stage 9), not on the world map.
6. Fuel stations: Germany waits on a Tankerkönig API key; Portugal on Archie's call (the DGEG portal allows free use but forbids commercial use); the UK's Fuel Finder on registration and runner access.
