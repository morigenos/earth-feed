"""NOAA Coral Reef Watch bleaching heat stress.

Degree Heating Weeks measures accumulated heat stress on reefs: roughly, how many
weeks of temperature 1 degree above the summer maximum a reef has endured over the
past twelve weeks. Four is where significant bleaching becomes likely, eight where
widespread bleaching and mortality do.

The 5 km grid is far too large for a browser, so this thins it to about one degree
and keeps only cells carrying real stress. NOAA blocks browser requests, which is
why this runs here rather than in the page.
"""
import json, pathlib, datetime, requests

OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)
TARGET = OUT / "coral.json"
BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW.json"
UA = {"User-Agent": "earth-observatory-feed (personal, non-commercial)"}
STRIDE = 20          # 5 km cells, so 20 is about one degree
LAT_LIMIT = 35       # reefs live in the tropics
MIN_DHW = 1.0        # below this there is no stress worth drawing

def query(day, lat_first, lat_last):
    url = (f"{BASE}?CRW_DHW%5B({day}T12:00:00Z)%5D"
           f"%5B({lat_first}):{STRIDE}:({lat_last})%5D"
           f"%5B(-180.0):{STRIDE}:(180.0)%5D")
    r = requests.get(url, headers=UA, timeout=180)
    r.raise_for_status()
    return r.json()

def main():
    cells, used_day, err = [], None, None
    for back in (1, 2, 3, 4):
        day = (datetime.date.today() - datetime.timedelta(days=back)).isoformat()
        for lat_first, lat_last in ((LAT_LIMIT, -LAT_LIMIT), (-LAT_LIMIT, LAT_LIMIT)):
            try:
                rows = query(day, lat_first, lat_last)["table"]["rows"]
            except Exception as e:
                err = f"{day}: {e}"
                continue
            for _, lat, lon, dhw in rows:
                if dhw is None or dhw < MIN_DHW:
                    continue
                cells.append([round(lon, 2), round(lat, 2), round(dhw, 1)])
            used_day = day
            break
        if used_day:
            break
    if not used_day:
        print("coral fetch failed, leaving any existing file alone:", err)
        return
    payload = {
        "items": cells,
        "validTime": f"{used_day}T12:00:00Z",
        "fetched": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "source": "NOAA Coral Reef Watch daily 5 km Degree Heating Weeks, via CoastWatch ERDDAP",
        "class": "observed",
        "note": ("Accumulated heat stress over twelve weeks, thinned to about one degree. "
                 "Bleaching becomes likely above 4 and widespread above 8. "
                 "This is ocean heat stress, not observed bleaching: whether a reef actually "
                 "bleaches depends on the corals themselves."),
        "scale": [[1, "watch"], [4, "bleaching likely"], [8, "widespread bleaching"], [12, "mortality likely"]],
    }
    tmp = TARGET.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, separators=(",", ":")))
    tmp.replace(TARGET)
    print(f"wrote coral.json with {len(cells)} stressed cells for {used_day}")

if __name__ == "__main__":
    main()
