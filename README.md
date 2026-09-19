# Earth Observatory data feed

A scheduled GitHub Actions job that fetches public data a browser cannot reach
directly, and commits small JSON files into `data/`. The Earth Now page reads
those files and shows them as live layers.

## Why this exists

- Some sources block browser requests (hurricane centre, GDACS, Coral Reef Watch).
- Some need a key that must not sit in browser code (NASA FIRMS).
- Some ship formats a browser cannot read (GOES GLM lightning arrives as NetCDF).
- Committed files also build an archive, which is what makes date playback possible.

## Setup

**Fast route, one command.** With the [GitHub CLI](https://cli.github.com) installed and
`gh auth login` done, run `bash setup.sh` in this folder. It creates a public repository,
pushes these files, and prints the feed address to paste into Earth Now.

**Manual route**

1. Create a **public** repository, for example `earth-feed`, and copy these files in.
2. Optional extras, each added as a repository secret:
   `OPENSKY_ID` and `OPENSKY_SECRET` for aircraft, `GFW_TOKEN` for fishing effort.
   Ship AIS is not included: the free services stream over websockets, which does not
   suit a scheduled job, so add your own script if you have an AIS source.
3. Optional, for fire detections: get a free key at
   <https://firms.modaps.eosdis.nasa.gov/api/map_key/> and add it as a repository
   secret named `FIRMS_KEY`.
4. In the repository, open **Actions** and enable workflows.
5. Run **Update Earth Observatory feed** once by hand to check it works.
6. In Earth Now, open **Data sources** and paste your feed address:
   `https://raw.githubusercontent.com/<user>/<repo>/main/data/`
   The offline copy remembers it.

## What each file holds

| File | Contents | Class | Cadence |
|---|---|---|---|
| `quakes.json` | USGS M4.5+, past 7 days | observed | 15 min |
| `storms.json` | NHC active storms | observed | 15 min |
| `alerts.json` | GDACS events | reported | 15 min |
| `space.json` | Kp index and OVATION aurora grid | modelled | 15 min |
| `fires.json` | FIRMS VIIRS detections, past 24 h | observed | 15 min, needs key |
| `coral.json` | Coral Reef Watch bleaching alert area | observed | 3 h |
| `flights.json` | OpenSky aircraft positions (account needed) | observed | 15 min |
| `fishing.json` | Global Fishing Watch effort (token needed) | calculated | 15 min, data is days behind |
| `outages.json` | IODA internet disruption alerts | reported | 15 min |
| `sats.json` | CelesTrak orbital elements (OMM JSON) for stations, weather, navigation, Earth observation, science and 300 Starlink | calculated | every 6 h |
| `lightning.json` | GOES GLM flashes, past ~20 min | observed | 15 min |
| `index.json` | List of available files | reference | every run |

Every file carries `fetched`, `source` and `class`, and the page shows those.

## Honest limits

- **Lightning** covers the GOES-East view only: the Americas and nearby ocean.
  These are optical flashes seen from orbit, including in-cloud lightning, so they
  are not all ground strikes. The page labels them that way.
- **Satellites** are element sets, not positions: the page propagates them with SGP4.
  Accuracy decays as elements age, and a pass overhead is not proof of imaging.
  The script refuses to refetch inside six hours, which respects CelesTrak's usage policy.
- GitHub's scheduler is best-effort; runs can be late under load.
- The free Actions allowance is generous for public repositories, but a 15-minute
  schedule is roughly 2,900 runs a month, so keep the jobs short.
- Everything here is for personal, non-commercial use, which matches the licences
  of the sources listed above. Keep the attributions.
