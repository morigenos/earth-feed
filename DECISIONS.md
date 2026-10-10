# Decisions

Append one line per decision, newest at the bottom, with the reason.

- 2026-09-17 Natural Earth for boundaries: public domain, and it maps de facto control with disputed lines kept separate. The app says so rather than presenting any line as settled.
- 2026-09-17 The claude.ai page cannot reach the network. Confirmed against runtime contract 0.2.52: no capability grants egress. Live data therefore lives in the downloaded copy or in data Claude writes into the artifact database.
- 2026-09-17 Blitzortung rejected for lightning: participant-only raw data, commercial use barred, redistribution requires your own server. GOES GLM chosen instead, through the feed.
- 2026-09-18 satellite.js 7 with OMM rather than legacy TLE: CelesTrak catalogue numbers have outgrown the two-line format.
- 2026-09-18 CelesTrak refreshed no more often than every 6 hours, per their usage policy.
- 2026-09-18 Pipelines blocked: Global Energy Monitor requires a request form. Submarine cables blocked: the public TeleGeography repository is gone.
- 2026-09-19 Deep Time uses published GPlates models (Merdith 2021, Müller 2022, Cao 2024). Anything older than a model's range is drawn as an explicitly illustrative scene, never as a reconstruction.
- 2026-09-20 Feed health is authoritative for layer status: `health.json` decides whether a layer reads as live, unconfigured or failed.
- 2026-10-10 Fuel prices start with the EU Weekly Oil Bulletin: free, reproduction authorised with acknowledgement, prices with and without taxes, weekly history since 2005. History is rebuilt from the Commission's workbook on every download rather than archived here, so a lost gh-pages branch loses nothing. Countries are keyed by ISO alpha-3.
- 2026-10-10 The gh-pages restore now fails the run unless the branch is restored or truly absent, and publishing requires a successful restore: before, a failed fetch fell back to main's frozen data and force-pushed it over the live site.
- 2026-10-10 One globe build: the Stage 1–3 build is the source of truth for the offline copy, `index.html` and the claude.ai page; the coral layer, feed-health list and Pages feed address were ported into it.
