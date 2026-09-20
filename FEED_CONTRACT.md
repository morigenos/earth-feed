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
