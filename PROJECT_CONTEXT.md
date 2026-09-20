# Project context

An interactive 3D Earth observatory viewed from space, plus a separate scenario globe.

## Surfaces

1. **Earth Now globe** — one self-contained HTML file. Two builds from one source:
   the published claude.ai page (sandboxed, no network, snapshot data) and the
   downloaded live copy (fetches providers directly and refreshes itself).
2. **Feed repository** — this repo. Scheduled GitHub Actions collect sources a
   browser cannot reach: CORS-blocked, key-gated, or in formats a browser cannot parse.
3. **Scenario globe** — the Super El Niño and disaster lab, kept separate by design.

## Principles

- Every layer is classified: observed, modelled, reported, calculated, reference.
- Provider, licence, resolution and update rhythm are recorded per layer and shown in the app.
- Unavailable is stated, never simulated. A layer that cannot load says why.
- Free viewing is not a free API; non-commercial is not commercial; regularly updated is not live.
- Personal, non-commercial use, which is what the Open-Meteo, RainViewer and GFW terms assume.
