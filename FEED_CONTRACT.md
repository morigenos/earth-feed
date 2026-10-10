# Feed contract

The interface between the **feed repository** (`morigenos/earth-feed`) and the
**Earth Now globe**. Either side can change freely as long as this contract holds.
Breaking a field breaks a layer silently, so change this file in the same commit.

Base address the globe is given:
`https://raw.githubusercontent.com/morigenos/earth-feed/main/data/`

## Common envelope

Every file is a JSON object carrying at least:

| Field | Meaning |
|---|---|
| `fetched` | ISO 8601 UTC, when the collector ran |
| `source` | human-readable provider string, shown in the app |
| `class` | one of `observed`, `modelled`, `reported`, `calculated`, `reference` |
| `note` | caveats shown to the reader |
| `validTime` | optional; the observation time, preferred over `fetched` for age |

## Files and shapes

| File | `items` shape | Notes |
|---|---|---|
| `quakes.json` | `[lon, lat, depthKm, mag, place, epochSeconds]` | USGS M4.5+, 7 days |
| `fires.json` | `[lat, lon, frp]` | note the lat/lon order differs from quakes |
| `lightning.json` | `[lon, lat, epochSeconds]` | plus `filesRead`, `filesRequested`, `coverage` |
| `flights.json` | `[lon, lat, altM, onGround0or1, callsign]` | |
| `storms.json` | `{n, basin, lat, lon, windKt, pres, status, d}` | `status: "active"` draws a spiral |
| `alerts.json` | `{t, n, lat, lon, d}`, `id` and `validTime` optional | `t` ∈ flood, drought, heat, storm, ash, quake, landslide |
| `outages.json` | `{n, lat, lon, d}` | |
| `fishing.json` | `[lon, lat, hours]` | |
| `sats.json` | OMM records, each with `OBJECT_NAME`, `EPOCH`, `MEAN_MOTION`, … and `__g` group | groups: stations, weather, gps-ops, resource, science, starlink |
| `space.json` | no `items`; `kp`, `kpTime`, `aurora` as `[lon, lat, value]`, `auroraTime` | |
| `paleo/<MODEL>_<age>.json` | `{age, model, features: GeoJSON}` | ages every 10 Ma (20 for CAO2024) |
| `fuel.json` | `[iso3, fuel, eurPerL, eurPerLExTax\|null, observedDate, sourceId, coverageLevel, currency, localPerL]` | `fuel` ∈ GASOLINE_95, DIESEL, LPG; plus `validTime` (bulletin date), `ref` (EU and euro-area averages), `stale` (`[iso3, lastDate]`, history only), `attribution` |
| `fuel/history/<ISO3>.json` | `{dates:[yyyymmdd…], series:{FUEL:{tax:[…], net:[…]}}}` | weekly since 2005, ascending, EUR/L, `null` where not reported; also `EU.json` and `EUR.json` |
| `fuel_world.json` | `[area, fuel, eurPerL, eurPerLExTax\|null, observedDate, sourceId, coverageLevel, currency, localPrice, localUnit, gradeLabel]` | areas USA, GBR, CAN, NZL, MYS, the sub-area `MYS-E` (Sabah, Sarawak, Labuan), 28 US areas (`USA-PADD1A`, `USA-CA`, `USA-LOSANGELES`…) and 18 Canadian cities (`CAN-TORONTO`…); plus `regions` (see below), `standard` (area → standard petrol id), `sources` (per source: name, licence, attribution, url, cadence, maxAgeDays, level, fetched), `asOf`, `extra` (Malaysia's subsidised RON95) |
| `fuel/history/<AREA>.json` (national) | as above, plus `grades`, `unit`, `source`, `attribution`, `maxAgeDays` | same path as the EU histories; written by `fetch_fuel_world.py` for its areas; Canada monthly since 2006 |
| `fuel_stations.json` | `[iso3, stationCount, validTime]` | plus `countries` (per country: source, licence, attribution, url, level, cadence, validTime, fuels, zones, stats, bbox, fetched, maxAgeDays, file, count, bytes, `currency`; outside the euro also `eurPerUnit`, `fxDate`; optional `note`, `undated`) |
| `fuel/stations/<ISO3>.json` | `[lon, lat, brandIdx\|-1, flags, petrol\|null, diesel\|null, lpg\|null, updatedEpoch, id, town, address, extra\|null]` | FRA, ESP, ITA, MEX; plus `brands`, `fuels`, `extraFuels`, `zones`, `fields`, `flagBits`, `stats`, `currency` (and the index's optional fields) |
| `fuel/fx.json` | `{CCY: [[yyyymmdd…], [rate…]]}` | cache of ECB euro reference rates, used when the ECB is unreachable |
| `health.json` | `{datasets: {name: {status, lastAttempt, lastSuccess, recordCount, validTime}}}` | `status` ∈ ok, not_configured, error strings |
| `index.json` | `{files: [...]}` | manifest |

## How the globe uses `health.json`

- `ok` with `recordCount: 0` → the layer says the feed reports none right now.
- `not_configured` → the layer says a key is missing, and stays off.
- anything else → the layer shows the failure and keeps the last good data.

## Rules both sides keep

1. A failed collector must leave the previous file intact, never write an empty one.
2. Coordinates are decimal degrees, WGS84, longitude first except where noted above.
3. Times are UTC, ISO 8601 for strings, epoch **seconds** inside item arrays.
4. Anything inferred or modelled says so in `class` and `note`; the app repeats that wording to the reader.
5. Keep files small: round coordinates, cap record counts, and prefer arrays over objects for large lists.

## Fuel prices (`fuel.json`)

- Country key is ISO 3166-1 alpha-3, the same key the globe's Natural Earth countries carry as `a3`.
  Never join on alpha-2: Natural Earth stores `-99` for France and Norway.
- Prices are euros per litre, three decimals. `localPerL` is the same price in the national currency
  for members outside the euro, otherwise equal to `eurPerL`.
- A country absent from `items` has no current value; it is not zero. Countries in `stale` stopped
  reporting (the United Kingdom after December 2020) and appear only in history.
- `validTime` is the bulletin date (a Monday), never the fetch time. The page treats the layer as stale
  after `staleAfterDays` (21: the Commission skips weeks around holidays).
- Attribution is required: "Source: European Commission, Weekly Oil Bulletin."
- The United Kingdom is not in `fuel.json` any more: `fetch_fuel_world.py` owns `GBR` and its history
  (DESNZ weekly series since 2003), so the bulletin's frozen UK rows never overwrite it.

## National fuel prices outside the EU (`fuel_world.json`)

- Fuel ids: `GASOLINE_95`, `GASOLINE_91`, `GASOLINE_97`, `GASOLINE_REGULAR` (US and Canadian regular, 87 AKI,
  about 91 RON), `GASOLINE_PREMIUM`, `DIESEL`, `LPG`. `standard` names the petrol a country's petrol map uses;
  absent means `GASOLINE_95`. Every item carries its own `gradeLabel`, shown to the reader as is.
- Euros per litre at the ECB reference rate on the observation date (monthly average for Canada's monthly
  data). `localPrice` is in the national currency per `localUnit` (`gal` for the US, `L` elsewhere).
- `eurPerLExTax` is `null` where the source publishes no tax split (US, Canada, Malaysia).
- `maxAgeDays` per source decides when a value stops showing on the map: 35 for weekly sources, 100 for
  Statistics Canada (monthly, about seven weeks behind).
- Sub-areas use `ISO3-X` keys (`MYS-E`); the globe paints them over the matching part of the country.
  A sub-area shares its country's `standard` petrol.

## Regions below the national level (`regions` in `fuel_world.json`)

- `regions.USA` and `regions.CAN`: `{fill, order, note, areas: {areaKey: {n, kind, st, eia?}}}`. `kind` is
  `region`, `subregion`, `state` or `city`; `st` lists the ISO 3166-2 codes the area covers (`US-CA`, `CA-ON`).
- `fill: "specific"` (US): a state takes the area of the highest `order` kind that covers it and has a value
  (state, then sub-region, then region). Cities are listed only.
- `fill: "mean"` (Canada): a province takes the plain average of its cities with a value; Statistics Canada
  publishes no provincial series. A province without a city (Nunavut) has no regional value.
- EIA publishes diesel for the regions, sub-regions and California only; other states and cities have petrol only.
- Regional series are downloaded once per published EIA week; a missing regional workbook is skipped (listed in
  the national file's `skipped`) and never fails the source.
- Each source's `attribution` and `licence` must be shown wherever its numbers are.

## Station prices (`fuel_stations.json`, `fuel/stations/`)

- France (prix-carburants, Licence Ouverte 2.0), Spain (MITECO Geoportal, reuse with attribution),
  Italy (MIMIT Osservatorio prezzi, IODL 2.0), Mexico (Comisión Nacional de Energía, Libre Uso MX).
  Pump prices with tax per litre in the country's `currency`: euros with three decimals, Mexican pesos
  with two. Outside the euro, `eurPerUnit` is the ECB reference rate (euros per unit) of `fxDate`; if the
  ECB is unreachable the previous file's rate is kept, and if there is none the field is `null`.
- `undated: true` (Mexico) means the source gives no per-station dates: `updatedEpoch` is `null` and no
  age filter can be applied. `validTime` is then the source's scheduled publication time (18:00 Mexico City).
- `note` is a caveat the globe shows with the country's stations (Mexico: lower VAT in the border regions).
- `flags`: bit 0 motorway, bit 1 attended service only, bit 2 open 24 hours; `flags >> 3` is the zone index
  into `zones` (Spain: mainland and Balearics, Canary Islands, Ceuta and Melilla, ranked separately).
- Columns `petrol`, `diesel`, `lpg` hold each country's standard product (labels in `fuels`);
  other products are `extra` pairs `[extraFuelIdx, price]` with names in `extraFuels`.
- `updatedEpoch` is the station's own last price change, epoch seconds UTC. France publishes Paris local
  time labelled as UTC; the collector reads it as Europe/Paris.
- Prices older than `maxAgeDays` (30) and prices outside a plausible range per product are dropped
  (`rejected` counts them). A country whose feed returns too few stations keeps its previous file.
