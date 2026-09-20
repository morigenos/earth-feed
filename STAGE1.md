Stage 1 corrects feed integrations and adds per-dataset health reporting.

- GDACS uses the documented events4app collection, classifies wildfires separately from heat, and accepts valid empty collections.
- NOAA Kp accepts current object records and legacy array rows.
- Lightning reads GOES-19, checks HTTP responses, preserves cached data if no files can be read, and reports partial coverage.
- Fire points retain acquisition times. Missing credentials are reported without exposing keys.
- Data writes are atomic. health.json records status, last attempt, last success, record count, and available valid time. A failed source preserves its previous JSON file.
- Movement and satellite collectors report failures and configuration gaps. The final index is written after all collectors.
- Scheduling is offset from quarter-hour boundaries; GitHub scheduling remains best-effort, not a real-time guarantee.

Run regression checks with `python -m unittest discover -s tests -v`.

No new credentials are required for public alerts, space weather or GOES lightning. Existing optional FIRMS/OpenSky/GFW secrets remain supported. Ships still require a separate collector. A successful workflow can include unavailable optional sources; consult health.json for dataset health.
