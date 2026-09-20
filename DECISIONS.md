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
